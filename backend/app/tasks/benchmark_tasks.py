"""
Benchmark Tasks — Asynchronous execution of the 200-case synthetic medical denial,
No Surprises Act, and billing fraud evaluation suite.
"""

import asyncio
import json
import logging
import time
from pathlib import Path

from app.worker import update_progress, complete_task, fail_task
from app.agents.graph import get_claim_evaluation_graph

logger = logging.getLogger(__name__)

# Locate benchmarks directory reliably
def get_benchmarks_dir() -> Path:
    paths_to_check = [
        Path(__file__).resolve().parents[2] / "benchmarks",  # backend/benchmarks
        Path("benchmarks").resolve(),
    ]
    for p in paths_to_check:
        if p.exists() and (p / "cases").exists():
            return p
    raise FileNotFoundError("Could not locate benchmarks/cases directory.")


async def evaluate_single_case(case: dict, sem: asyncio.Semaphore) -> dict:
    """Evaluate a single benchmark scenario against the multi-agent pipeline."""
    async with sem:
        case_id = case.get("id", "UNKNOWN")
        category = case.get("category", "general")
        expected = case.get("expected", {})
        
        logger.debug(f"Benchmark: Starting evaluation for case {case_id} ({category})")
        
        graph = get_claim_evaluation_graph()
        initial_state = {
            "messages": [],
            "raw_policy_text": "",
            "raw_claim_text": case.get("claim_description", ""),
            "benchmark_policy_excerpt": case.get("benchmark_policy_excerpt"),
            "policy_profile": case.get("policy_profile"),
            "claim_case": None,
            "claim_overrides": case.get("claim_overrides"),
            "allowed_amount": case.get("allowed_amount"),
            "cost_breakdown": None,
            "contradiction_analysis": None,
            "triage_decision": None,
            "appeal_output": None,
            "current_phase": "intake",
            "route_decision": "",
            "errors": [],
            "extraction_warnings": [],
            "extraction_confidence": None,
            "explanations": {},
            "session_id": None,
            "policy_indexed": True,
        }

        start_time = time.time()
        try:
            # Run with a 50 second timeout per case
            result_state = await asyncio.wait_for(
                graph.ainvoke(initial_state),
                timeout=50.0
            )
        except Exception as e:
            logger.error(f"Benchmark case {case_id} failed with error: {e}")
            return {
                "case_id": case_id,
                "category": category,
                "title": case.get("title", f"Case {case_id}"),
                "expected": expected,
                "actual": {"error": str(e)},
                "status": "fail",
                "reason": f"Execution error: {str(e)}",
                "duration_ms": int((time.time() - start_time) * 1000),
                "ground_truth_rationale": case.get("ground_truth_rationale", "")
            }

        duration_ms = int((time.time() - start_time) * 1000)
        
        # Extract actual reasoning metrics
        actual = {}
        appeal_out = result_state.get("appeal_output") or {}
        cost_out = result_state.get("cost_breakdown") or {}
        triage_out = result_state.get("triage_decision") or {}
        contradiction_out = result_state.get("contradiction_analysis") or {}
        
        actual["appeal_recommendation"] = appeal_out.get("appeal_recommendation") or contradiction_out.get("appeal_recommendation") or "UNKNOWN"
        actual["contradiction_detected"] = appeal_out.get("contradiction_detected") or contradiction_out.get("is_contradiction")
        actual["contradiction_strength"] = appeal_out.get("contradiction_strength") or contradiction_out.get("contradiction_strength")
        actual["route_decision"] = result_state.get("route_decision")
        actual["triage_path"] = triage_out.get("path")
        actual["nsa_violation_detected"] = cost_out.get("nsa_violation_detected", False)
        
        # Determine pass/fail based on category semantics
        passed = True
        reasons = []
        
        expected_rec = expected.get("appeal_recommendation", "")
        actual_rec = str(actual.get("appeal_recommendation", "")).upper()
        
        # Semantic grouping for recommendations
        affirmative_appeals = {"STRONG_APPEAL", "APPEAL", "EXCEPTION_REQUEST"}
        negative_appeals = {"CLAIM_CORRECTLY_DENIED", "UNLIKELY_TO_WIN"}
        
        if expected_rec in affirmative_appeals:
            if actual_rec not in affirmative_appeals:
                passed = False
                reasons.append(f"Expected appeal ({expected_rec}), got {actual_rec}")
        elif expected_rec in negative_appeals:
            if actual_rec not in negative_appeals:
                passed = False
                reasons.append(f"Expected denial/unlikely ({expected_rec}), got {actual_rec}")
        elif expected_rec and expected_rec != actual_rec:
            passed = False
            reasons.append(f"Recommendation mismatch: expected {expected_rec}, got {actual_rec}")

        # Check special NSA rule
        if category == "nsa_balance_billing" and expected.get("nsa_violation_detected"):
            if not actual["nsa_violation_detected"] and actual["triage_path"] != "PAYER_ILLEGAL_DENIAL":
                passed = False
                reasons.append("Failed to detect No Surprises Act (NSA) balance billing violation")

        status = "pass" if passed else "fail"
        reason_str = "; ".join(reasons) if reasons else "Match verified against ground truth"

        return {
            "case_id": case_id,
            "category": category,
            "title": case.get("title", f"Case {case_id}"),
            "claim_description": case.get("claim_description", ""),
            "expected": expected,
            "actual": actual,
            "status": status,
            "reason": reason_str,
            "duration_ms": duration_ms,
            "ground_truth_rationale": case.get("ground_truth_rationale", "")
        }


