"""Human-in-the-loop 单元测试 — 工具调用前人工确认。

用真实编译的 LangGraph（含 ConfirmingToolNode + MemorySaver）+ ScriptedLLM
验证完整确认流程:
  1. 允许 → 工具真的执行（FakeTavily 被调用）→ 回复继续
  2. 拒绝 → 工具不执行 → LLM 转述取消
  3. 超时 → 默认拒绝
  4. 未知 request_id → confirm 返回 False
  5. HITL 关闭 → 无 tool_request 事件, 工具直接执行
"""

from __future__ import annotations

import pytest
from backend.agent.agent_graph import confirm_tool_call, run_agent_stream
from backend.tests.unit.test_agent_stream import FakeChromaMemory, FakeSkillLoader
from langchain_core.messages import AIMessage

_TOOL_REPLY = AIMessage(
    content="",
    tool_calls=[{"name": "search_web", "args": {"query": "测试"}, "id": "call_1", "type": "tool_call"}],
)
_FINAL_REPLY = AIMessage(content="[EMOTION: happy|0.5] 好的，已经处理完了。")


class ScriptedLLM:
    """按调用次数返回预设回复（第一次声明工具调用, 第二次正常回复）。"""

    def __init__(self, replies: list[AIMessage]) -> None:
        self._replies = replies
        self.calls = 0

    def bind_tools(self, tools: list) -> ScriptedLLM:
        return self

    async def ainvoke(self, messages: list) -> AIMessage:
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return reply


class FakeTavily:
    """记录 search 调用的假 Tavily 客户端。"""

    def __init__(self) -> None:
        self.search_calls: list[str] = []

    def search(self, query: str, **kwargs) -> dict:
        self.search_calls.append(query)
        return {"answer": "摘要", "results": []}


def _patch_env(monkeypatch, llm: ScriptedLLM, tavily: FakeTavily, hitl_on: bool = True) -> None:
    monkeypatch.setattr("backend.agent.agent_graph.HITL_ENABLED", hitl_on)
    monkeypatch.setattr("backend.agent.agent_graph.HITL_CONFIRM_TIMEOUT", 5)
    monkeypatch.setattr("backend.agent.agent_graph._build_llm", lambda: llm)
    monkeypatch.setattr("backend.agent.agent_graph.chroma_memory", FakeChromaMemory())
    monkeypatch.setattr("backend.agent.agent_graph._skill_loader", FakeSkillLoader())
    monkeypatch.setattr("backend.agent.tools._tavily", tavily)


async def _consume_until_tool_request(
    monkeypatch, llm, tavily, rid: str = "hitl-approve", hitl_on: bool = True
) -> tuple[list, object]:
    """消费到 tool_request 事件为止, 返回 (已消费事件, 挂起的 generator)。

    generator 此刻正挂起在确认等待（future 已注册）—— 调 confirm_tool_call 后
    用 async for 继续消费剩余事件。rid 必须每个测试唯一（MemorySaver 按
    thread_id 存状态, 复用会污染）。
    """
    _patch_env(monkeypatch, llm, tavily, hitl_on)
    gen = run_agent_stream("帮我搜索一下", history=[], request_id=rid)
    events: list = []
    ev = await anext(gen)
    while ev.event != "tool_request":
        events.append(ev)
        ev = await anext(gen)
    events.append(ev)
    return events, gen


@pytest.fixture(autouse=True)
def _clean_pending():
    """清理跨测试的待确认状态。"""
    from backend.agent.agent_graph import _pending_confirms

    _pending_confirms.clear()
    yield
    _pending_confirms.clear()


@pytest.mark.asyncio
async def test_approved_executes_tool(monkeypatch) -> None:
    """允许 → 工具真的执行（FakeTavily 被调用）→ 后续回复正常。"""
    llm = ScriptedLLM([_TOOL_REPLY, _FINAL_REPLY])
    tavily = FakeTavily()

    events, gen = await _consume_until_tool_request(monkeypatch, llm, tavily, rid="hitl-approve")
    request_event = events[-1]
    assert request_event.event == "tool_request"
    payload = request_event.data
    assert payload["request_id"] == "hitl-approve"
    assert payload["tool_calls"][0]["name"] == "search_web"
    assert payload["timeout_s"] == 5

    # 确认前工具未执行; 确认后 generator 恢复, 工具执行
    assert tavily.search_calls == []
    assert confirm_tool_call("hitl-approve", True) is True
    async for ev in gen:
        events.append(ev)

    assert tavily.search_calls == ["测试"], "允许后工具必须执行"
    texts = [ev.data.get("text", "") for ev in events if ev.event == "token"]
    assert "已经处理完了" in "".join(texts)
    assert [ev.event for ev in events][-1] == "done"


@pytest.mark.asyncio
async def test_rejected_skips_tool(monkeypatch) -> None:
    """拒绝 → 工具不执行 → LLM 转述取消。"""
    llm = ScriptedLLM([_TOOL_REPLY, _FINAL_REPLY])
    tavily = FakeTavily()

    events, gen = await _consume_until_tool_request(monkeypatch, llm, tavily, rid="hitl-reject")
    assert confirm_tool_call("hitl-reject", False) is True
    async for ev in gen:
        events.append(ev)

    assert tavily.search_calls == [], "拒绝后工具不得执行"
    texts = [ev.data.get("text", "") for ev in events if ev.event == "token"]
    assert "已经处理完了" in "".join(texts)  # 第二轮 LLM 照常回复


def test_timeout_defaults_to_reject(monkeypatch) -> None:
    """超时未确认 → 默认拒绝（不执行工具, 流程继续）。"""
    import asyncio

    monkeypatch.setattr("backend.agent.agent_graph.HITL_CONFIRM_TIMEOUT", 1)
    llm = ScriptedLLM([_TOOL_REPLY, _FINAL_REPLY])
    tavily = FakeTavily()

    # 不确认, 直接消费全部事件（超时后自动拒绝继续）
    async def collect():
        _patch_env(monkeypatch, llm, tavily)
        return [ev async for ev in run_agent_stream("帮我搜索一下", history=[], request_id="hitl-timeout")]

    events = asyncio.run(collect())
    assert tavily.search_calls == [], "超时默认拒绝, 工具不得执行"
    assert any(ev.event == "tool_request" for ev in events)
    assert [ev.event for ev in events][-1] == "done"


def test_confirm_unknown_request_id() -> None:
    """未知/已过期的 request_id 返回 False（端点 404）。"""
    assert confirm_tool_call("no-such-id", True) is False


@pytest.mark.asyncio
async def test_hitl_disabled_runs_tool_without_confirm(monkeypatch) -> None:
    """HITL 关闭时无 tool_request 事件, 工具直接执行（与旧行为一致）。"""
    llm = ScriptedLLM([_TOOL_REPLY, _FINAL_REPLY])
    tavily = FakeTavily()

    _patch_env(monkeypatch, llm, tavily, hitl_on=False)
    events = [ev async for ev in run_agent_stream("帮我搜索一下", history=[], request_id="hitl-off")]

    assert not any(ev.event == "tool_request" for ev in events)
    assert tavily.search_calls == ["测试"], "HITL 关闭时工具直接执行"
    texts = [ev.data.get("text", "") for ev in events if ev.event == "token"]
    assert "已经处理完了" in "".join(texts)
