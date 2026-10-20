"""Token-aware chunking that preserves source metadata."""

from __future__ import annotations

import re
from typing import Iterable

from app.schemas.documents import Chunk, PageDocument

_TOKEN_RE = re.compile(r"\S+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def count_tokens(text: str) -> int:
    """Approximate token count as whitespace-separated words.

    This keeps the chunker dependency-free and deterministic in tests.
    """
    return len(_TOKEN_RE.findall(text))


def tokenize(text: str) -> list[str]:
    """Split text into whitespace-separated tokens, preserving punctuation."""
    return _TOKEN_RE.findall(text)


def chunk_pages(
    pages: Iterable[PageDocument],
    *,
    chunk_size: int = 600,
    overlap: int = 100,
) -> list[Chunk]:
    """Split each page into overlapping chunks of about `chunk_size` tokens.

    Pages are chunked independently so every chunk keeps a single page number
    for citations. Overlap applies only within a page.

    Raises:
        ValueError: If sizes are invalid.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[Chunk] = []
    global_index = 0
    for page in pages:
        page_chunks = _chunk_text(page.text, chunk_size=chunk_size, overlap=overlap)
        for local_index, text in enumerate(page_chunks):
            chunks.append(
                Chunk(
                    text=text,
                    metadata={
                        "source": page.source,
                        "page": page.page,
                        "source_id": page.source_id,
                        "session_id": page.session_id,
                        "chunk_index": global_index,
                        "page_chunk_index": local_index,
                    },
                )
            )
            global_index += 1
    return chunks


def _chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []

    sentences = [part.strip() for part in _SENTENCE_RE.split(stripped) if part.strip()]
    if not sentences:
        sentences = [stripped]

    packed: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current, current_tokens
        if current:
            packed.append(current)
            current = []
            current_tokens = 0

    for sentence in sentences:
        sentence_tokens = tokenize(sentence)
        if len(sentence_tokens) > chunk_size:
            flush()
            packed.extend(_split_long_tokens(sentence_tokens, chunk_size=chunk_size, overlap=overlap))
            continue

        if current_tokens + len(sentence_tokens) > chunk_size and current:
            flush()
        current.extend(sentence_tokens)
        current_tokens += len(sentence_tokens)

    flush()
    overlapped = _apply_overlap(packed, overlap=overlap)
    return [" ".join(tokens) for tokens in overlapped if tokens]


def _split_long_tokens(tokens: list[str], *, chunk_size: int, overlap: int) -> list[list[str]]:
    """Split an oversized sentence into contiguous windows.

    Overlap is applied later by `_apply_overlap`, so windows here do not overlap.
    """
    del overlap  # overlap is handled centrally
    pieces: list[list[str]] = []
    start = 0
    while start < len(tokens):
        pieces.append(tokens[start : start + chunk_size])
        start += chunk_size
    return pieces


def _apply_overlap(packed: list[list[str]], *, overlap: int) -> list[list[str]]:
    if overlap == 0 or len(packed) <= 1:
        return packed
    result: list[list[str]] = [packed[0]]
    for index in range(1, len(packed)):
        previous = result[-1]
        prefix = previous[-overlap:] if overlap <= len(previous) else previous
        merged = prefix + packed[index]
        result.append(merged)
    return result
