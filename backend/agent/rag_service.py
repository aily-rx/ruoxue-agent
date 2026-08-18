"""RAG knowledge base — FAISS vector index + BM25 hybrid retrieval.

Loads docs, chunks them, indexes with FAISS IndexFlatIP.
Embedding: bge-small-zh-v1.5 (Chinese-capable, local transformers) when the
model exists under model_assets/; falls back to Chroma's bundled ONNX
all-MiniLM-L6-v2 (English-only, weak on Chinese) otherwise.
Keyword search: jieba-tokenized BM25. Results are merged with RRF.

Why hybrid: vector search alone misses exact keywords (IDs, code, filenames);
BM25 alone misses paraphrases. RRF merges both rank lists robustly.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

import faiss
import jieba
import numpy as np
from backend.config import (
    RAG_BM25_K,
    RAG_RERANK_CANDIDATES,
    RAG_RERANK_ENABLED,
    RAG_RERANK_TOP_PASS,
    RAG_TOP_K,
    RAG_VECTOR_K,
)
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from rank_bm25 import BM25Okapi

_logger = logging.getLogger("agent.rag_service")

# ---------------------------------------------------------------------------
# Embedding — bge-small-zh-v1.5 (Chinese) with all-MiniLM-L6-v2 fallback
# ---------------------------------------------------------------------------

_EMBED_FN: DefaultEmbeddingFunction | None = None
_BGE_DIR = Path(__file__).resolve().parent.parent.parent / "model_assets" / "embeddings" / "bge-small-zh-v1.5"
_BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

_bge_model = None  # lazily loaded (AutoModel) — tuple (tokenizer, model)
_bge_ready: bool | None = None  # None = not yet probed


def _embed_fn() -> DefaultEmbeddingFunction:
    global _EMBED_FN
    if _EMBED_FN is None:
        _EMBED_FN = DefaultEmbeddingFunction()
    return _EMBED_FN


def _bge_available() -> bool:
    """True when the Chinese embedding model is present on disk."""
    global _bge_ready
    if _bge_ready is None:
        _bge_ready = (_BGE_DIR / "config.json").exists() and (_BGE_DIR / "model.safetensors").exists()
    return _bge_ready


def _embed(texts: list[str], is_query: bool = False) -> np.ndarray:
    """Embed texts into L2-normalized vectors.

    Uses bge-small-zh-v1.5 (512-dim, Chinese-capable) when available;
    otherwise falls back to Chroma's ONNX all-MiniLM-L6-v2 (384-dim).
    Query vectors get the bge retrieval instruction prefix (docs do not).
    """
    if _bge_available():
        return _embed_bge(texts, is_query=is_query)
    return _embed_onnx(texts)


@lru_cache(maxsize=512)
def _embed_query(query: str) -> np.ndarray:
    """Embed a single query with LRU caching — identical queries skip inference.

    Search hot paths (search_hybrid / search_indices) call this instead of
    _embed directly; repeated user questions re-run embedding on the same
    query, and CPU inference is the most expensive step of retrieval.
    Returns a (1, dim) L2-normalized vector; callers must not mutate it.
    """
    return _embed([query], is_query=True)


def _embed_onnx(texts: list[str]) -> np.ndarray:
    """Embed via Chroma's bundled ONNX model (all-MiniLM-L6-v2, 384-dim)."""
    fn = _embed_fn()
    vecs = fn(texts)
    arr = np.array(vecs, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms  # type: ignore[no-any-return]


def _embed_bge(texts: list[str], is_query: bool = False, batch_size: int = 64) -> np.ndarray:
    """Embed via local bge-small-zh-v1.5 (CPU, transformers). CLS pooling + L2-norm."""
    global _bge_model
    if _bge_model is None:
        from transformers import AutoModel, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(str(_BGE_DIR))
        model = AutoModel.from_pretrained(str(_BGE_DIR))
        model.eval()
        _bge_model = (tokenizer, model)
    tokenizer, model = _bge_model

    if is_query:
        texts = [_BGE_QUERY_PREFIX + t for t in texts]

    import torch

    vecs: list[np.ndarray] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        with torch.no_grad():
            inputs = tokenizer(batch, padding=True, truncation=True, max_length=512, return_tensors="pt")
            out = model(**inputs)
            vecs.append(out.last_hidden_state[:, 0].numpy())  # CLS pooling

    arr = np.vstack(vecs).astype(np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


# ---------------------------------------------------------------------------
# Text chunker
# ---------------------------------------------------------------------------


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """Split text into overlapping chunks, preferring natural boundaries."""
    text_len = len(text)
    if text_len <= chunk_size:
        return [text] if text.strip() else []

    chunks: list[str] = []
    start = 0
    max_chunks = 10000

    while start < text_len and len(chunks) < max_chunks:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            search_start = max(start, end - chunk_size // 5)
            window = text[search_start:end]
            for sep in ("\n\n", "\n", "。", "！", "？", ".", "!", "?"):
                idx = window.rfind(sep)
                if idx > 0:
                    end = search_start + idx + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        # 死循环防护（2026-08-18 修复）:
        # 短行文档（markdown 表格/列表）里 chunk 实际长度 < overlap 时,
        # 旧逻辑 start = end - overlap 会回退到原地, 同一片段被反复切出,
        # 直到 max_chunks 强制终止 → 索引 97% 内容重复（13501 条仅 346 唯一）。
        # 修复: overlap 只在 chunk 确实够长时生效, 否则无重叠直接前进。
        next_start = end - overlap
        start = next_start if next_start > start else end
    return chunks


# ---------------------------------------------------------------------------
# Tokenizer — for BM25 keyword index
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Tokenize text for BM25: jieba for Chinese, lowercase for Latin words.

    Drops whitespace and pure-punctuation tokens (e.g. "+", "|", "->")
    that carry no retrieval signal.

    注: 曾实验驼峰/下划线子词拆分（收尾① 分词粒度 miss 类）, 实测回退:
    query 侧子词全库乱匹配、doc 侧子词改变语料平均长度扰动 BM25 长度
    归一化, Recall@5 0.780→0.760。结论见 text/rag/rag-eval.md。
    """
    tokens: list[str] = []
    for tok in jieba.lcut(text.lower()):
        tok = tok.strip()
        if not tok or tok.isspace():
            continue
        if all(not ch.isalnum() for ch in tok):
            continue  # pure punctuation / symbols
        tokens.append(tok)
    return tokens


# ---------------------------------------------------------------------------
# KnowledgeBase — FAISS-backed
# ---------------------------------------------------------------------------


class KnowledgeBase:
    """Indexes and searches docs using FAISS (per PRD) + sentence-transformers."""

    SUPPORTED_SUFFIXES = {".txt", ".md", ".py", ".ts", ".tsx", ".json", ".yaml", ".yml", ".pdf"}

    def __init__(self, persist_dir: str = "./faiss_data") -> None:
        self._dir = Path(persist_dir).resolve()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "knowledge.index"
        self._meta_path = self._dir / "knowledge_meta.json"

        self._index: faiss.Index | None = None
        self._docs: list[str] = []  # aligned with index rows
        self._metas: list[dict] = []  # metadata per chunk
        self._bm25: BM25Okapi | None = None  # keyword index (built from _docs)

        if self._index_path.exists():
            self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            self._index = faiss.read_index(str(self._index_path))
            with open(self._meta_path, encoding="utf-8") as f:
                data = json.load(f)
            self._docs = data.get("docs", [])
            self._metas = data.get("metas", [])
        except Exception:
            self._index = None
            self._docs = []
            self._metas = []
            self._bm25 = None
        # BM25 rebuild failure must not break vector retrieval
        try:
            self._build_bm25()
        except Exception:
            self._bm25 = None

    def _save(self) -> None:
        if self._index is not None:
            faiss.write_index(self._index, str(self._index_path))
        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump({"docs": self._docs, "metas": self._metas}, f, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def index_directory(self, dir_path: str) -> int:
        """Index all supported files in a directory tree. Returns chunk count."""
        root = Path(dir_path).resolve()
        if not root.exists():
            return 0

        files = [f for f in root.rglob("*") if f.suffix.lower() in self.SUPPORTED_SUFFIXES]
        if not files:
            return 0

        all_chunks: list[str] = []
        all_metas: list[dict] = []

        for fp in files:
            try:
                if fp.suffix.lower() == ".pdf":
                    from pypdf import PdfReader

                    reader = PdfReader(str(fp))
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
                else:
                    text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            chunks = _chunk_text(text)
            rel = str(fp.relative_to(root))
            for i, ch in enumerate(chunks):
                all_chunks.append(ch)
                all_metas.append({"source": rel, "chunk_index": i})

        if not all_chunks:
            return 0

        # Build FAISS index
        vecs = _embed(all_chunks)  # documents: no query prefix
        dim = vecs.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(vecs)
        self._docs = all_chunks
        self._metas = all_metas
        self._build_bm25()
        self._save()

        _logger.info("faiss indexed", extra={"chunks": len(all_chunks), "files": len(files)})
        return len(all_chunks)

    # ------------------------------------------------------------------
    # BM25 keyword index
    # ------------------------------------------------------------------

    def _build_bm25(self) -> None:
        """Rebuild BM25 index from current chunks (jieba-tokenized)."""
        if not self._docs:
            self._bm25 = None
            return
        tokenized = [_tokenize(doc) for doc in self._docs]
        self._bm25 = BM25Okapi(tokenized)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, k: int | None = None) -> str:
        """Hybrid search (vector + BM25, RRF-fused), return formatted results."""
        hits = self.search_hybrid(query, k=k)
        if not hits:
            return "No relevant documents found."

        lines: list[str] = []
        for idx, score in hits:
            doc = self._docs[idx] if idx < len(self._docs) else "(missing)"
            meta = self._metas[idx] if idx < len(self._metas) else {}
            src = meta.get("source", "unknown")
            lines.append(f"--- [{src}] (score={score:.3f}) ---\n{doc}")

        return "\n\n".join(lines)

    def search_hybrid(
        self,
        query: str,
        k: int | None = None,
        vector_k: int | None = None,
        bm25_k: int | None = None,
    ) -> list[tuple[int, float]]:
        """Hybrid search: FAISS vector top-N + BM25 keyword top-N, merged by RRF.

        RRF (Reciprocal Rank Fusion): score(idx) = Σ 1 / (K + rank), K=60.
        Each retriever contributes only its *rank*, not its raw score, so the
        merge is robust to the two retrievers having incompatible score scales
        (cosine similarity vs BM25 term-frequency scores).

        保底规则（2026-08-18）: 任一路 rank ≤ RAG_RERANK_TOP_PASS 的 chunk
        获得大额 boost —— 修复 RRF 固有缺陷"双路平庸 > 单路极强"
        （单路 rank=1 的 chunk 得 1/61=0.0164, 会被 v=2/b=3 的 0.0317 挤掉）。

        候选池随后经 cross-encoder rerank（bge-reranker-base, CPU）重排,
        模型缺失/失败时自动保持 RRF 顺序（降级为纯 RRF 行为）。

        Falls back to pure vector search when the BM25 index is unavailable.

        参数默认值来自 backend.config（RAG_TOP_K / RAG_VECTOR_K / RAG_BM25_K /
        RAG_RERANK_*），调参实验只需改环境变量或 .env，不用改代码。
        """
        if k is None:
            k = RAG_TOP_K
        if vector_k is None:
            vector_k = RAG_VECTOR_K
        if bm25_k is None:
            bm25_k = RAG_BM25_K

        if self._index is None or self._index.ntotal == 0:
            return []
        if self._bm25 is None:
            return self.search_indices(query, k)

        # 1. Vector top-N (rank starts at 1)
        q_vec = _embed_query(query)
        distances, indices = self._index.search(q_vec, min(vector_k, self._index.ntotal))
        vector_hits = [(int(idx), rank) for rank, idx in enumerate(indices[0], start=1) if idx >= 0]

        # 2. BM25 top-N (rank starts at 1; zero-score hits carry no signal)
        bm25_scores = self._bm25.get_scores(_tokenize(query))
        order = np.argsort(bm25_scores)[::-1][:bm25_k]
        bm25_hits = [(int(idx), rank) for rank, idx in enumerate(order, start=1) if bm25_scores[idx] > 0]

        # 3. RRF fusion + 单路强信号保底 boost
        top_pass = RAG_RERANK_TOP_PASS
        fused: dict[int, float] = {}
        for idx, rank in [*vector_hits, *bm25_hits]:
            boost = 10.0 if rank <= top_pass else 0.0  # 远大于任何 RRF 差值
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (60.0 + rank) + boost
        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)

        # 4. Cross-encoder rerank（候选池重排; 失败自动保持 RRF 顺序）
        if RAG_RERANK_ENABLED:
            from backend.agent.reranker import rerank

            candidates = ranked[:RAG_RERANK_CANDIDATES]
            pairs = [(idx, self._docs[idx]) for idx, _ in candidates if idx < len(self._docs)]
            reranked = rerank(query, pairs)
            if reranked:
                return reranked[:k]
        return ranked[:k]

    def search_indices(self, query: str, k: int | None = None) -> list[tuple[int, float]]:
        """Return raw (chunk_index, similarity) pairs for eval / hybrid retrieval.

        Unlike search(), this returns index positions instead of formatted text,
        so callers can compute metrics (Recall@k, MRR) or merge with BM25 results.
        Applies the same 0.3 similarity floor as search() for realism.
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        if k is None:
            k = RAG_TOP_K

        q_vec = _embed_query(query)
        distances, indices = self._index.search(q_vec, min(k, self._index.ntotal))
        return [
            (int(idx), float(sim)) for idx, sim in zip(indices[0], distances[0], strict=True) if idx >= 0 and sim >= 0.3
        ]

    @property
    def chunk_count(self) -> int:
        return self._index.ntotal if self._index else 0

    def clear(self) -> None:
        self._index = None
        self._docs = []
        self._metas = []
        self._bm25 = None
        if self._index_path.exists():
            self._index_path.unlink()
        if self._meta_path.exists():
            self._meta_path.unlink()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

knowledge_base = KnowledgeBase()
