"""Retrieve → (optional web search) → prompt → generate, with citations."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.llm.base import HistoryItem, LLMClient
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.llm.providers import LLMError
from app.retrieval.embedder import Embedder
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStore
from app.retrieval.web_search import WebResult, WebSearcher
from app.schemas.api import ChatResponse, Citation, HistoryMessage
from app.schemas.documents import RetrievedChunk
from app.utils.ids import collection_name

logger = logging.getLogger(__name__)

_HISTORY_CHAR_LIMIT = 1500


@dataclass
class PreparedQuery:
    """Everything the LLM needs, computed once (shared by compare mode)."""

    user_prompt: str
    history: list[HistoryItem]
    sources: list[Citation]
    web_used: bool


class RagService:
    """RAG query service: single answer, token streaming, and 3-model compare."""

    def __init__(
        self,
        *,
        settings: Settings,
        embedder: Embedder,
        vector_store: VectorStore,
        llm: LLMClient,
        web_searcher: WebSearcher | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self._settings = settings
        self._embedder = embedder
        self._vector_store = vector_store
        self._llm = llm
        self._web = web_searcher
        self._reranker = reranker

    # ---------------------------------------------------------------- shared
    async def prepare(
        self,
        *,
        session_id: str,
        question: str,
        top_k: int | None = None,
        web_search: bool = False,
        history: list[HistoryMessage] | None = None,
    ) -> PreparedQuery:
        collection = collection_name(session_id)
        if not self._vector_store.collection_exists(collection):
            raise FileNotFoundError(
                "No indexed documents for this session. Upload a PDF or YouTube link first."
            )

        k = top_k or self._settings.retrieve_top_k
        use_rerank = self._reranker is not None and self._settings.rerank_enabled
        fetch_k = k * self._settings.rerank_candidate_multiplier if use_rerank else k

        query_embedding = await asyncio.to_thread(self._embedder.embed_query, question)
        chunks = await asyncio.to_thread(
            lambda: self._vector_store.query(
                collection=collection, query_embedding=query_embedding, top_k=fetch_k
            )
        )
        if use_rerank and chunks:
            chunks = await asyncio.to_thread(self._reranker.rerank, question, chunks, k)  # type: ignore[union-attr]
        logger.info("Retrieved %s chunk(s) for session=%s", len(chunks), session_id)

        web_results: list[WebResult] | None = None
        if web_search and self._web is not None:
            web_results = await self._web.search(question)

        sources = _citations_from_chunks(chunks)
        sources.extend(_citations_from_web(web_results or []))
        return PreparedQuery(
            user_prompt=build_user_prompt(question, chunks, web_results),
            history=self._trim_history(history),
            sources=sources,
            web_used=web_results is not None,
        )

    def _trim_history(self, history: list[HistoryMessage] | None) -> list[HistoryItem]:
        limit = self._settings.max_history_messages
        if not history or limit == 0:
            return []
        return [
            {"role": item.role, "content": item.content[:_HISTORY_CHAR_LIMIT]}
            for item in history[-limit:]
            if item.content.strip()
        ]

    # ------------------------------------------------------------ single reply
    async def chat(
        self,
        *,
        session_id: str,
        question: str,
        top_k: int | None = None,
        model: str | None = None,
        web_search: bool = False,
        history: list[HistoryMessage] | None = None,
    ) -> ChatResponse:
        """Answer a question using chunks retrieved for this session."""
        prepared = await self.prepare(
            session_id=session_id,
            question=question,
            top_k=top_k,
            web_search=web_search,
            history=history,
        )
        resolved_model = self._settings.resolved_model(model)
        answer = await self._llm.complete(
            system=SYSTEM_PROMPT,
            user=prepared.user_prompt,
            model=resolved_model,
            history=prepared.history,
        )
        return ChatResponse(
            answer=answer,
            model=resolved_model,
            sources=prepared.sources,
            session_id=session_id,
            web_used=prepared.web_used,
        )

    # --------------------------------------------------------------- streaming
    async def stream_events(
        self,
        *,
        session_id: str,
        question: str,
        top_k: int | None = None,
        model: str | None = None,
        web_search: bool = False,
        history: list[HistoryMessage] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield events: meta → token* → done (or error). Retrieval errors raise early."""
        prepared = await self.prepare(
            session_id=session_id,
            question=question,
            top_k=top_k,
            web_search=web_search,
            history=history,
        )
        resolved = self._settings.resolved_model(model)
        async for event in self._stream_model(resolved, prepared, include_meta=True):
            yield event

    async def compare_events(
        self,
        *,
        session_id: str,
        question: str,
        top_k: int | None = None,
        web_search: bool = False,
        history: list[HistoryMessage] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream all three models in parallel; every event is tagged with its model."""
        prepared = await self.prepare(
            session_id=session_id,
            question=question,
            top_k=top_k,
            web_search=web_search,
            history=history,
        )
        models = list(dict.fromkeys(self._settings.llm_models))  # unique, ordered
        yield {
            "type": "meta",
            "models": models,
            "sources": [c.model_dump() for c in prepared.sources],
            "web_used": prepared.web_used,
        }

        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def worker(model_name: str) -> None:
            try:
                async for event in self._stream_model(model_name, prepared, include_meta=False):
                    await queue.put(event)
            finally:
                await queue.put(None)  # this worker is finished

        tasks = [asyncio.create_task(worker(name)) for name in models]
        finished = 0
        try:
            while finished < len(tasks):
                item = await queue.get()
                if item is None:
                    finished += 1
                else:
                    yield item
        finally:
            for task in tasks:
                task.cancel()

    async def _stream_model(
        self,
        model: str,
        prepared: PreparedQuery,
        *,
        include_meta: bool,
    ) -> AsyncIterator[dict[str, Any]]:
        if include_meta:
            yield {
                "type": "meta",
                "model": model,
                "sources": [c.model_dump() for c in prepared.sources],
                "web_used": prepared.web_used,
            }
        started = time.perf_counter()
        first_token_ms: int | None = None
        try:
            async for piece in self._llm.stream(
                system=SYSTEM_PROMPT,
                user=prepared.user_prompt,
                model=model,
                history=prepared.history,
            ):
                if first_token_ms is None:
                    first_token_ms = int((time.perf_counter() - started) * 1000)
                yield {"type": "token", "model": model, "text": piece}
        except LLMError as exc:
            yield {"type": "error", "model": model, "message": str(exc)}
            return
        except Exception:
            logger.exception("Streaming failed for model=%s", model)
            yield {"type": "error", "model": model, "message": "Unexpected error while generating"}
            return
        yield {
            "type": "done",
            "model": model,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "first_token_ms": first_token_ms,
        }


def _citations_from_chunks(chunks: list[RetrievedChunk]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[str, int | None, float | None]] = set()
    for chunk in chunks:
        meta = chunk.metadata
        source = str(meta.get("source", "unknown"))
        page_raw = meta.get("page")
        page = int(page_raw) if page_raw is not None else None
        start_raw = meta.get("start_seconds")
        start = float(start_raw) if start_raw is not None else None
        key = (source, page, start)
        if key in seen:
            continue
        seen.add(key)
        snippet = chunk.text[:700] + ("…" if len(chunk.text) > 700 else "")
        citations.append(
            Citation(
                source=source,
                page=page,
                source_id=str(meta["source_id"]) if meta.get("source_id") else None,
                chunk_id=chunk.id,
                score=chunk.score,
                snippet=snippet,
                source_type=str(meta.get("source_type", "pdf")),
                start_seconds=start,
                url=str(meta["url"]) if meta.get("url") else None,
            )
        )
    return citations


def _citations_from_web(results: list[WebResult]) -> list[Citation]:
    return [
        Citation(
            source=result.title,
            snippet=result.content[:400] + ("…" if len(result.content) > 400 else ""),
            source_type="web",
            url=result.url,
        )
        for result in results
    ]
