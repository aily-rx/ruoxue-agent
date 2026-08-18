"""Cross-encoder reranker — bge-reranker-base (Chinese-capable).

Reranks the RRF-fused candidate pool by pairwise (query, doc) relevance
scores, fixing the RRF weakness where a chunk ranked #1 by one retriever
loses to chunks that merely appear in both lists (single-strong vs
double-mediocre, see text/rag/rag-eval.md §五).

- Model: BAAI/bge-reranker-base, expected at
  model_assets/rerankers/bge-reranker-base/ (gitignored, lazy-loaded).
- Missing model → graceful fallback: caller keeps the RRF order
  (identical behavior to pre-rerank builds).
- CPU inference: ~20 pairs ≈ 200-500ms; LRU-cached per query.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np

_logger = logging.getLogger("agent.reranker")

_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "model_assets" / "rerankers" / "bge-reranker-base"

_model = None  # lazy (tokenizer, model)
_ready: bool | None = None  # None = not yet probed


def available() -> bool:
    """True when the reranker model is present on disk (probed once)."""
    global _ready
    if _ready is None:
        _ready = (_MODEL_DIR / "config.json").exists() and (_MODEL_DIR / "model.safetensors").exists()
        if not _ready:
            _logger.warning("reranker model missing at %s — keeping RRF order", _MODEL_DIR)
    return _ready


def _load() -> tuple:
    """Lazily load tokenizer + model (CPU). Returns (tokenizer, model)."""
    global _model
    if _model is None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(str(_MODEL_DIR))
        model = AutoModelForSequenceClassification.from_pretrained(str(_MODEL_DIR))
        model.eval()
        _model = (tokenizer, model)
    return _model


@lru_cache(maxsize=512)
def _rerank_cached(query: str, doc_texts: tuple[str, ...]) -> tuple[float, ...]:
    """Rerank a cached (query, docs) pair — identical queries skip inference."""
    if not doc_texts:
        return ()
    import torch

    tokenizer, model = _load()
    pairs = [(query, doc) for doc in doc_texts]
    with torch.no_grad():
        # max_length: 512 vs 256 实测差 1 题（R@1 0.620→0.600, 见 rag-eval.md §五）
        inputs = tokenizer(pairs, padding=True, truncation=True, max_length=512, return_tensors="pt")
        # sigmoid: raw logits 可为负, 归一为相关性概率 (0,1) — 保持调用方 score>0 契约
        scores = torch.sigmoid(model(**inputs).logits.flatten()).numpy().astype(np.float64)
    return tuple(float(s) for s in scores)


def rerank(query: str, candidates: list[tuple[int, str]]) -> list[tuple[int, float]]:
    """Score candidate (chunk_index, doc_text) pairs, return sorted desc by score.

    Returns [] when the model is unavailable — callers should keep the
    original (RRF) ordering as a fallback.
    """
    if not candidates:
        return []
    if not available():
        return []  # 降级: 调用方保持 RRF 顺序
    try:
        texts = tuple(doc for _, doc in candidates)
        scores = _rerank_cached(query, texts)
        scored = [(idx, float(s)) for (idx, _), s in zip(candidates, scores, strict=True)]
        return sorted(scored, key=lambda kv: kv[1], reverse=True)
    except Exception:
        _logger.exception("rerank failed — keeping RRF order")
        return []
