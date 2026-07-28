"""
Lightweight task runner using FastAPI BackgroundTasks + Redis (Upstash).

Why NOT Celery/worker dyno:
  - Heroku Eco plan has 1,000 hours/month shared across ALL dynos.
  - web + worker = ~1,488 hours → exceeds the free limit.
  - Cost: $0 extra with this approach vs $5-7/mo for a separate worker dyno.

How it works:
  1. API route receives request → validates + PHI scrubs synchronously (fast).
  2. FastAPI BackgroundTask dispatches the heavy coroutine in the same process.
  3. Progress is written to Upstash Redis so the frontend can poll it.
  4. If Redis is unavailable (local dev), an in-memory dict is used as fallback.

Limitations vs Celery:
  - Tasks die if the dyno restarts mid-task (rare on Heroku, acceptable for demo).
  - No cross-dyno task visibility (but we only run 1 web dyno anyway).
  - No automatic retry (we implement manual retry logic inside each task).
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

logger = logging.getLogger(__name__)

# ── Redis client (optional — falls back to in-memory if unavailable) ──
_redis_client = None
_memory_store: dict[str, str] = {}   # local dev fallback


def _get_redis():
    """Return a Redis client, or None if not configured."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    from app.config import settings
    if not settings.redis_url:
        return None

    try:
        import redis as redis_lib
        _redis_client = redis_lib.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        _redis_client.ping()
        logger.info("Redis connected: task status store active")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable ({e}), using in-memory task store")
        return None


# ── Task State Management ─────────────────────────────────────────

TASK_TTL = 3600  # seconds — results expire after 1 hour


def set_task_state(task_id: str, state: dict) -> None:
    """Persist task state to Redis or in-memory fallback."""
    payload = json.dumps(state)
    r = _get_redis()
    if r:
        try:
            r.setex(f"task:{task_id}", TASK_TTL, payload)
            return
        except Exception as e:
            logger.warning(f"Redis write failed: {e}, falling back to memory")
    _memory_store[task_id] = payload


def get_task_state(task_id: str) -> dict | None:
    """Retrieve task state from Redis or in-memory fallback."""
    r = _get_redis()
    if r:
        try:
            raw = r.get(f"task:{task_id}")
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning(f"Redis read failed: {e}, falling back to memory")
    raw = _memory_store.get(task_id)
    return json.loads(raw) if raw else None


def update_progress(task_id: str, progress: int, current_step: str,
                    pipeline_phase: str = "", **extra) -> None:
    """Convenience: update a running task's progress."""
    state = get_task_state(task_id) or {}
    state.update({
        "task_id": task_id,
        "state": "PROGRESS",
        "progress": progress,
        "current_step": current_step,
        "pipeline_phase": pipeline_phase,
        **extra,
    })
    set_task_state(task_id, state)


def complete_task(task_id: str, result: dict) -> None:
    """Mark a task as successfully completed with its result."""
    set_task_state(task_id, {
        "task_id": task_id,
        "state": "SUCCESS",
        "progress": 100,
        "current_step": "Complete",
        "result": result,
    })


def fail_task(task_id: str, error: str) -> None:
    """Mark a task as failed with an error message."""
    state = get_task_state(task_id) or {}
    state.update({
        "task_id": task_id,
        "state": "FAILURE",
        "progress": state.get("progress", 0),
        "current_step": "Failed",
        "error": error,
    })
    set_task_state(task_id, state)


# ── Task Starters ─────────────────────────────────────────────────

def new_task_id() -> str:
    return uuid4().hex


def init_task(task_id: str, task_type: str, session_id: str = "") -> None:
    """Initialise a new task in PENDING state."""
    set_task_state(task_id, {
        "task_id": task_id,
        "state": "PENDING",
        "progress": 0,
        "current_step": "Queued...",
        "task_type": task_type,
        "session_id": session_id,
        "created_at": time.time(),
    })
