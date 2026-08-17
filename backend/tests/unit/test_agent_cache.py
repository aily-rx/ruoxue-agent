"""并发与成本优化单元测试 — LLM 单例 / embedding 缓存 / 回复缓存 / usage 记账。

覆盖:
  1. _build_llm 模块级单例（复用连接池, 不重复初始化）
  2. rag_service._embed_query LRU 缓存（相同 query 只推理一次）
  3. run_agent_stream 回复缓存: 命中返回缓存的全文、有工具调用不缓存、
     TTL 过期失效、use_cache 默认关闭（测试隔离）
  4. LLM token 用量（usage_metadata）进 JSON 日志（成本记账）
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Sequence

import numpy as np
import pytest
from backend.agent.agent_graph import (
    _build_llm,
    _reply_cache,
    run_agent_stream,
)
from backend.agent.rag_service import _embed_query
from backend.tests.unit.test_agent_stream import (
    FakeChromaMemory,
    FakeSkillLoader,
    _chunk,
    _d,
    _tool_message,
)
from langchain_core.messages import AIMessageChunk

_STREAM_LOGGER = "agent.agent_graph"


class FakeGraph:
    """替代编译后的 LangGraph: 按预设序列产出 stream_mode=messages 的 item。"""

    def __init__(self, items: list[object]) -> None:
        self._items = items

    async def astream(
        self, inputs: dict, config: dict | None = None, stream_mode: str = "messages"
    ) -> AsyncGenerator[object, None]:
        for item in self._items:
            yield item


def _patch_stream(monkeypatch, items: Sequence[object]) -> None:
    monkeypatch.setattr("backend.agent.agent_graph.agent_graph", FakeGraph(list(items)))
    monkeypatch.setattr("backend.agent.agent_graph.chroma_memory", FakeChromaMemory())
    monkeypatch.setattr("backend.agent.agent_graph._skill_loader", FakeSkillLoader())


@pytest.fixture(autouse=True)
def _clean_reply_cache():
    """每个测试前后清空模块级回复缓存, 防止测试间状态泄漏。"""
    _reply_cache.clear()
    yield
    _reply_cache.clear()


async def _collect(monkeypatch, text: str, items: Sequence[object], use_cache: bool = False) -> list:
    _patch_stream(monkeypatch, items)
    events = [ev async for ev in run_agent_stream(text, history=[], request_id="req-cache", use_cache=use_cache)]
    return [_d(ev).get("text", "") for ev in events if ev.event == "token"]


# --- LLM 单例 ---


def test_build_llm_is_singleton() -> None:
    first = _build_llm()
    second = _build_llm()
    assert first is second  # lru_cache(maxsize=1): 同一实例, 复用连接池


# --- embedding 缓存 ---


def test_embed_query_caches_identical_queries(monkeypatch) -> None:
    calls: list[str] = []

    def fake_embed(texts: list[str], is_query: bool = False) -> np.ndarray:
        calls.extend(texts)
        return np.zeros((len(texts), 1), dtype=np.float32)

    monkeypatch.setattr("backend.agent.rag_service._embed", fake_embed)

    q = "缓存测试查询-唯一串-20260814"
    _embed_query(q)
    _embed_query(q)
    assert len(calls) == 1, "相同 query 第二次应命中缓存, 不重复推理"

    _embed_query(q + "-另一个")
    assert len(calls) == 2, "不同 query 应重新推理"


# --- 回复缓存 ---


async def test_reply_cache_hit_returns_first_reply(monkeypatch) -> None:
    """第二次同问题直接命中缓存, 即使 graph 本会产出不同内容。"""
    first = await _collect(monkeypatch, "今天有什么安排", [_chunk("[EMOTION: happy|0.5] 第一次回答")], use_cache=True)
    assert first == ["第一次回答"]

    second = await _collect(
        monkeypatch, "今天有什么安排", [_chunk("[EMOTION: sad|0.3] 第二次不同内容")], use_cache=True
    )
    assert second == ["第一次回答"], "应命中缓存, 而不是重新生成"


async def test_reply_cache_logs_hit(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger=_STREAM_LOGGER)
    await _collect(monkeypatch, "缓存日志问题", [_chunk("[EMOTION: happy|0.5] 答案")], use_cache=True)
    await _collect(monkeypatch, "缓存日志问题", [_chunk("x")], use_cache=True)
    assert "reply cache hit" in caplog.text


async def test_tool_calls_not_cached(monkeypatch) -> None:
    """走了工具的对话绝不缓存（回复依赖外部数据, 不能复用）。"""
    tool_items = [_chunk("查一下", tool_calls=True), _tool_message(), _chunk("[EMOTION: happy|0.5] 查到了")]
    first = await _collect(monkeypatch, "查个数据", tool_items, use_cache=True)
    assert first == ["查到了"]

    second = await _collect(monkeypatch, "查个数据", [_chunk("[EMOTION: happy|0.5] 重新查的")], use_cache=True)
    assert second == ["重新查的"], "有工具调用的回复不应被缓存"


async def test_reply_cache_expires_by_ttl(monkeypatch) -> None:
    """TTL 过期后应重新走完整链路。"""
    monkeypatch.setattr("backend.agent.agent_graph._REPLY_CACHE_TTL_S", -1)  # 写入即过期

    await _collect(monkeypatch, "过期测试问题", [_chunk("[EMOTION: happy|0.5] 第一版")], use_cache=True)
    second = await _collect(monkeypatch, "过期测试问题", [_chunk("[EMOTION: happy|0.5] 第二版")], use_cache=True)
    assert second == ["第二版"], "过期缓存应失效, 重新生成"


async def test_cache_off_by_default(monkeypatch) -> None:
    """use_cache 默认关闭（routes 显式开启）——测试与真实链路隔离。"""
    await _collect(monkeypatch, "默认不开缓存", [_chunk("[EMOTION: happy|0.5] 第一次")])
    second = await _collect(monkeypatch, "默认不开缓存", [_chunk("[EMOTION: happy|0.5] 第二次")], use_cache=True)
    assert second == ["第二次"], "默认关闭时第一次不应写缓存"


# --- usage 记账 ---


async def test_usage_metadata_logged(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger=_STREAM_LOGGER)
    chunk = AIMessageChunk(
        content="[EMOTION: happy|0.5] 你好",
        usage_metadata={"input_tokens": 120, "output_tokens": 8, "total_tokens": 128},
    )
    _patch_stream(monkeypatch, [chunk])

    [ev async for ev in run_agent_stream("测试", history=[], request_id="req-usage")]

    usage = next(r for r in caplog.records if r.getMessage() == "llm usage")
    assert usage.input_tokens == 120
    assert usage.output_tokens == 8
    assert usage.request_id == "req-usage"


async def test_no_usage_log_without_metadata(monkeypatch, caplog) -> None:
    """模型不返回 usage_metadata 时（如 mock/Fake 链路）不产生 usage 日志。"""
    caplog.set_level(logging.INFO, logger=_STREAM_LOGGER)
    _patch_stream(monkeypatch, [_chunk("普通回复")])

    [ev async for ev in run_agent_stream("测试")]

    assert not any(r.getMessage() == "llm usage" for r in caplog.records)
