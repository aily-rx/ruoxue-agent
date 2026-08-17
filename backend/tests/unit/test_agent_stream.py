"""run_agent_stream 流式解析单元测试 — mock 掉 LLM/记忆/skill 外部依赖。

被测对象是 agent_graph.run_agent_stream 的**确定性解析逻辑**:
  1. [EMOTION: xxx|0.0] 标签提取与剥离（单 chunk / 跨 chunk）
  2. 无标签时默认 neutral/0.3
  3. 工具阶段 token 抑制（tool_call_chunks → ToolMessage 复位）
  4. 事件顺序以 done 收尾

FakeGraph 替换模块级 agent_graph, 产出受控的 chunk 序列;
chroma_memory / _skill_loader 也替换为假实现, 保证测试不触碰真实存储。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence

from backend.agent.agent_graph import run_agent_stream
from backend.agent.emotional_agent import SSEEvent
from langchain_core.messages import AIMessageChunk, ToolMessage


def _d(ev: SSEEvent) -> dict:
    """测试里事件 data 必为 dict（SSEEvent.data 类型是 dict | str）。"""
    assert isinstance(ev.data, dict)
    return ev.data


class FakeGraph:
    """替代编译后的 LangGraph: 按预设序列产出 stream_mode=messages 的 item。"""

    def __init__(self, items: list[object]) -> None:
        self._items = items

    async def astream(
        self, inputs: dict, config: dict | None = None, stream_mode: str = "messages"
    ) -> AsyncGenerator[object, None]:
        for item in self._items:
            yield item


class FakeChromaMemory:
    """替代 chroma_memory: 不查询真实 Chroma。"""

    def retrieve_context(self, query: str) -> str:
        return ""


class FakeSkillLoader:
    """替代 _skill_loader: 不加载真实 skills 目录。"""

    def match(self, user_input: str) -> str | None:
        return None

    def core_rules(self) -> str:
        return ""


def _chunk(text: str, tool_calls: bool = False) -> AIMessageChunk:
    """构造一个 LLM 文本 chunk（可选带工具调用标记）。"""
    return AIMessageChunk(
        content=text,
        tool_call_chunks=(
            [{"index": 0, "name": "search_web", "args": "{}", "id": "call_1", "type": "tool_call_chunk"}]
            if tool_calls
            else []
        ),
    )


def _tool_message() -> ToolMessage:
    return ToolMessage(content="工具返回结果", tool_call_id="call_1")


def _patch_deps(monkeypatch, items: Sequence[object]) -> None:
    """替换 agent_graph 模块的全局依赖为受控假实现。"""
    monkeypatch.setattr("backend.agent.agent_graph.agent_graph", FakeGraph(list(items)))
    monkeypatch.setattr("backend.agent.agent_graph.chroma_memory", FakeChromaMemory())
    monkeypatch.setattr("backend.agent.agent_graph._skill_loader", FakeSkillLoader())


async def _collect(monkeypatch, items: Sequence[object]) -> list[SSEEvent]:
    _patch_deps(monkeypatch, items)
    events = [ev async for ev in run_agent_stream("测试输入", history=[])]
    return events


def _event_names(events: list[SSEEvent]) -> list[str]:
    return [ev.event for ev in events]


# --- 情绪标签提取 ---


async def test_emotion_tag_single_chunk(monkeypatch) -> None:
    events = await _collect(monkeypatch, [_chunk("[EMOTION: happy|0.8]"), _chunk("你好"), _chunk("世界！")])
    assert _event_names(events) == ["emotion", "token", "token", "done"]
    assert events[0].data == {"emotion": "happy", "intensity": 0.8}
    assert events[1].data == {"text": "你好"}
    assert events[2].data == {"text": "世界！"}


async def test_emotion_tag_split_across_chunks(monkeypatch) -> None:
    """标签被网络 chunk 截断时, 跨 chunk 累积后仍能提取。"""
    events = await _collect(monkeypatch, [_chunk("[EMOTION: sad|0.5] 我"), _chunk("很难过")])
    assert _event_names(events) == ["emotion", "token", "token", "done"]
    assert events[0].data == {"emotion": "sad", "intensity": 0.5}
    assert events[1].data == {"text": "我"}
    assert events[2].data == {"text": "很难过"}


async def test_emotion_tag_inline_with_remaining_text(monkeypatch) -> None:
    """标签与正文同 chunk: 剥离标签后剩余文本立即作为 token 发出。"""
    events = await _collect(monkeypatch, [_chunk("[EMOTION: surprised|0.9] 真的吗")])
    assert _event_names(events) == ["emotion", "token", "done"]
    assert events[0].data == {"emotion": "surprised", "intensity": 0.9}
    assert events[1].data == {"text": "真的吗"}


async def test_missing_emotion_tag_defaults_neutral(monkeypatch) -> None:
    events = await _collect(monkeypatch, [_chunk("普通回复")])
    assert _event_names(events) == ["emotion", "token", "done"]
    assert events[0].data == {"emotion": "neutral", "intensity": 0.3}
    assert events[1].data == {"text": "普通回复"}


# --- 工具阶段 token 抑制 ---


async def test_tool_phase_suppresses_internal_thinking(monkeypatch) -> None:
    """LLM 宣告工具调用后的内耗文本必须被丢弃, 只保留最终回复。"""
    events = await _collect(
        monkeypatch,
        [
            _chunk("我需要查一下资料", tool_calls=True),  # 进入工具阶段, 本段被丢弃
            _tool_message(),  # 工具返回 → 阶段复位
            _chunk("[EMOTION: happy|0.6] 查到了"),
            _chunk("结果如下"),
        ],
    )
    texts = [_d(ev).get("text", "") for ev in events if ev.event == "token"]
    assert texts == ["查到了", "结果如下"]
    assert "我需要查一下资料" not in texts
    assert _event_names(events)[-1] == "done"


async def test_tool_message_without_tool_calls_passes_through(monkeypatch) -> None:
    """非工具场景: 普通文本 chunk 不应被抑制。"""
    events = await _collect(monkeypatch, [_chunk("[EMOTION: neutral|0.3] 直接回答")])
    texts = [_d(ev).get("text", "") for ev in events if ev.event == "token"]
    assert texts == ["直接回答"]


# --- 事件收尾 ---


async def test_done_event_always_last(monkeypatch) -> None:
    for items in (
        [_chunk("[EMOTION: happy|0.5] 好")],
        [_chunk("无标签")],
        [_chunk("a", tool_calls=True), _tool_message(), _chunk("[EMOTION: sad|0.4] b")],
    ):
        events = await _collect(monkeypatch, items)
        assert _event_names(events)[-1] == "done"
