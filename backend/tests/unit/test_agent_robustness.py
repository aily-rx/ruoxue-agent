"""Agent 容错单元测试 — 工具循环上限 / LLM 重试 / 超限提示。

覆盖:
  1. should_continue 超轮数强制 END
  2. agent_node 递增 tool_rounds 且走重试包装
  3. _ainvoke_with_retry: 失败后指数退避重试, 3 次耗尽原样抛出
  4. run_agent_stream: 工具循环超限且无回复时给用户提示, 而不是沉默

外部依赖(mock 手法)与 test_agent_stream.py 一致: FakeGraph 替换编译后的图。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from backend.agent.agent_graph import (
    MAX_TOOL_ROUNDS,
    _ainvoke_with_retry,
    agent_node,
    run_agent_stream,
    should_continue,
)
from backend.agent.emotional_agent import SSEEvent
from backend.tests.unit.test_agent_stream import FakeChromaMemory, FakeSkillLoader, _chunk, _tool_message
from langchain_core.messages import AIMessage
from langgraph.graph import END


class FakeLLM:
    """可控 LLM: bind_tools 透传, ainvoke 返回预设结果。"""

    def __init__(self, result: AIMessage) -> None:
        self._result = result
        self.invoked = False

    def bind_tools(self, tools: list) -> FakeLLM:
        return self

    async def ainvoke(self, messages: list) -> AIMessage:
        self.invoked = True
        return self._result


class FlakyLLM:
    """前 fail_count 次调用抛异常, 之后成功; 记录调用次数。"""

    def __init__(self, fail_count: int) -> None:
        self.fail_count = fail_count
        self.calls = 0

    async def ainvoke(self, messages: list) -> AIMessage:
        self.calls += 1
        if self.calls <= self.fail_count:
            raise RuntimeError("network error")
        return AIMessage(content="ok")


class FakeGraph:
    """替代编译后的 LangGraph: 按预设序列产出 stream_mode=messages 的 item。"""

    def __init__(self, items: list[object]) -> None:
        self._items = items

    async def astream(self, inputs: dict, stream_mode: str = "messages") -> AsyncGenerator[object, None]:
        for item in self._items:
            yield item


def _patch_stream(monkeypatch, items: list[object]) -> None:
    monkeypatch.setattr("backend.agent.agent_graph.agent_graph", FakeGraph(items))
    monkeypatch.setattr("backend.agent.agent_graph.chroma_memory", FakeChromaMemory())
    monkeypatch.setattr("backend.agent.agent_graph._skill_loader", FakeSkillLoader())


# --- should_continue: 循环上限 ---


def test_should_continue_stops_when_over_round_limit() -> None:
    state = {
        "messages": [
            AIMessage(content="x", tool_calls=[{"name": "search_web", "args": {}, "id": "1", "type": "tool_call"}])
        ],
        "tool_rounds": MAX_TOOL_ROUNDS + 1,
    }
    assert should_continue(state) == END


def test_should_continue_routes_to_tools_within_limit() -> None:
    state = {
        "messages": [
            AIMessage(content="x", tool_calls=[{"name": "search_web", "args": {}, "id": "1", "type": "tool_call"}])
        ],
        "tool_rounds": 3,
    }
    assert should_continue(state) == "tools"


def test_should_continue_ends_without_tool_calls() -> None:
    state = {"messages": [AIMessage(content="普通回复")], "tool_rounds": 0}
    assert should_continue(state) == END


def test_should_continue_ends_when_over_limit_even_without_tools() -> None:
    state = {"messages": [AIMessage(content="回复")], "tool_rounds": MAX_TOOL_ROUNDS + 1}
    assert should_continue(state) == END


# --- agent_node: 轮数递增 + 走重试包装 ---


async def test_agent_node_increments_tool_rounds(monkeypatch) -> None:
    llm = FakeLLM(AIMessage(content="[EMOTION: happy|0.5] 你好"))
    monkeypatch.setattr("backend.agent.agent_graph._build_llm", lambda: llm)

    calls: list[list] = []

    async def fake_retry(llm_obj, messages):
        calls.append(messages)
        return await llm_obj.ainvoke(messages)

    monkeypatch.setattr("backend.agent.agent_graph._ainvoke_with_retry", fake_retry)

    state = {
        "messages": [],
        "system_prompt": "persona",
        "runtime_context": "",
        "memory_context": "",
        "skill_context": "",
        "tool_rounds": 2,
    }
    result = await agent_node(state)
    assert result["tool_rounds"] == 3
    assert calls, "agent_node 必须经由重试包装调用 LLM"
    assert llm.invoked


# --- _ainvoke_with_retry: 指数退避重试 ---


async def test_retry_succeeds_after_transient_failures(monkeypatch) -> None:
    monkeypatch.setattr("tenacity.nap.sleep", lambda *a, **k: None)  # 测试不等待退避
    llm = FlakyLLM(fail_count=2)
    result = await _ainvoke_with_retry(llm, [])
    assert isinstance(result, AIMessage)
    assert result.content == "ok"
    assert llm.calls == 3  # 失败 2 次 + 成功 1 次


async def test_retry_reraises_after_exhausting_attempts(monkeypatch) -> None:
    monkeypatch.setattr("tenacity.nap.sleep", lambda *a, **k: None)
    llm = FlakyLLM(fail_count=99)
    with pytest.raises(RuntimeError):
        await _ainvoke_with_retry(llm, [])
    assert llm.calls == 3  # 3 次尝试后原样抛出, 不吞异常


# --- run_agent_stream: 超限提示 ---


async def test_tool_limit_reached_yields_hint(monkeypatch) -> None:
    """工具调用超限且没有任何回复 → 明确提示用户而不是沉默。"""
    items = [_chunk("第1次", tool_calls=True)] * (MAX_TOOL_ROUNDS + 1)
    _patch_stream(monkeypatch, items)

    events = [ev async for ev in run_agent_stream("任务", history=[])]
    texts = [ev.data.get("text", "") for ev in events if ev.event == "token"]
    assert texts and "拆小一点" in texts[0]
    assert _event_names(events)[-1] == "done"


async def test_normal_reply_within_limit_no_hint(monkeypatch) -> None:
    """正常回复（少量工具调用）不应出现提示。"""
    items = [_chunk("查一下", tool_calls=True), _tool_message(), _chunk("[EMOTION: happy|0.5] 查到了")]
    _patch_stream(monkeypatch, items)

    events = [ev async for ev in run_agent_stream("任务", history=[])]
    texts = [ev.data.get("text", "") for ev in events if ev.event == "token"]
    assert texts == ["查到了"]


def _event_names(events: list[SSEEvent]) -> list[str]:
    return [ev.event for ev in events]
