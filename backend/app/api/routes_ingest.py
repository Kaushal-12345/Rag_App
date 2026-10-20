"""Document ingestion endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.api.deps import get_app_settings, get_pipeline
from app.config import Settings
from app.ingestion.pipeline import IngestPipeline
from app.schemas.api import IngestResponse, YouTubeIngestRequest
from app.utils.ids import clean_session_id, new_id

logger = logging.getLogger(__name__)

router = APIRouter()

_CHUNK = 1024 * 1024


async def _read_limited(file: UploadFile, limit_bytes: int) -> bytes:
    """Read an upload in pieces so an oversized file is rejected early."""
    data = bytearray()
    while piece := await file.read(_CHUNK):
        data.extend(piece)
        if len(data) > limit_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File is too large (limit {limit_bytes // (1024 * 1024)} MB).",
            )
    return bytes(data)


@router.post("/ingest/pdf", response_model=IngestResponse)
async def ingest_pdf(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    pipeline: IngestPipeline = Depends(get_pipeline),
    settings: Settings = Depends(get_app_settings),
) -> IngestResponse:
    """Upload a PDF, chunk it, embed it, and index it into a session collection."""
    filename = Path(file.filename or "upload.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are accepted")

    try:
        session = clean_session_id(session_id) or new_id()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = await _read_limited(file, settings.max_upload_mb * 1024 * 1024)
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if not payload.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="That file doesn't look like a real PDF")

    dest_dir = settings.upload_dir / session
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(payload)

    try:
        # PDF parsing + embedding are CPU-bound; keep them off the event loop.
        return await run_in_threadpool(
            pipeline.ingest_pdf, dest, filename=filename, session_id=session
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("PDF ingest failed for %s", filename)
        raise HTTPException(status_code=500, detail="Failed to ingest PDF") from None


@router.post("/ingest/youtube", response_model=IngestResponse)
async def ingest_youtube(
    body: YouTubeIngestRequest,
    pipeline: IngestPipeline = Depends(get_pipeline),
) -> IngestResponse:
    """Fetch a YouTube transcript, embed it, and index it into a session collection."""
    try:
        session = clean_session_id(body.session_id)
        return await run_in_threadpool(pipeline.ingest_youtube, body.url, session_id=session)
    except ValueError as exc:  # includes YouTubeError (bad link, no captions)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("YouTube ingest failed for %s", body.url)
        raise HTTPException(status_code=500, detail="Failed to ingest video") from None
