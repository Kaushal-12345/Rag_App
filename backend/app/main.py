"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_chat import router as chat_router
from app.api.routes_ingest import router as ingest_router
from app.api.routes_sources import router as sources_router
from app.config import Settings, get_settings
from app.ingestion.pipeline import IngestPipeline
from app.llm.providers import OpenAICompatibleClient
from app.retrieval.embedder import SentenceTransformerEmbedder
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.vector_store import ChromaVectorStore
from app.retrieval.web_search import DefaultWebSearcher
from app.services.rag_service import RagService
from app.utils.logging import configure_logging
from app.utils.rate_limit import RateLimitMiddleware


def _build_services(settings: Settings) -> tuple[IngestPipeline, RagService, ChromaVectorStore]:
    embedder = SentenceTransformerEmbedder(settings)
    vector_store = ChromaVectorStore(settings.chroma_path)
    llm = OpenAICompatibleClient(settings)
    pipeline = IngestPipeline(settings=settings, embedder=embedder, vector_store=vector_store)
    rag = RagService(
        settings=settings,
        embedder=embedder,
        vector_store=vector_store,
        llm=llm,
        web_searcher=DefaultWebSearcher(settings),
        reranker=CrossEncoderReranker(settings.rerank_model) if settings.rerank_enabled else None,
    )
    return pipeline, rag, vector_store


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    pipeline, rag, vector_store = _build_services(settings)
    app.state.settings = settings
    app.state.pipeline = pipeline
    app.state.rag_service = rag
    app.state.vector_store = vector_store
    yield


app = FastAPI(
    title="RAG App",
    version="1.0.0",
    description="Chat with PDFs and YouTube videos using open-source models and optional web search.",
    lifespan=lifespan,
)

_settings = get_settings()
app.add_middleware(RateLimitMiddleware, per_minute=_settings.rate_limit_per_minute)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list() or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ingest_router)
app.include_router(chat_router)
app.include_router(sources_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
