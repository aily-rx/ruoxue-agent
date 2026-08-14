"""可观测性单元测试 — JSON 日志格式 / Agent 阶段埋点 / request_id 贯穿。

覆盖:
  1. JSONFormatter 输出 extra 自定义字段（request_id / duration_ms）
  2. run_agent_stream 每个阶段输出结构化日志, 且 request_id 一致
  3. LLM 重试时打 WARNING 日志（便于 tracing 定位抖动）

外部依赖 mock 手法与 test_agent_stream.py 一致。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from backend.agent.agent_graph import _ainvoke_with_retry, run_agent_stream
from backend.config import JSONFormatter
from backend.tests.unit.test_agent_robustness import FlakyLLM
from backend.tests.unit.test_agent_stream import FakeChromaMemory, FakeSkillLoader, _chunk
from langchain_core.messages import AIMessage

_STREAM_LOGGER = "agent.agent_graph"


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


# --- JSONFormatter: extra 字段 ---


def test_json_formatter_includes_extra_fields() -> None:
    record = logging.LogRecord(
        name="agent.agent_graph",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="chroma retrieve",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-abc123"
    record.duration_ms = 12.5
    record.tool_calls = 2

    payload = json.loads(JSONFormatter().format(record))
    assert payload["message"] == "chroma retrieve"
    assert payload["request_id"] == "req-abc123"
    assert payload["duration_ms"] == 12.5
    assert payload["tool_calls"] == 2


def test_json_formatter_always_has_standard_fields() -> None:
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello", (), None)
    payload = json.loads(JSONFormatter().format(record))
    assert {"timestamp", "level", "logger", "message"} <= set(payload.keys())


def test_json_formatter_serializes_unserializable_extra() -> None:
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", (), None)
    record.weird = object()  # 不可 JSON 序列化 → 应转字符串而不是报错
    payload = json.loads(JSONFormatter().format(record))
    assert isinstance(payload["weird"], str)


# --- run_agent_stream: 阶段埋点 + request_id 贯穿 ---


async def test_stream_emits_all_stage_logs(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger=_STREAM_LOGGER)
    _patch_stream(monkeypatch, [_chunk("[EMOTION: happy|0.5] 你好")])

    events = [ev async for ev in run_agent_stream("测试", history=[], request_id="req-test-1")]

    assert [ev.event for ev in events][-1] == "done"
    text = caplog.text
    assert "agent request start" in text
    assert "chroma retrieve" in text
    assert "skill match" in text
    assert "agent request done" in text


async def test_request_id_threads_through_all_logs(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger=_STREAM_LOGGER)
    _patch_stream(monkeypatch, [_chunk("回复")])

    rid = "req-thread-42"
    [ev async for ev in run_agent_stream("测试", history=[], request_id=rid)]

    records = [r for r in caplog.records if r.name == _STREAM_LOGGER]
    assert len(records) >= 4
    for record in records:
        assert record.request_id == rid, f"{record.getMessage()} 的 request_id 不一致"


async def test_stream_logs_tool_calls_and_reply_length(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger=_STREAM_LOGGER)
    _patch_stream(monkeypatch, [_chunk("[EMOTION: happy|0.5] 好的")])

    [ev async for ev in run_agent_stream("测试", history=[], request_id="req-len")]

    done = next(r for r in caplog.records if r.getMessage() == "agent request done")
    assert done.tool_calls == 0
    assert done.reply_chars == 2  # "好的"


async def test_stream_without_request_id_generates_one(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger=_STREAM_LOGGER)
    _patch_stream(monkeypatch, [_chunk("回复")])

    [ev async for ev in run_agent_stream("测试")]

    records = [r for r in caplog.records if r.name == _STREAM_LOGGER]
    assert records
    rid = records[0].request_id
    assert isinstance(rid, str) and len(rid) == 12  # uuid4().hex[:12]
    for record in records[1:]:
        assert record.request_id == rid


# --- LLM 重试日志 ---


async def test_retry_emits_warning_log(monkeypatch, caplog) -> None:
    caplog.set_level(logging.WARNING, logger=_STREAM_LOGGER)
    monkeypatch.setattr("tenacity.nap.sleep", lambda *a, **k: None)  # 测试不等待退避

    llm = FlakyLLM(fail_count=1)
    result = await _ainvoke_with_retry(llm, [])
    assert isinstance(result, AIMessage)

    assert "llm call retry" in caplog.text
    records = [r for r in caplog.records if r.getMessage() == "llm call retry"]
    assert records and records[0].attempt == 1  # 第一次失败后重试
