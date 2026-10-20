"""Chat endpoints: one-shot, streaming (SSE), 3-model compare (SSE), model list."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_app_settings, get_rag_service
from app.api.sse import sse_response
from app.config import Settings
from app.llm.providers import LLMError
from app.schemas.api import ChatRequest, ChatResponse, CompareRequest, ModelsResponse
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models", response_model=ModelsResponse)
def list_models(settings: Settings = Depends(get_app_settings)) -> ModelsResponse:
    """The three configured open-source models and the default."""
    return ModelsResponse(
        models=list(dict.fromkeys(settings.llm_models)),
        default=settings.resolved_model(None),
        web_search_available=True,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    rag: RagService = Depends(get_rag_service),
) -> ChatResponse:
    """Retrieve top-k chunks for the session and return a grounded answer."""
    try:
        return await rag.chat(
            session_id=body.session_id,
            question=body.question,
            top_k=body.top_k,
            model=body.model,
            web_search=body.web_search,
            history=body.history,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Chat failed for session=%s", body.session_id)
        raise HTTPException(status_code=500, detail="Failed to generate an answer") from None


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    rag: RagService = Depends(get_rag_service),
) -> StreamingResponse:
    """Stream an answer token by token as Server-Sent Events."""
    return sse_response(
        rag.stream_events(
            session_id=body.session_id,
            question=body.question,
            top_k=body.top_k,
            model=body.model,
            web_search=body.web_search,
            history=body.history,
        )
    )


@router.post("/chat/compare")
async def chat_compare(
    body: CompareRequest,
    rag: RagService = Depends(get_rag_service),
) -> StreamingResponse:
    """Ask all three models the same question; events are tagged with the model name."""
    return sse_response(
        rag.compare_events(
            session_id=body.session_id,
            question=body.question,
            top_k=body.top_k,
            web_search=body.web_search,
            history=body.history,
        )
    )
