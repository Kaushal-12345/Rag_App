"""Ingest pipelines: PDF and YouTube → chunk → embed → index."""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import Settings
from app.ingestion.chunker import chunk_pages
from app.ingestion.pdf_loader import load_pdf
from app.ingestion.youtube_loader import fetch_title, fetch_windows, timestamp_url
from app.retrieval.embedder import Embedder
from app.retrieval.vector_store import VectorStore
from app.schemas.api import IngestResponse
from app.schemas.documents import Chunk
from app.utils.ids import collection_name, new_id

logger = logging.getLogger(__name__)


class IngestPipeline:
    """Coordinates ingestion into a per-session vector collection."""

    def __init__(
        self,
        *,
        settings: Settings,
        embedder: Embedder,
        vector_store: VectorStore,
    ) -> None:
        self._settings = settings
        self._embedder = embedder
        self._vector_store = vector_store

    def ingest_pdf(
        self,
        path: Path,
        *,
        filename: str,
        session_id: str | None = None,
    ) -> IngestResponse:
        """Index a PDF into a session collection and return ingest stats."""
        session = session_id or new_id()
        source_id = new_id()
        pages = load_pdf(
            path,
            source=filename,
            source_id=source_id,
            session_id=session,
            ocr=self._settings.ocr_enabled,
        )
        chunks = chunk_pages(
            pages,
            chunk_size=self._settings.chunk_size_tokens,
            overlap=self._settings.chunk_overlap_tokens,
        )
        if not chunks:
            raise ValueError(
                "No extractable text found in this PDF. It looks like a scan, and OCR "
                "isn't available (install Tesseract: `brew install tesseract`)."
            )
        for chunk in chunks:
            chunk.metadata["source_type"] = "pdf"

        self._index(session, source_id, chunks)
        logger.info(
            "Indexed session=%s source=%s pages=%s chunks=%s",
            session,
            filename,
            len(pages),
            len(chunks),
        )
        return IngestResponse(
            session_id=session,
            source_id=source_id,
            filename=filename,
            pages=len(pages),
            chunks=len(chunks),
        )

    def ingest_youtube(
        self,
        url: str,
        *,
        session_id: str | None = None,
    ) -> IngestResponse:
        """Fetch a video transcript and index it with timestamp metadata."""
        session = session_id or new_id()
        source_id = new_id()
        video_id, windows = fetch_windows(
            url,
            whisper_fallback=self._settings.whisper_fallback,
            whisper_model=self._settings.whisper_model,
        )
        title = fetch_title(video_id) or f"YouTube video {video_id}"

        chunks = [
            Chunk(
                text=window.text,
                metadata={
                    "source": title,
                    "source_type": "youtube",
                    "source_id": source_id,
                    "session_id": session,
                    "video_id": video_id,
                    "start_seconds": window.start,
                    "end_seconds": window.end,
                    "url": timestamp_url(video_id, window.start),
                    "chunk_index": index,
                },
            )
            for index, window in enumerate(windows)
        ]

        self._index(session, source_id, chunks)
        logger.info("Indexed session=%s video=%s chunks=%s", session, video_id, len(chunks))
        return IngestResponse(
            session_id=session,
            source_id=source_id,
            filename=title,
            chunks=len(chunks),
            source_type="youtube",
            url=f"https://www.youtube.com/watch?v={video_id}",
        )

    def _index(self, session: str, source_id: str, chunks: list[Chunk]) -> None:
        texts = [chunk.text for chunk in chunks]
        embeddings = self._embedder.embed(texts)
        ids = [f"{source_id}_{index}" for index in range(len(chunks))]
        self._vector_store.upsert(
            collection=collection_name(session),
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=[chunk.metadata for chunk in chunks],
        )
