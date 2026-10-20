"""Vector store interface plus a persistent Chroma implementation."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.schemas.documents import RetrievedChunk

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    """Backend-agnostic vector index. Qdrant can replace Chroma later."""

    @abstractmethod
    def upsert(
        self,
        *,
        collection: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Insert or update vectors in a named collection."""

    @abstractmethod
    def query(
        self,
        *,
        collection: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Return the nearest neighbors for a query embedding."""

    @abstractmethod
    def collection_exists(self, collection: str) -> bool:
        """Whether a collection has been created."""

    @abstractmethod
    def delete_collection(self, collection: str) -> None:
        """Drop a collection if it exists."""

    @abstractmethod
    def list_sources(self, collection: str) -> list[dict[str, Any]]:
        """Summarise the documents in a collection (one dict per source_id)."""

    @abstractmethod
    def delete_source(self, collection: str, source_id: str) -> int:
        """Delete every chunk of one source. Returns the number of chunks removed."""


class ChromaVectorStore(VectorStore):
    """Persistent ChromaDB store. One collection per session."""

    def __init__(self, persist_path: Path) -> None:
        import chromadb

        persist_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist_path))

    def upsert(
        self,
        *,
        collection: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not (len(ids) == len(documents) == len(embeddings) == len(metadatas)):
            raise ValueError("ids, documents, embeddings, and metadatas must be the same length")
        coll = self._client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )
        coll.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.debug("Upserted %s vectors into %s", len(ids), collection)

    def query(
        self,
        *,
        collection: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if not self.collection_exists(collection):
            return []
        coll = self._client.get_collection(collection)
        count = coll.count()
        if count == 0:
            return []
        n_results = min(top_k, count)
        raw = coll.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        results: list[RetrievedChunk] = []
        for item_id, text, metadata, distance in zip(ids, documents, metadatas, distances, strict=True):
            score = 1.0 - float(distance)
            results.append(
                RetrievedChunk(
                    id=item_id,
                    text=text or "",
                    metadata=dict(metadata or {}),
                    score=score,
                )
            )
        return results

    def collection_exists(self, collection: str) -> bool:
        names: set[str] = set()
        for item in self._client.list_collections():
            name = item if isinstance(item, str) else getattr(item, "name", None)
            if name:
                names.add(name)
        return collection in names

    def delete_collection(self, collection: str) -> None:
        if self.collection_exists(collection):
            self._client.delete_collection(collection)
            logger.info("Deleted collection %s", collection)

    def list_sources(self, collection: str) -> list[dict[str, Any]]:
        if not self.collection_exists(collection):
            return []
        coll = self._client.get_collection(collection)
        raw = coll.get(include=["metadatas"])
        summary: dict[str, dict[str, Any]] = {}
        for metadata in raw.get("metadatas") or []:
            meta = dict(metadata or {})
            source_id = str(meta.get("source_id") or "unknown")
            entry = summary.setdefault(
                source_id,
                {
                    "source_id": source_id,
                    "source": str(meta.get("source", "unknown")),
                    "source_type": str(meta.get("source_type", "pdf")),
                    "chunks": 0,
                    "url": None,
                },
            )
            entry["chunks"] += 1
            if meta.get("video_id") and not entry["url"]:
                entry["url"] = f"https://www.youtube.com/watch?v={meta['video_id']}"
        return sorted(summary.values(), key=lambda item: item["source"].lower())

    def delete_source(self, collection: str, source_id: str) -> int:
        if not self.collection_exists(collection):
            return 0
        coll = self._client.get_collection(collection)
        existing = coll.get(where={"source_id": source_id}, include=[])
        ids = existing.get("ids") or []
        if ids:
            coll.delete(ids=ids)
        return len(ids)
