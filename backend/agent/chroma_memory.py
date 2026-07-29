"""Chroma-based long-term memory for conversation history.

Phase 4 Step 3: Replaces the need for manual memory retrieval by storing
conversation turns as embeddings and retrieving semantically relevant
context for each new query.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

# ---------------------------------------------------------------------------
# ChromaMemory — singleton service
# ---------------------------------------------------------------------------


class ChromaMemory:
    """Stores and retrieves conversation turns via Chroma vector DB.

    Each turn is embedded as a single document and can be retrieved by
    semantic similarity to the current user query.
    """

    def __init__(self, persist_dir: str = "./chroma_data") -> None:
        self._persist_dir = str(Path(persist_dir).resolve())
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._embed_fn = embedding_functions.DefaultEmbeddingFunction()
        self._collection = self._client.get_or_create_collection(
            name="ruoxue_conversations",
            embedding_function=self._embed_fn,  # type: ignore[arg-type]
            metadata={"description": "Ruoxue conversation history"},
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def store_turn(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """Embed and persist one conversation turn."""
        doc = f"用户: {user_text}\n若雪: {assistant_text}"
        turn_id = str(uuid.uuid4())
        try:
            self._collection.add(
                documents=[doc],
                metadatas=[
                    {
                        "session_id": session_id,
                        "user_text": user_text[:500],
                        "assistant_text": assistant_text[:500],
                        "stored_at": datetime.now(UTC).isoformat(),
                    }
                ],
                ids=[turn_id],
            )
        except Exception as exc:
            print(f"[Chroma] store failed: {exc}")

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def retrieve_context(self, query: str, k: int = 3) -> str:
        """Return relevant past conversation turns as a formatted string.

        Args:
            query: The current user message to search against.
            k: Number of top results to return.

        Returns:
            Formatted string of past turns, or empty string if nothing found.
        """
        count = self._collection.count()
        if count == 0:
            return ""

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(k, count),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            print(f"[Chroma] query failed: {exc}")
            return ""

        docs = results.get("documents")
        metas = results.get("metadatas")
        dists = results.get("distances")

        if not docs or not docs[0]:
            return ""

        lines: list[str] = []
        for i, doc in enumerate(docs[0]):
            dist = dists[0][i] if dists and dists[0] else 999
            # Cosine distance: 0 = identical, 2 = opposite. Lower is better.
            if dist < 1.5:
                lines.append(f"--- (distance: {dist:.3f}) ---\n{doc}")
        return "\n\n".join(lines) if lines else ""

    @property
    def turn_count(self) -> int:
        """Total stored turns."""
        return self._collection.count()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

chroma_memory = ChromaMemory()
