"""Builders shared by service and API tests."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.ingestion.pipeline import IngestPipeline
from app.retrieval.vector_store import ChromaVectorStore
from app.services.rag_service import RagService
from tests.fakes import FakeEmbedder, FakeLLM, FakeWebSearcher


def make_settings(tmp_path: Path, **overrides) -> Settings:
    base = dict(
        _env_file=None,
        chroma_path=tmp_path / "chroma",
        upload_dir=tmp_path / "uploads",
        llm_model_1="model-a",
        llm_model_2="model-b",
        llm_model_3="model-c",
        default_llm_model="model-a",
        llm_api_key="test",
    )
    base.update(overrides)
    settings = Settings(**base)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings


def make_services(tmp_path: Path, *, llm: FakeLLM | None = None, web: FakeWebSearcher | None = None, **settings_overrides):
    settings = make_settings(tmp_path, **settings_overrides)
    embedder = FakeEmbedder()
    store = ChromaVectorStore(settings.chroma_path)
    llm = llm or FakeLLM()
    web = web or FakeWebSearcher()
    pipeline = IngestPipeline(settings=settings, embedder=embedder, vector_store=store)
    rag = RagService(settings=settings, embedder=embedder, vector_store=store, llm=llm, web_searcher=web)
    return settings, pipeline, rag, store, llm, web
