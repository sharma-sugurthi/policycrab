"""
Benchmark API Routes — manage and execute the 200-case synthetic evaluation suite.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.security.rate_limit import rate_limit_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/benchmark", tags=["Benchmark Suite"])
BENCHMARK_RUN_RATE_LIMIT = rate_limit_user("benchmark:run", max_requests=10, window_seconds=300)


class BenchmarkRunRequest(BaseModel):
    mode: str = Field("quick", description="'quick' (21 curated sample cases) or 'full' (all 200 cases)")
    concurrency: int = Field(4, ge=1, le=10, description="Max parallel reasoning evaluation tasks")


def _get_benchmarks_dir() -> Path:
    paths_to_check = [
        Path(__file__).resolve().parents[3] / "benchmarks",
        Path("benchmarks").resolve(),
        Path("../benchmarks").resolve(),
    ]
    for p in paths_to_check:
        if p.exists() and (p / "cases").exists():
            return p
    raise FileNotFoundError("Could not locate benchmarks/cases directory.")


@router.get("/cases")
async def get_benchmark_cases(user: dict = Depends(get_current_user)):
    """
    Retrieve metadata and summary count of all synthetic ground-truth test cases.
    """
    try:
        benchmarks_dir = _get_benchmarks_dir()
        cases_dir = benchmarks_dir / "cases"
        case_files = sorted(cases_dir.glob("*.json"))
        
        cases = []
        category_counts = {}
        for f in case_files:
            try:
                with open(f, "r", encoding="utf-8") as h:
                    c = json.load(h)
                    cat = c.get("category", "other")
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                    cases.append({
                        "id": c.get("id"),
                        "category": cat,
                        "title": c.get("title"),
                        "claim_description": c.get("claim_description"),
                        "allowed_amount": c.get("allowed_amount"),
                        "expected": c.get("expected"),
                        "ground_truth_rationale": c.get("ground_truth_rationale")
                    })
            except Exception as e:
                logger.warning(f"Error reading {f.name}: {e}")

        return {
            "total_cases": len(cases),
            "categories": category_counts,
            "cases": cases
        }
    except Exception as e:
        logger.error(f"Failed to fetch benchmark cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results")
async def get_latest_results(user: dict = Depends(get_current_user)):
    """
    Get the official saved benchmark test results (results.json).
    """
    try:
        benchmarks_dir = _get_benchmarks_dir()
        results_file = benchmarks_dir / "results.json"
        
        if not results_file.exists():
            return {"status": "no_results", "summary": None, "results": []}

        with open(results_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {"status": "complete", **data}
    except Exception as e:
        logger.error(f"Error fetching benchmark results: {e}")
        return {"status": "error", "summary": None, "results": []}


@router.post("/run", status_code=202)
async def start_benchmark_run(
    request: BenchmarkRunRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    _: None = Depends(BENCHMARK_RUN_RATE_LIMIT),
):
    """
    Start an automated background evaluation of the synthetic benchmark suite.
    Returns a task ID that can be streamed via SSE at /api/tasks/{task_id}/stream.
    """
    from app.worker import new_task_id, init_task
    from app.tasks.benchmark_tasks import run_benchmark_task

    task_id = new_task_id()
    init_task(task_id, "benchmark_suite")
    
    background_tasks.add_task(
        run_benchmark_task,
        task_id=task_id,
        mode=request.mode,
        concurrency=request.concurrency,
        user_id=user.get("id"),
    )

    logger.info(f"Started benchmark run {task_id} (mode={request.mode}, concurrency={request.concurrency})")

    return {
        "task_id": task_id,
        "mode": request.mode,
        "status_url": f"/api/tasks/{task_id}",
        "stream_url": f"/api/tasks/{task_id}/stream",
        "message": f"Benchmark evaluation started ({request.mode} mode)."
    }
