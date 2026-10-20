"""Optional cross-encoder reranking (enabled with RERANK_ENABLED=true)."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from app.schemas.documents import RetrievedChunk

logger = logging.getLogger(__name__)


@runtime_checkable
class Reranker(Protocol):
    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        """Return the `top_k` most relevant chunks, best first."""


class CrossEncoderReranker:
    """Scores (query, passage) pairs with a small cross-encoder. Loaded lazily."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading reranker %s on CPU", self._model_name)
            self._model = CrossEncoder(self._model_name, device="cpu")
        return self._model

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        if len(chunks) <= 1:
            return chunks[:top_k]
        model = self._load()
        scores = model.predict([(query, chunk.text) for chunk in chunks])
        ranked = sorted(zip(chunks, scores, strict=True), key=lambda pair: float(pair[1]), reverse=True)
        return [
            chunk.model_copy(update={"score": float(score)}) for chunk, score in ranked[:top_k]
        ]
