"""
Appeal QA — deterministic post-processing node that runs AFTER the Grievance
agent and BEFORE the Explanation agent.

Purpose: turn the LLM-drafted appeal into something a professional advocate can
trust without re-checking every line. Everything here is pure Python — no LLM.

Order of operations (each step is optional and independently guarded):
  1. Citation grounding verifier — every statute the letter cites must exist in
     the verified allowlist or in the knowledge chunks the LLM was actually shown;
     every quoted policy clause must appear in the retrieved policy chunks.
  2. Deterministic success score — transparent, factor-by-factor estimate that
     sits alongside (never replaces) the LLM's estimated_success_probability.
  3. Attach the quality-gate result (if the quality_gate node ran) so the
     AppealOutput carries the missing-information checklist.

Contract:
  * NEVER raises and NEVER appends to state["errors"] — a QA failure must not
    turn a successfully drafted letter into a pipeline error.
  * Additive only: every key it writes onto appeal_output has a default on
    AppealOutput, so older persisted claims still validate.
  * Benchmark mode (claim_overrides set) returns a differently shaped
    appeal_output with no `cited_regulations`; in that case this node passes the
    dict through untouched and reports status SKIPPED.
"""

from __future__ import annotations

import logging

from app.agents.state import AgentState

logger = logging.getLogger(__name__)


def _is_full_appeal_output(appeal_output: object) -> bool:
    """True only for the real AppealOutput shape (not the benchmark stub)."""
    return isinstance(appeal_output, dict) and "cited_regulations" in appeal_output


async def appeal_qa_node(state: AgentState) -> dict:
    """Run deterministic QA over the drafted appeal. Never raises."""
    appeal_output = state.get("appeal_output")

    if not _is_full_appeal_output(appeal_output):
        reason = (
            "no appeal_output in state" if appeal_output is None
            else "appeal_output is not a full AppealOutput (benchmark mode)"
        )
        logger.info(f"Appeal QA: skipped — {reason}")
        return {
            "citation_verification": {"status": "SKIPPED", "reason": reason},
            "current_phase": "appeal",
        }

    # Copy so we never mutate the dict another node may still hold.
    qa_output = dict(appeal_output)
    citation_verification: dict = {"status": "SKIPPED", "reason": "verifier not yet wired"}

    try:
        from app.engine.citation_verifier import run_citation_verification

        citation_verification, qa_output = run_citation_verification(
            appeal_output=qa_output,
            knowledge_chunks=state.get("knowledge_chunks_retrieved") or [],
            policy_chunks=state.get("policy_chunks_retrieved") or [],
        )
    except ImportError:
        # Verifier module not present yet (Phase 0) — pass-through.
        pass
    except Exception as e:  # pragma: no cover - defensive: QA must never break the pipeline
        logger.warning(f"Appeal QA: citation verification failed (non-fatal): {e}", exc_info=True)
        citation_verification = {"status": "SKIPPED", "reason": f"verifier error: {e}"}

    try:
        from app.engine.success_scorer import attach_success_score

        qa_output = attach_success_score(
            appeal_output=qa_output,
            claim_case=state.get("claim_case"),
            cost_breakdown=state.get("cost_breakdown"),
            triage_decision=state.get("triage_decision"),
            contradiction_analysis=state.get("contradiction_analysis"),
            policy_indexed=bool(state.get("policy_indexed")),
            quality_gate=state.get("quality_gate"),
        )
    except ImportError:
        pass
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Appeal QA: success scoring failed (non-fatal): {e}", exc_info=True)

    quality_gate = state.get("quality_gate")
    if isinstance(quality_gate, dict):
        qa_output["quality_gate"] = quality_gate

    return {
        "appeal_output": qa_output,
        "citation_verification": citation_verification,
        "current_phase": "appeal",
    }
