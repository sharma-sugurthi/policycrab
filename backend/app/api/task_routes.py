"""
Task Status API — poll or stream progress of background tasks.

Background tasks run inside the web dyno via FastAPI BackgroundTasks.
Their state is stored in Redis (Upstash free tier) or in-memory as fallback.

Endpoints:
  GET  /api/tasks/{task_id}        — Instant JSON poll
  GET  /api/tasks/{task_id}/stream — SSE real-time progress stream
  DELETE /api/tasks/{task_id}      — Best-effort cancellation
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.auth import get_current_user
from app.worker import get_task_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["Task Queue"])


@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Poll the current status of a background task.

    States:
    - PENDING:  Task queued but not yet started
    - PROGRESS: Task running — check `progress` (0-100) and `current_step`
    - SUCCESS:  Complete — `result` contains the output payload
    - FAILURE:  Failed — `error` contains the error message
    """
    state = get_task_state(task_id)
    if state is None:
        return {
            "task_id": task_id,
            "state": "NOT_FOUND",
            "progress": 0,
            "current_step": "Task not found or expired (results expire after 1 hour)",
            "result": None,
        }
    return state


@router.get("/{task_id}/stream")
async def stream_task_progress(task_id: str):
    """
    SSE real-time progress stream for a background task.

    Emits progress events every second until the task reaches a terminal
    state (SUCCESS or FAILURE). Automatically closes after 10 minutes.

    Usage (JavaScript):
        const es = new EventSource('/api/tasks/abc123/stream');
        es.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.state === 'SUCCESS' || data.state === 'FAILURE') {
                es.close();
            }
        };
    """
    async def _generate():
        max_polls = 600   # 10 minutes at 1s interval
        last_progress = -1

        for _ in range(max_polls):
            state = get_task_state(task_id)

            if state is None:
                yield f"event: failed\ndata: {json.dumps({'task_id': task_id, 'error': 'Task not found'})}\n\n"
                return

            current_progress = state.get("progress", 0)
            task_state = state.get("state", "PENDING")

            # Emit only if progress changed, or we reached a terminal state
            if current_progress != last_progress or task_state in ("SUCCESS", "FAILURE"):
                event = {
                    **state,
                    "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                }

                if task_state == "SUCCESS":
                    yield f"event: completed\ndata: {json.dumps(event)}\n\n"
                    return
                elif task_state == "FAILURE":
                    yield f"event: failed\ndata: {json.dumps(event)}\n\n"
                    return
                else:
                    yield f"event: progress\ndata: {json.dumps(event)}\n\n"

                last_progress = current_progress
            else:
                # Emit a keep-alive comment to flush proxy buffers (Vite / Cloud Run)
                yield ": keep-alive\n\n"

            await asyncio.sleep(1)

        # Timeout
        yield f"event: failed\ndata: {json.dumps({'task_id': task_id, 'error': 'Stream timed out after 10 minutes'})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
