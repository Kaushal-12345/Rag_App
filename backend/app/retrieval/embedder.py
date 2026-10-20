"""Embedding interface and sentence-transformers implementation."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from app.config import Settings

logger = logging.getLogger(__name__)

# Official query instruction for BAAI/bge-small-en-v1.5
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@runtime_checkable
class Embedder(Protocol):
    """Produces dense vectors for documents and queries."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document chunks."""

    def embed_query(self, text: str) -> list[float]:
        """Embed a user query (may apply a model-specific prefix)."""


class SentenceTransformerEmbedder:
    """CPU embeddings via sentence-transformers. Model is loaded lazily."""

    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.embedding_model
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model %s on CPU", self._model_name)
            self._model = SentenceTransformer(self._model_name, device="cpu")
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        prefixed = f"{BGE_QUERY_PREFIX}{text}"
        return self.embed([prefixed])[0]
