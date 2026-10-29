from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from graphmovie.config import settings

OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.api_keys:
            return await call_next(request)
        if request.url.path in OPEN_PATHS:
            return await call_next(request)
        key = request.headers.get("x-api-key") or request.query_params.get("api_key")
        if not key or key not in settings.api_keys:
            return JSONResponse(status_code=401, content={"detail": "invalid or missing API key"})
        request.state.api_key = key
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, per_minute: int | None = None) -> None:
        super().__init__(app)
        self.per_minute = per_minute if per_minute is not None else settings.rate_limit_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _client_id(self, request: Request) -> str:
        api_key = getattr(request.state, "api_key", None)
        if api_key:
            return f"key:{api_key}"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        client = request.client.host if request.client else "unknown"
        return f"ip:{client}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self.per_minute <= 0 or request.url.path in OPEN_PATHS:
            return await call_next(request)
        now = time.monotonic()
        bucket = self._client_id(request)
        with self._lock:
            window = self._hits[bucket]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self.per_minute:
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"rate limit exceeded: {self.per_minute}/minute"},
                    headers={"Retry-After": "60"},
                )
            window.append(now)
        return await call_next(request)


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Best-effort wall-clock timeout for sync routes running in the threadpool."""

    def __init__(self, app, *, timeout_sec: float | None = None) -> None:
        super().__init__(app)
        self.timeout_sec = (
            timeout_sec if timeout_sec is not None else settings.request_timeout_sec
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self.timeout_sec <= 0 or request.url.path in OPEN_PATHS:
            return await call_next(request)
        import anyio

        try:
            with anyio.fail_after(self.timeout_sec):
                return await call_next(request)
        except TimeoutError:
            return JSONResponse(
                status_code=504,
                content={"detail": f"request timed out after {self.timeout_sec}s"},
            )
