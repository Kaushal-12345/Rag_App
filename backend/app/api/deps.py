"""FastAPI dependency accessors."""

from __future__ import annotations

from fastapi import Request

from app.config import Settings
from app.ingestion.pipeline import IngestPipeline
from app.retrieval.vector_store import VectorStore
from app.services.rag_service import RagService


def get_pipeline(request: Request) -> IngestPipeline:
    return request.app.state.pipeline


def get_rag_service(request: Request) -> RagService:
    return request.app.state.rag_service


def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings
