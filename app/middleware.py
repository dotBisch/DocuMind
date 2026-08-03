"""Cross-cutting HTTP concerns: rate limiting, request logging, and
mapping upstream failures to structured JSON errors.

The rate limiter is in-memory per process — on serverless that means
per warm instance, so it's a soft limit. Fine for a demo; a shared
store (Redis/Postgres) would be the production answer, noted in
DESIGN.md limitations.
"""

import logging
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import RATE_LIMIT_PER_MINUTE

logger = logging.getLogger("documind.http")

_WINDOW_SECONDS = 60
_hits: dict[str, deque] = defaultdict(deque)


def _rate_limited(client_ip: str) -> bool:
    now = time.monotonic()
    window = _hits[client_ip]
    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        return True
    window.append(now)
    return False


def _looks_like_quota_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower()


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def observe(request: Request, call_next):
        if request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            if _rate_limited(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "rate limit exceeded — slow down"},
                )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000)
            if _looks_like_quota_error(exc):
                # upstream LLM/embedding daily quota — the client's most
                # actionable signal is "try again later", not a 500
                logger.warning(
                    "quota exhausted: path=%s ms=%d", request.url.path, elapsed_ms
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "LLM daily quota exhausted — try again later"
                    },
                )
            logger.exception("unhandled: path=%s ms=%d", request.url.path, elapsed_ms)
            return JSONResponse(
                status_code=500, content={"detail": "internal error"}
            )

        elapsed_ms = round((time.perf_counter() - start) * 1000)
        # one structured line per request; no question text, no IPs (PII)
        logger.info(
            "request: method=%s path=%s status=%d ms=%d",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
