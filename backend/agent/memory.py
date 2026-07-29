"""In-memory conversation history with sliding window.

Phase 1: simple dict-based storage with max turn limit.
Phase 4: upgrade to Chroma vector store for long-term memory.
"""

from __future__ import annotations

from collections import defaultdict

from backend.config import MAX_HISTORY_TURNS


class ConversationMemory:
    """Stores recent conversation turns in memory.

    Each turn = one user message + one assistant reply.
    Format compatible with LangChain MessagesPlaceholder.
    """

    def __init__(self, max_turns: int = MAX_HISTORY_TURNS) -> None:
        self._store: dict[str, list[dict]] = defaultdict(list)
        self._max_turns = max_turns

    def add_user_message(self, session_id: str, text: str) -> None:
        """Record a user message."""
        self._store[session_id].append({"role": "user", "content": text})

    def add_assistant_message(self, session_id: str, text: str) -> None:
        """Record an assistant reply."""
        self._store[session_id].append({"role": "assistant", "content": text})

    def get_history(self, session_id: str) -> list[dict]:
        """Get conversation history for a session.

        Returns the most recent turns, limited to max_turns * 2 messages
        (one user + one assistant per turn).
        """
        messages = self._store[session_id]
        max_messages = self._max_turns * 2
        return messages[-max_messages:] if len(messages) > max_messages else messages

    def clear(self, session_id: str) -> None:
        """Clear history for a session."""
        self._store.pop(session_id, None)

    def get_turn_count(self, session_id: str) -> int:
        """Return number of completed turns (assistant messages)."""
        return sum(1 for m in self._store[session_id] if m["role"] == "assistant")


# Global singleton
memory = ConversationMemory()
