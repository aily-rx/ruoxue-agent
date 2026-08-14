"""RAG service 单元测试 — 分块 / 分词 / 临时知识库行为。

覆盖: _chunk_text 边界(短文本/空/超长/overlap/max_chunks), _tokenize 过滤,
KnowledgeBase 用 tmp_path 临时目录验证 建库/检索/持久化/清空 全流程。
不依赖真实 faiss_data(被 gitignore 的索引), 不触碰全局 knowledge_base 单例。
"""

from __future__ import annotations

from pathlib import Path

from backend.agent.rag_service import KnowledgeBase, _chunk_text, _tokenize

_DOC = (
    "若雪是一个多模态 AI 数字人助手, 基于 React 和 Live2D 构建。"
    "她支持文字聊天、语音交互和口型同步。后端使用 LangGraph 管理 Agent 流程, "
    "工具包括网页搜索、天气查询和知识库检索。前端通过 SSE 接收流式回复。"
    "长期记忆使用 Chroma 向量库, 知识库检索使用 FAISS 与 BM25 混合方案。"
)


# --- _chunk_text: 分块边界 ---


def test_chunk_text_short_unchanged() -> None:
    assert _chunk_text("短文本") == ["短文本"]


def test_chunk_text_empty() -> None:
    assert _chunk_text("") == []


def test_chunk_text_whitespace_only() -> None:
    assert _chunk_text("   \n  ") == []


def test_chunk_text_long_splits_with_overlap() -> None:
    text = _DOC * 30  # 约 30 × 100+ 字, 必超 500 字上限
    chunks = _chunk_text(text)
    assert len(chunks) >= 2
    assert len(chunks[0]) <= 500
    # 相邻 chunk 应有重叠(overlap=80)
    assert text.find(chunks[1][:30]) < text.find(chunks[0]) + len(chunks[0])


def test_chunk_text_respects_max_chunks() -> None:
    text = _DOC * 5000
    chunks = _chunk_text(text)
    assert len(chunks) <= 500  # max_chunks 上限


def test_chunk_text_prefers_sentence_boundary() -> None:
    """长文本优先在句号处断句。"""
    text = ("第一句。" * 100) + ("第二句。" * 100)
    chunks = _chunk_text(text)
    assert any(c.endswith("。") for c in chunks[:-1]) or len(chunks) == 1


# --- _tokenize: BM25 分词 ---


def test_tokenize_keeps_chinese_words() -> None:
    tokens = _tokenize("混合检索知识库")
    assert "混合" in tokens and "检索" in tokens


def test_tokenize_lowercases_latin() -> None:
    assert "indexflatip" in _tokenize("FAISS IndexFlatIP")


def test_tokenize_drops_pure_punctuation() -> None:
    tokens = _tokenize("FastAPI + Uvicorn | 流式")
    assert "+" not in tokens and "|" not in tokens
    assert "fastapi" in tokens


def test_tokenize_empty() -> None:
    assert _tokenize("") == []


# --- KnowledgeBase: 临时目录全流程 ---


def test_knowledge_base_index_and_hybrid_search(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    docs_dir.joinpath("intro.md").write_text(_DOC, encoding="utf-8")

    kb = KnowledgeBase(persist_dir=str(tmp_path / "faiss_data"))
    count = kb.index_directory(str(docs_dir))
    assert count > 0
    assert kb.chunk_count == count

    hits = kb.search_hybrid("混合检索是怎么实现的", k=3)
    assert hits, "建库后应能检索到结果"
    assert all(0 <= idx < count for idx, _ in hits)
    assert all(score > 0 for _, score in hits)


def test_search_formats_result_with_source(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    docs_dir.joinpath("intro.md").write_text(_DOC, encoding="utf-8")

    kb = KnowledgeBase(persist_dir=str(tmp_path / "faiss_data"))
    kb.index_directory(str(docs_dir))

    result = kb.search("SSE 流式回复")
    assert "intro.md" in result  # 结果带来源标注
    assert "rrf=" in result


def test_search_on_empty_kb(tmp_path: Path) -> None:
    kb = KnowledgeBase(persist_dir=str(tmp_path / "faiss_data"))
    assert kb.search_hybrid("任何查询") == []
    assert kb.search("任何查询") == "No relevant documents found."


def test_persist_roundtrip_reloads_index(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    docs_dir.joinpath("intro.md").write_text(_DOC, encoding="utf-8")
    kb_dir = str(tmp_path / "faiss_data")

    kb = KnowledgeBase(persist_dir=kb_dir)
    count = kb.index_directory(str(docs_dir))

    # 重新实例化: 应从磁盘恢复索引, 且 BM25 重建成功
    kb2 = KnowledgeBase(persist_dir=kb_dir)
    assert kb2.chunk_count == count
    assert kb2.search_hybrid("混合检索", k=2), "恢复后应仍可混合检索"


def test_clear_removes_index_files(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    docs_dir.joinpath("intro.md").write_text(_DOC, encoding="utf-8")
    kb_dir = str(tmp_path / "faiss_data")

    kb = KnowledgeBase(persist_dir=kb_dir)
    kb.index_directory(str(docs_dir))
    assert kb.chunk_count > 0

    kb.clear()
    assert kb.chunk_count == 0
    assert not Path(kb_dir, "knowledge.index").exists()
    assert not Path(kb_dir, "knowledge_meta.json").exists()


# --- 检索参数配置化（RAG_TOP_K 等来自 config, 调参不改代码）---


def test_hybrid_defaults_follow_config() -> None:
    import inspect

    from backend.config import RAG_BM25_K, RAG_TOP_K, RAG_VECTOR_K

    sig = inspect.signature(KnowledgeBase.search_hybrid)
    assert sig.parameters["k"].default is None  # None → 运行时解析为 RAG_TOP_K
    assert RAG_TOP_K > 0 and RAG_VECTOR_K > 0 and RAG_BM25_K > 0


def test_search_honors_explicit_k(tmp_path: Path) -> None:
    """显式传 k 时优先于 config 默认值。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    docs_dir.joinpath("intro.md").write_text(_DOC, encoding="utf-8")

    kb = KnowledgeBase(persist_dir=str(tmp_path / "faiss_data"))
    kb.index_directory(str(docs_dir))

    hits = kb.search_hybrid("混合检索", k=1)
    assert len(hits) <= 1