async def run_benchmark_task(task_id: str, mode: str = "quick", concurrency: int = 5, user_id: str = None):
    """
    Background task coroutine executing the benchmark suite.
    mode: "quick" (21 cases, 3 per category) or "full" (all 200 cases)
    """
    logger.info(f"Starting benchmark task {task_id}: mode={mode}, concurrency={concurrency}")
    try:
        benchmarks_dir = get_benchmarks_dir()
        cases_dir = benchmarks_dir / "cases"
        results_file = benchmarks_dir / "results.json"
        
        case_files = sorted(cases_dir.glob("*.json"))
        if not case_files:
            fail_task(task_id, "No synthetic case files found in benchmarks/cases/.")
            return

        all_cases = []
        for f in case_files:
            try:
                with open(f, "r", encoding="utf-8") as file_handle:
                    all_cases.append(json.load(file_handle))
            except Exception as e:
                logger.warning(f"Could not load case {f.name}: {e}")

        if not all_cases:
            fail_task(task_id, "Failed to parse JSON benchmark cases.")
            return

        # Select cases based on mode
        selected_cases = []
        if mode == "quick":
            # 3 cases per category for fast demo (~21 total)
            seen_counts = {}
            for c in all_cases:
                cat = c.get("category", "other")
                count = seen_counts.get(cat, 0)
                if count < 3:
                    selected_cases.append(c)
                    seen_counts[cat] = count + 1
        else:
            selected_cases = all_cases

        total_cases = len(selected_cases)
        logger.info(f"Benchmark suite task {task_id}: selected {total_cases} scenarios for execution.")
        
        update_progress(
            task_id=task_id,
            progress=5,
            current_step=f"Loaded {total_cases} scenarios. Starting multi-agent reasoning eval...",
            completed_cases=0,
            total_cases=total_cases,
            passed_cases=0,
            mode=mode
        )

        # Use Semaphore to manage concurrency without overwhelming rate limits
        sem = asyncio.Semaphore(concurrency)
        completed_count = 0
        passed_count = 0
        results_list = []

        # Run tasks and report progress as each finishes
        tasks = [evaluate_single_case(c, sem) for c in selected_cases]
        for future in asyncio.as_completed(tasks):
            case_result = await future
            results_list.append(case_result)
            completed_count += 1
            if case_result["status"] == "pass":
                passed_count += 1

            progress_percent = min(95, max(10, int((completed_count / total_cases) * 90)))
            update_progress(
                task_id=task_id,
                progress=progress_percent,
                current_step=f"Evaluating ({completed_count}/{total_cases}) — {passed_count} passing",
                completed_cases=completed_count,
                total_cases=total_cases,
                passed_cases=passed_count,
                latest_case=case_result,
                mode=mode
            )

        # Calculate final stats and category breakdown
        results_list.sort(key=lambda x: x["case_id"])
        total_passed = sum(1 for r in results_list if r["status"] == "pass")
        accuracy = (total_passed / total_cases) * 100.0 if total_cases > 0 else 0.0

        category_stats = {}
        for r in results_list:
            cat = r["category"]
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "passed": 0, "accuracy": 0.0}
            category_stats[cat]["total"] += 1
            if r["status"] == "pass":
                category_stats[cat]["passed"] += 1

        for cat, stats in category_stats.items():
            stats["accuracy"] = round((stats["passed"] / stats["total"]) * 100.0, 1)

        final_output = {
            "summary": {
                "total": total_cases,
                "passed": total_passed,
                "failed": total_cases - total_passed,
                "accuracy_percent": round(accuracy, 2),
                "timestamp": time.time(),
                "mode": mode,
                "categories": category_stats
            },
            "results": results_list
        }

        # Save to official results.json
        try:
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(final_output, f, indent=2)
            logger.info(f"Updated official benchmark test results at {results_file}")
        except Exception as e:
            logger.warning(f"Failed to write results.json: {e}")

        logger.info(f"Benchmark task {task_id} completed successfully. Overall Accuracy: {accuracy:.1f}%")
        complete_task(task_id, final_output)

    except Exception as e:
        logger.error(f"Benchmark task {task_id} crashed: {e}", exc_info=True)
        fail_task(task_id, f"Benchmark suite crashed: {str(e)}")
