"""HTTP request and response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    session_id: str
    source_id: str
    filename: str
    pages: int = 0
    chunks: int
    source_type: str = "pdf"
    url: str | None = None


class YouTubeIngestRequest(BaseModel):
    url: str = Field(min_length=5)
    session_id: str | None = None


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=50)
    model: str | None = None
    web_search: bool = False
    history: list[HistoryMessage] = Field(default_factory=list)


class CompareRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=50)
    web_search: bool = False
    history: list[HistoryMessage] = Field(default_factory=list)


class Citation(BaseModel):
    source: str
    page: int | None = None
    source_id: str | None = None
    chunk_id: str | None = None
    score: float | None = None
    snippet: str | None = None
    source_type: str = "pdf"  # "pdf" | "youtube" | "web"
    start_seconds: float | None = None
    url: str | None = None


class ChatResponse(BaseModel):
    answer: str
    model: str
    sources: list[Citation]
    session_id: str
    web_used: bool = False


class SourceInfo(BaseModel):
    source_id: str
    source: str
    source_type: str
    chunks: int
    url: str | None = None


class SourcesResponse(BaseModel):
    session_id: str
    sources: list[SourceInfo]


class ModelsResponse(BaseModel):
    models: list[str]
    default: str
    web_search_available: bool
