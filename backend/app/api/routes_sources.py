"""List and delete indexed sources."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_app_settings, get_vector_store
from app.config import Settings
from app.retrieval.vector_store import VectorStore
from app.schemas.api import SourceInfo, SourcesResponse
from app.utils.ids import collection_name, safe_session_id

router = APIRouter()


def _session(raw: str) -> str:
    try:
        return safe_session_id(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sources", response_model=SourcesResponse)
def list_sources(
    session_id: str = Query(min_length=1),
    store: VectorStore = Depends(get_vector_store),
) -> SourcesResponse:
    """Documents and videos indexed in a session."""
    session = _session(session_id)
    items = store.list_sources(collection_name(session))
    return SourcesResponse(session_id=session, sources=[SourceInfo(**item) for item in items])


@router.delete("/sources/{source_id}")
def delete_source(
    source_id: str,
    session_id: str = Query(min_length=1),
    store: VectorStore = Depends(get_vector_store),
) -> dict[str, int | str]:
    """Remove one document or video from a session."""
    session = _session(session_id)
    removed = store.delete_source(collection_name(session), source_id)
    if removed == 0:
        raise HTTPException(status_code=404, detail="Source not found in this session")
    return {"source_id": source_id, "chunks_removed": removed}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, str]:
    """Delete everything for a session (vectors and uploaded files)."""
    session = _session(session_id)
    store.delete_collection(collection_name(session))
    shutil.rmtree(settings.upload_dir / session, ignore_errors=True)
    return {"session_id": session, "status": "deleted"}
