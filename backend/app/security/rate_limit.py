"""Small in-process rate limiter for expensive API paths.

This protects a single API process from accidental or basic abusive bursts. In
production with multiple workers/instances, keep this dependency but back it
with Redis or enforce equivalent limits at the edge.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status


@dataclass(frozen=True)
class RateLimitRule:
    scope: str
    max_requests: int
    window_seconds: int


_buckets: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def _fingerprint(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:16]


def request_identity(request: Request) -> str:
    """Build a non-PII limiter identity from bearer token or client IP."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return f"token:{_fingerprint(auth_header[7:].strip())}"

    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',')[0].strip()}"

    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


def check_rate_limit(identity: str, rule: RateLimitRule) -> None:
    """Raise HTTP 429 when identity exceeds the configured fixed window."""
    now = monotonic()
    cutoff = now - rule.window_seconds
    key = f"{rule.scope}:{identity}"

    with _lock:
        bucket = _buckets[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= rule.max_requests:
            retry_after = max(1, int(rule.window_seconds - (now - bucket[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait and try again.",
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)


def rate_limit(scope: str, max_requests: int, window_seconds: int):
    """FastAPI dependency factory for per-route rate limits."""
    rule = RateLimitRule(scope=scope, max_requests=max_requests, window_seconds=window_seconds)

    async def dependency(request: Request) -> None:
        check_rate_limit(request_identity(request), rule)

    return dependency


def websocket_identity(user: dict) -> str:
    user_id = user.get("id") or user.get("sub") or user.get("email") or "unknown"
    return f"user:{_fingerprint(str(user_id))}"
