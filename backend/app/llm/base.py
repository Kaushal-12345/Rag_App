"""LLM client protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

# A chat turn: {"role": "user" | "assistant", "content": "..."}
HistoryItem = dict[str, str]


@runtime_checkable
class LLMClient(Protocol):
    """Completion interface used by the RAG service."""

    async def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        history: list[HistoryItem] | None = None,
    ) -> str:
        """Return a full (non-streaming) model completion."""

    def stream(
        self,
        *,
        system: str,
        user: str,
        model: str,
        history: list[HistoryItem] | None = None,
    ) -> AsyncIterator[str]:
        """Yield answer text pieces as the model produces them."""
