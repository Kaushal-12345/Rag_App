"""Server-Sent Events helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # stop nginx-style proxies from buffering the stream
}


def format_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _encode(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
    try:
        async for event in events:
            yield format_event(event)
    except FileNotFoundError as exc:
        yield format_event({"type": "error", "message": str(exc)})
    except ValueError as exc:
        yield format_event({"type": "error", "message": str(exc)})
    except Exception:
        logger.exception("Stream failed")
        yield format_event({"type": "error", "message": "Something went wrong while answering."})
    yield format_event({"type": "end"})


def sse_response(events: AsyncIterator[dict[str, Any]]) -> StreamingResponse:
    return StreamingResponse(_encode(events), media_type="text/event-stream", headers=SSE_HEADERS)
