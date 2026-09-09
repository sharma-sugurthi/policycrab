"""
Quality Gate nodes — deterministic checkpoint between cost calculation and the
appeal path.

Why: the Claim Intake agent substitutes sentinel values when the patient's
description is thin (billed_amount -> 1.0, cpt_code -> "00000", denial_date ->
None which later becomes "today"). Drafting a legal appeal on top of those
sentinels produces confident-looking letters with wrong deadlines and invented
amounts. The gate makes that visible — and, in "block" mode, refuses to draft.

Modes (settings.quality_gate_mode):
  "off"   — node is a no-op
  "warn"  — (default) evaluate, attach checklist to state, continue as before
  "block" — if any CRITICAL field is missing, route to explain_blocked instead
            of the appeal path

Both nodes are pure Python. They never raise and never append to errors.
"""

from __future__ import annotations

import logging

from app.agents.state import AgentState
from app.engine.quality_gate import evaluate_quality_gate, render_checklist_text

logger = logging.getLogger(__name__)


async def quality_gate_node(state: AgentState) -> dict:
    """Evaluate extraction completeness. Never raises."""
    from app.config import settings

    mode = (settings.quality_gate_mode or "warn").lower()
    if mode not in ("off", "warn", "block"):
        mode = "warn"

    try:
        result = evaluate_quality_gate(
            claim_case=state.get("claim_case"),
            policy_profile=state.get("policy_profile"),
            eob_extraction=state.get("eob_extraction"),
            policy_indexed=bool(state.get("policy_indexed")) or bool(state.get("benchmark_policy_excerpt")),
            route_decision=str(state.get("route_decision") or ""),
            mode=mode,
            benchmark_mode=bool(state.get("claim_overrides")),
        )
        gate = result.to_dict()
        if gate["status"] != "PASS":
            logger.info(
                f"Quality gate: {gate['status']} (mode={mode}) — "
                f"critical={gate['critical_missing']} warnings={len(gate['warnings'])}"
            )
    except Exception as e:  # pragma: no cover - defensive: gate must never break the pipeline
        logger.warning(f"Quality gate: evaluation failed (non-fatal): {e}", exc_info=True)
        gate = {"status": "PASS", "mode": mode, "critical_missing": [], "warnings": [],
                "missing_information_checklist": [], "field_confidence": {},
                "completeness_score": 1.0, "version": "v1", "error": str(e)}

    # Deliberately do NOT touch current_phase: the explanation node keys its
    # approved-claim branch on current_phase == "calculation" (set by cost_calculation).
    return {"quality_gate": gate}


async def explain_blocked_node(state: AgentState) -> dict:
    """
    Deterministic (no LLM) explanation used ONLY when the gate BLOCKS drafting.
    Writes a plain-English checklist so the advocate knows exactly what to supply.
    """
    gate = state.get("quality_gate") or {}
    explanations = dict(state.get("explanations", {}))
    explanations["quality_gate"] = render_checklist_text(gate)
    return {
        "explanations": explanations,
        "appeal_output": None,
        "current_phase": "quality_gate_blocked",
    }


def route_after_quality_gate(state: AgentState) -> str:
    """BLOCK -> explain_blocked; otherwise defer to the original cost-based routing."""
    gate = state.get("quality_gate") or {}
    if gate.get("status") == "BLOCK":
        logger.info("Routing → explain_blocked (quality gate BLOCK)")
        return "explain_blocked"
    from app.agents.graph import route_after_cost  # local import: graph imports this module

    return route_after_cost(state)
