"""Test doubles and PDF fixtures."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pymupdf as fitz


class FakeEmbedder:
    """Deterministic bag-of-tokens embedder for unit tests."""

    dim = 32

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            index = int(digest, 16) % self.dim
            vec[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vec)) or 1.0
        return [value / norm for value in vec]


def make_pdf(path: Path, pages: list[str]) -> Path:
    """Write a simple multi-page PDF for loader tests."""
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path


class FakeLLM:
    """Deterministic LLM: answers by echoing the model name, streams word by word."""

    def __init__(self, fail_models: set[str] | None = None) -> None:
        self.fail_models = fail_models or set()
        self.calls: list[dict] = []

    async def complete(self, *, system, user, model, history=None) -> str:
        from app.llm.providers import LLMError

        self.calls.append({"model": model, "user": user, "history": history or []})
        if model in self.fail_models:
            raise LLMError("boom")
        return f"answer from {model}"

    async def stream(self, *, system, user, model, history=None):
        from app.llm.providers import LLMError

        self.calls.append({"model": model, "user": user, "history": history or []})
        if model in self.fail_models:
            raise LLMError("boom")
        for word in f"answer from {model}".split(" "):
            yield word + " "


class FakeWebSearcher:
    def __init__(self, results=None) -> None:
        self.results = results or []
        self.queries: list[str] = []

    async def search(self, query: str):
        self.queries.append(query)
        return self.results
