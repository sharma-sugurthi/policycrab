import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import httpx
from tqdm.asyncio import tqdm

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CASES_DIR = Path("cases")
RESULTS_FILE = Path("results.json")

sys.path.append(str(Path(__file__).parent.parent / "backend"))
from app.agents.graph import get_claim_evaluation_graph

# Pre-load graph to avoid re-instantiation
graph = get_claim_evaluation_graph()

async def run_case(client: httpx.AsyncClient, url: str, token: str, case: dict) -> dict:
    try:
        initial_state = {
            "messages": [],
            "raw_policy_text": case.get("benchmark_policy_excerpt", "Standard Policy"),
            "raw_claim_text": case["claim_description"],
            "policy_profile": case.get("policy_profile"),
            "session_id": None,
            "policy_indexed": False,
            "current_phase": "intake",
            "errors": []
        }
        
        final_state = await graph.ainvoke(initial_state)
        
    except Exception as e:
        logger.error(f"Error evaluating case {case['id']}: {e}")
        return {
            "case_id": case["id"],
            "category": case["category"],
            "expected": case["expected"],
            "actual": {"error": str(e)},
            "status": "fail",
            "reason": f"Engine Error: {str(e)}"
        }

    # Extract actual results
    actual = {}
    if final_state.get("appeal_output"):
        actual["appeal_recommendation"] = final_state["appeal_output"].get("appeal_recommendation")
        actual["contradiction_detected"] = final_state["appeal_output"].get("contradiction_detected")
        actual["contradiction_strength"] = final_state["appeal_output"].get("contradiction_strength")
    actual["route_decision"] = final_state.get("route_decision")

    expected = case["expected"]
    
    # Determine pass/fail
    passed = True
    reason = []
    
    if actual.get("appeal_recommendation") != expected.get("appeal_recommendation"):
        passed = False
        reason.append(f"Recommendation: expected {expected.get('appeal_recommendation')}, got {actual.get('appeal_recommendation')}")
        
    if actual.get("contradiction_detected") != expected.get("contradiction_detected"):
        passed = False
        reason.append(f"Contradiction Detected: expected {expected.get('contradiction_detected')}, got {actual.get('contradiction_detected')}")
        
    if actual.get("contradiction_strength") != expected.get("contradiction_strength"):
        passed = False
        reason.append(f"Strength: expected {expected.get('contradiction_strength')}, got {actual.get('contradiction_strength')}")
        
    status = "pass" if passed else "fail"
    
    return {
        "case_id": case["id"],
        "category": case["category"],
        "expected": expected,
        "actual": actual,
        "status": status,
        "reason": "; ".join(reason) if reason else "Perfect Match"
    }


async def main(url: str, token: str, concurrency: int = 5):
    if not CASES_DIR.exists():
        logger.error(f"Cases directory not found: {CASES_DIR}")
        sys.exit(1)
        
    case_files = list(CASES_DIR.glob("*.json"))
    if not case_files:
        logger.error("No case files found.")
        sys.exit(1)
        
    logger.info(f"Loaded {len(case_files)} cases.")
    
    cases = []
    for cf in case_files:
        with open(cf, "r") as f:
            cases.append(json.load(f))
            
    # Restore concurrency limit to take advantage of unlocked quotas
    sem = asyncio.Semaphore(concurrency)
    
    async def bound_run_case(client, c):
        async with sem:
            return await run_case(client, url, token, c)
            
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Run with a nice progress bar
        tasks = [bound_run_case(client, c) for c in cases]
        results = await tqdm.gather(*tasks, desc="Evaluating Claims")
            
    # Calculate stats
    passed = sum(1 for r in results if r["status"] == "pass")
    total = len(results)
    accuracy = (passed / total) * 100
    
    logger.info(f"--- Benchmark Complete ---")
    logger.info(f"Total Cases: {total}")
    logger.info(f"Passed:      {passed}")
    logger.info(f"Accuracy:    {accuracy:.1f}%")
    
    # Save results
    with open(RESULTS_FILE, "w") as f:
        json.dump({
            "summary": {
                "total": total,
                "passed": passed,
                "accuracy_percent": accuracy
            },
            "results": results
        }, f, indent=2)
        
    logger.info(f"Results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PolicyCrab Benchmark Runner")
    parser.add_argument("--url", type=str, default="http://localhost:8000/api/claim/evaluate", help="API Endpoint")
    parser.add_argument("--token", type=str, help="JWT auth token (required unless auth is bypassed in dev)")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent requests")
    
    args = parser.parse_args()
    
    asyncio.run(main(args.url, args.token, args.concurrency))
