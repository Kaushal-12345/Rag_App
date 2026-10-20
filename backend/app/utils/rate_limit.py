"""Tiny in-memory sliding-window rate limiter (per client IP, per process)."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_LIMITED_PREFIXES = ("/chat", "/ingest")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limits expensive endpoints. Fine for a demo; use Redis for multiple workers."""

    def __init__(self, app, *, per_minute: int) -> None:
        super().__init__(app)
        self._per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "POST" and request.url.path.startswith(_LIMITED_PREFIXES):
            client = request.client.host if request.client else "unknown"
            now = time.monotonic()
            window = self._hits[client]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self._per_minute:
                return JSONResponse(
                    {"detail": "Too many requests. Please wait a minute and try again."},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            window.append(now)
        return await call_next(request)
