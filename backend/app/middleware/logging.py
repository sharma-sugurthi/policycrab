"""
Structured Request Logging Middleware

Logs every HTTP request and response as a single JSON line, suitable for
parsing in Heroku log viewer, Datadog, or any log aggregator.

Fields logged per request:
  - method     HTTP method
  - path       URL path (no query string — avoids PII in query params)
  - status     HTTP response status code
  - latency_ms Round-trip latency in milliseconds
  - user        Short hash of Bearer token (non-reversible, no raw UUID)
                Present only when a valid Bearer token exists.

Fields deliberately NOT logged:
  - Email, name, or any PII
  - Request/response bodies
  - Query parameters (may contain sensitive values)
  - Full Authorization header value
"""

import json
import logging
import time
from hashlib import sha256

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("policycrab.access")

# Paths to skip (health checks and static files clutter logs)
_SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}


def _hash_token(token: str) -> str:
    """Return first 12 hex chars of SHA-256 of the raw JWT — stable, non-reversible."""
    return sha256(token.encode()).hexdigest()[:12]


def _extract_user_hash(request: Request) -> str | None:
    """Extract a non-PII token hash from the Authorization header, if present."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return _hash_token(token)
    return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that emits one structured JSON log line per request.

    Register in main.py:
        from app.middleware.request_logger import RequestLoggingMiddleware
        app.add_middleware(RequestLoggingMiddleware)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        user_hash = _extract_user_hash(request)

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            _emit(request.method, path, 500, elapsed_ms, user_hash,
                  error=type(exc).__name__)
            raise

        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

        # Cloudflare metadata (set by CloudflareMiddleware if active)
        cf_ray = getattr(request.state, "cf_ray", "") or ""
        cf_country = getattr(request.state, "cf_country", "") or ""

        _emit(request.method, path, status_code, elapsed_ms, user_hash,
              cf_ray=cf_ray, cf_country=cf_country)
        return response


def _emit(
    method: str,
    path: str,
    status: int,
    latency_ms: float,
    user_hash: str | None,
    error: str | None = None,
    cf_ray: str = "",
    cf_country: str = "",
) -> None:
    record: dict = {
        "method": method,
        "path": path,
        "status": status,
        "latency_ms": latency_ms,
    }
    if user_hash:
        record["user"] = user_hash
    if cf_ray:
        record["cf_ray"] = cf_ray
    if cf_country:
        record["cf_country"] = cf_country
    if error:
        record["error"] = error

    if status >= 500:
        logger.error(json.dumps(record))
    elif status >= 400:
        logger.warning(json.dumps(record))
    else:
        logger.info(json.dumps(record))
