"""Prompt templates for grounded RAG answers."""

from __future__ import annotations

from app.retrieval.web_search import WebResult
from app.schemas.documents import RetrievedChunk

SYSTEM_PROMPT = """You are a careful question-answering assistant.

You may be given two kinds of context, always labelled:
- DOCUMENT CONTEXT: passages from the user's uploaded PDFs or YouTube videos.
- WEB CONTEXT: live web search results (only present when the user enabled web search).

Rules:
1. Prefer DOCUMENT CONTEXT for anything about the user's documents or videos.
2. Use WEB CONTEXT only for facts outside the documents, and say when you did.
3. If the available context does not contain the answer, say so plainly. Never guess.
4. Never invent facts, quotes, or citations.
5. Cite what you use: [file name, p. N] for PDF pages, [video title @ mm:ss] for videos,
   and [web: site title] for web results. Use the exact names shown in the context.
6. Be concise and well organised. Plain markdown is fine.
"""


def format_timestamp(seconds: float) -> str:
    """Seconds → m:ss or h:mm:ss."""
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _label(chunk: RetrievedChunk) -> str:
    meta = chunk.metadata
    source = meta.get("source", "unknown")
    if meta.get("source_type") == "youtube" and meta.get("start_seconds") is not None:
        return f"video={source} @ {format_timestamp(float(meta['start_seconds']))}"
    return f"file={source} page={meta.get('page', '?')}"


def build_user_prompt(
    question: str,
    chunks: list[RetrievedChunk],
    web_results: list[WebResult] | None = None,
) -> str:
    """Assemble the user message with clearly separated context sections."""
    parts = ["DOCUMENT CONTEXT:"]
    if not chunks:
        parts.append("(no matching passages)")
    for index, chunk in enumerate(chunks, start=1):
        parts.append(f"[{index}] {_label(chunk)}\n{chunk.text}")

    if web_results is not None:
        parts.append("WEB CONTEXT:")
        if not web_results:
            parts.append("(web search returned nothing)")
        for index, result in enumerate(web_results, start=1):
            parts.append(f"[w{index}] web: {result.title} ({result.url})\n{result.content}")

    parts.append(f"QUESTION:\n{question}")
    parts.append("ANSWER:")
    return "\n\n".join(parts)
