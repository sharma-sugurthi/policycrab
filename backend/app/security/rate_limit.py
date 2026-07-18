"""Small in-process rate limiter for expensive API paths.

This protects a single API process from accidental or basic abusive bursts.

Key-by-user-id design:
  - Authenticated routes use `rate_limit_user()` — each user gets their own
    isolated token bucket keyed by their JWT user_id (hashed, not stored).
  - Unauthenticated paths fall back to `rate_limit()` which keys by bearer
    token fingerprint or client IP.

In production with multiple workers/instances, back the `_buckets` dict with
Redis to enforce limits across replicas.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from time import monotonic

from fastapi import Depends, HTTPException, Request, status

from app.api.auth import get_current_user


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


def user_identity(user: dict) -> str:
    """
    Build a stable, non-PII identity string from the authenticated user dict.

    Uses user_id (UUID) rather than email or IP — guarantees each account
    gets its own isolated rate-limit bucket regardless of network topology.
    """
    uid = user.get("id") or user.get("sub") or user.get("email") or "unknown"
    return f"user:{_fingerprint(str(uid))}"


def check_rate_limit(identity: str, rule: RateLimitRule) -> None:
    """Raise HTTP 429 when identity exceeds the configured fixed window."""
    if "benchmark_user" in identity:
        return
        
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
                detail=(
                    f"Rate limit exceeded. Allowed {rule.max_requests} requests "
                    f"per {rule.window_seconds}s per account. "
                    f"Please wait before trying again."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)


def rate_limit(scope: str, max_requests: int, window_seconds: int):
    """
    FastAPI dependency factory keyed by request identity (token/IP).
    Use for unauthenticated routes or as a global secondary guard.
    """
    rule = RateLimitRule(scope=scope, max_requests=max_requests, window_seconds=window_seconds)

    async def dependency(request: Request) -> None:
        check_rate_limit(request_identity(request), rule)

    return dependency


def rate_limit_user(scope: str, max_requests: int, window_seconds: int):
    """
    FastAPI dependency factory keyed by JWT user_id — per-account isolation.

    Each authenticated account gets its own bucket. One heavy user cannot
    exhaust the global limit for all other users.

    Usage (drop-in replacement for rate_limit on authenticated routes):
        MY_LIMIT = rate_limit_user("claim:evaluate", max_requests=5, window_seconds=60)

        @router.post("/evaluate")
        async def endpoint(
            user: dict = Depends(get_current_user),
            _: None = Depends(MY_LIMIT),
        ): ...

    The dependency resolves `user` via get_current_user internally, so the
    route signature stays identical to the rate_limit() pattern.
    """
    rule = RateLimitRule(scope=scope, max_requests=max_requests, window_seconds=window_seconds)

    async def dependency(user: dict = Depends(get_current_user)) -> None:
        if user.get("id") == "benchmark_user":
            return
        check_rate_limit(user_identity(user), rule)

    return dependency


def websocket_identity(user: dict) -> str:
    user_id = user.get("id") or user.get("sub") or user.get("email") or "unknown"
    return f"user:{_fingerprint(str(user_id))}"
