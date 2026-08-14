"""Chroma 长期记忆单元测试 — 临时目录隔离真实 chroma_data。

覆盖: store_turn 写入, retrieve_context 语义命中/空库返回空,
turn_count 统计。全部使用 tmp_path 实例化, 不触碰全局 chroma_memory 单例。
"""

from __future__ import annotations

from pathlib import Path

from backend.agent.chroma_memory import ChromaMemory


def _make_memory(tmp_path: Path) -> ChromaMemory:
    return ChromaMemory(persist_dir=str(tmp_path / "chroma"))


def test_store_and_retrieve_semantic_match(tmp_path: Path) -> None:
    memory = _make_memory(tmp_path)
    memory.store_turn("sess-1", "What is the capital of France?", "Paris is the capital.")
    assert memory.turn_count == 1

    context = memory.retrieve_context("capital of France")
    assert "Paris is the capital." in context


def test_retrieve_returns_empty_when_nothing_stored(tmp_path: Path) -> None:
    memory = _make_memory(tmp_path)
    assert memory.retrieve_context("anything") == ""


def test_retrieve_excludes_irrelevant_turns(tmp_path: Path) -> None:
    memory = _make_memory(tmp_path)
    memory.store_turn("sess-1", "Tell me about cats", "Cats are furry animals.")
    memory.store_turn("sess-1", "What is the weather?", "It is sunny today.")

    context = memory.retrieve_context("weather forecast")
    assert "sunny" in context
    assert "cats" not in context


def test_turn_count_tracks_stored_turns(tmp_path: Path) -> None:
    memory = _make_memory(tmp_path)
    assert memory.turn_count == 0
    memory.store_turn("sess-1", "hello", "hi")
    memory.store_turn("sess-2", "how are you", "fine")
    assert memory.turn_count == 2


def test_persist_across_instances(tmp_path: Path) -> None:
    """数据写入磁盘后, 新实例应能读到（持久化验证）。"""
    persist = str(tmp_path / "chroma")
    ChromaMemory(persist_dir=persist).store_turn("sess-1", "favorite color", "blue")

    memory2 = ChromaMemory(persist_dir=persist)
    assert memory2.turn_count == 1
    assert "blue" in memory2.retrieve_context("favorite color")
