"""Internal document and chunk representations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PageDocument(BaseModel):
    """Extracted page of a PDF."""

    source: str
    page: int = Field(ge=1)
    text: str
    source_id: str
    session_id: str


class Chunk(BaseModel):
    """Text chunk ready for embedding, with citation metadata."""

    text: str
    metadata: dict[str, Any]


class RetrievedChunk(BaseModel):
    """A chunk returned from the vector store."""

    text: str
    metadata: dict[str, Any]
    score: float
    id: str
