"""RAG knowledge base — FAISS vector index (per PRD).

Loads docs, chunks them, indexes with FAISS IndexFlatIP.
Uses Chroma's bundled ONNX embedding (all-MiniLM-L6-v2, 384-dim).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import faiss
import numpy as np
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


# ---------------------------------------------------------------------------
# Embedding — reuses Chroma's bundled ONNX model (all-MiniLM-L6-v2, 384-dim)
# ---------------------------------------------------------------------------

_EMBED_FN: DefaultEmbeddingFunction | None = None


def _embed_fn() -> DefaultEmbeddingFunction:
    global _EMBED_FN
    if _EMBED_FN is None:
        _EMBED_FN = DefaultEmbeddingFunction()
    return _EMBED_FN


def _embed(texts: list[str]) -> np.ndarray:
    """Embed texts into 384-dim L2-normalized vectors via Chroma's ONNX model."""
    fn = _embed_fn()
    vecs = fn(texts)
    arr = np.array(vecs, dtype=np.float32)
    # L2-normalize for cosine similarity via inner product
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms  # type: ignore[no-any-return]


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
    max_chunks = 500

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
        start = end - overlap
    return chunks


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
        self._docs: list[str] = []       # aligned with index rows
        self._metas: list[dict] = []     # metadata per chunk

        if self._index_path.exists():
            self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            self._index = faiss.read_index(str(self._index_path))
            with open(self._meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._docs = data.get("docs", [])
            self._metas = data.get("metas", [])
        except Exception:
            self._index = None
            self._docs = []
            self._metas = []

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
                    text = "\n".join(
                        page.extract_text() or "" for page in reader.pages
                    )
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
        vecs = _embed(all_chunks)
        dim = vecs.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(vecs)
        self._docs = all_chunks
        self._metas = all_metas
        self._save()

        print(f"[RAG] FAISS indexed {len(all_chunks)} chunks from {len(files)} files")
        return len(all_chunks)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, k: int = 4) -> str:
        """Search FAISS index, return formatted results."""
        if self._index is None or self._index.ntotal == 0:
            return "(knowledge base is empty)"

        q_vec = _embed([query])
        distances, indices = self._index.search(q_vec, min(k, self._index.ntotal))

        lines: list[str] = []
        for i in range(len(indices[0])):
            idx = indices[0][i]
            sim = float(distances[0][i])  # cosine similarity (0..1)
            if sim < 0.3:
                continue
            doc = self._docs[idx] if idx < len(self._docs) else "(missing)"
            meta = self._metas[idx] if idx < len(self._metas) else {}
            src = meta.get("source", "unknown")
            lines.append(f"--- [{src}] (cos={sim:.3f}) ---\n{doc}")

        return "\n\n".join(lines) if lines else "No relevant documents found."

    @property
    def chunk_count(self) -> int:
        return self._index.ntotal if self._index else 0

    def clear(self) -> None:
        self._index = None
        self._docs = []
        self._metas = []
        if self._index_path.exists():
            self._index_path.unlink()
        if self._meta_path.exists():
            self._meta_path.unlink()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

knowledge_base = KnowledgeBase()
