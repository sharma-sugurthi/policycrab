"""
Deterministic Success Scorer — a transparent, factor-by-factor estimate of how
likely an appeal (or provider correction request) is to succeed.

Why: AppealOutput.estimated_success_probability is an LLM/triage guess with no
audit trail. Professional advocates need to see WHY a case looks strong or weak.
This module computes a second number from facts the pipeline already established
(contradiction strength, NSA detection, CARC routing, deadline, grounding score,
data completeness) with every point recorded in `factors`.

The weights below are a documented heuristic (version v1). They are NOT
calibrated against observed outcomes yet — `calibration_note` says so, and the
appeal_outcomes table + /api/outcomes/calibration exist precisely to replace
them with measured rates over time. Never present the score as a probability
derived from data until calibration says it is.

Pure Python. Never raises to the caller (attach_success_score is defensive).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

SCORER_VERSION = "v1"
CALIBRATION_NOTE = (
    "Heuristic v1 — transparent point table, not yet calibrated against recorded appeal outcomes. "
    "Record outcomes via /api/outcomes to build calibration data."
)

# Payer-violation CARC codes (mirrors app/agents/triage.PAYER_VIOLATION_CARC_CODES;
# kept local so the engine layer does not import agent modules).
_PAYER_VIOLATION_CARCS = {"PR-242", "CO-45", "CO-50", "CO-96", "PR-96", "CO-197", "CO-B16", "PR-1"}

BAND_HIGH = 0.70
BAND_MEDIUM = 0.45
BAND_LOW = 0.20
SCORE_FLOOR = 0.02
SCORE_CEILING = 0.95


@dataclass(frozen=True)
class SuccessFeatures:
    appeal_recommendation: str = "APPEAL"
    contradiction_strength: str = "NONE"
    contradiction_detected: bool = False
    triage_path: str = "PAYER_ILLEGAL_DENIAL"
    triage_confidence: str = "LOW"
    triage_method: str | None = None
    nsa_violation_detected: bool = False
    nsa_applies: bool = False
    denial_reason: str | None = None
    denial_carc_code: str | None = None
    is_emergency: bool = False
    appeal_framework: str | None = None
    days_remaining: int | None = None
    policy_indexed: bool = False
    grounding_score: float | None = None
    quality_gate_status: str | None = None
    letter_type: str = "payer_appeal"


@dataclass
class SuccessScore:
    score: float
    band: str
    factors: list[dict] = field(default_factory=list)
    hard_rule: str | None = None
    version: str = SCORER_VERSION
    calibration_note: str = CALIBRATION_NOTE

    def to_dict(self) -> dict:
        return asdict(self)


def _band(score: float) -> str:
    if score >= BAND_HIGH:
        return "HIGH"
    if score >= BAND_MEDIUM:
        return "MEDIUM"
    if score >= BAND_LOW:
        return "LOW"
    return "VERY_LOW"


def build_success_features(
    appeal_output: dict | None,
    claim_case: dict | None = None,
    cost_breakdown: dict | None = None,
    triage_decision: dict | None = None,
    contradiction_analysis: dict | None = None,
    policy_indexed: bool = False,
    quality_gate: dict | None = None,
) -> SuccessFeatures:
    ao = appeal_output if isinstance(appeal_output, dict) else {}
    cc = claim_case if isinstance(claim_case, dict) else {}
    cb = cost_breakdown if isinstance(cost_breakdown, dict) else {}
    td = triage_decision if isinstance(triage_decision, dict) else {}
    ca = contradiction_analysis if isinstance(contradiction_analysis, dict) else {}
    qg = quality_gate if isinstance(quality_gate, dict) else {}
    cv = ao.get("citation_verification") if isinstance(ao.get("citation_verification"), dict) else {}

    days = ao.get("days_remaining")
    try:
        days = int(days) if days is not None else None
    except (TypeError, ValueError):
        days = None

    grounding = cv.get("grounding_score")
    try:
        grounding = float(grounding) if grounding is not None else None
    except (TypeError, ValueError):
        grounding = None

    return SuccessFeatures(
        appeal_recommendation=str(ao.get("appeal_recommendation") or ca.get("appeal_recommendation") or "APPEAL").upper(),
        contradiction_strength=str(ao.get("contradiction_strength") or ca.get("contradiction_strength") or "NONE").upper(),
        contradiction_detected=bool(ao.get("contradiction_detected") or ca.get("is_contradiction")),
        triage_path=str(ao.get("triage_path") or td.get("path") or "PAYER_ILLEGAL_DENIAL").upper(),
        triage_confidence=str(ao.get("triage_confidence") or td.get("confidence") or "LOW").upper(),
        triage_method=td.get("triage_method"),
        nsa_violation_detected=bool(cb.get("nsa_violation_detected")),
        nsa_applies=bool(cc.get("nsa_applies")),
        denial_reason=(str(ao.get("denial_reason") or cc.get("denial_reason")).upper()
                       if (ao.get("denial_reason") or cc.get("denial_reason")) else None),
        denial_carc_code=(str(cc.get("denial_carc_code")).upper() if cc.get("denial_carc_code") else None),
        is_emergency=bool(cc.get("is_emergency")),
        appeal_framework=str(ao.get("appeal_framework")) if ao.get("appeal_framework") else None,
        days_remaining=days,
        policy_indexed=bool(policy_indexed),
        grounding_score=grounding,
        quality_gate_status=str(qg.get("status")) if qg.get("status") else None,
        letter_type=str(ao.get("letter_type") or "payer_appeal"),
    )


def compute_success_score(f: SuccessFeatures) -> SuccessScore:
    """Transparent point table. Every adjustment is recorded in factors."""
    factors: list[dict] = []

    def add(name: str, delta: float, note: str) -> None:
        factors.append({"factor": name, "delta": round(delta, 3), "note": note})

    # ── Provider correction path: its own (higher) base, fewer legal factors ──
    if f.triage_path == "PROVIDER_CODING_ERROR" or f.letter_type == "provider_correction":
        score = 0.60
        add("base_provider_correction", 0.60, "Billing corrections are routinely accepted once the error is identified")
        if f.triage_confidence == "HIGH":
            score += 0.15
            add("triage_confidence_high", 0.15, "Coding error identified with high confidence")
        elif f.triage_confidence == "LOW":
            score -= 0.10
            add("triage_confidence_low", -0.10, "Coding error is a low-confidence inference")
        if f.denial_carc_code:
            score += 0.05
            add("carc_present", 0.05, f"Specific CARC code {f.denial_carc_code} available to cite")
        if f.quality_gate_status == "WARN":
            score -= 0.05
            add("quality_gate_warn", -0.05, "Some claim facts were missing at drafting time")
        score = max(SCORE_FLOOR, min(SCORE_CEILING, round(score, 3)))
        return SuccessScore(score=score, band=_band(score), factors=factors)

    # ── Payer appeal path ──────────────────────────────────────────
    score = 0.35
    add("base_payer_appeal", 0.35, "Baseline for a formal appeal of an adverse benefit determination")

    strength_pts = {"STRONG": 0.30, "MODERATE": 0.15, "WEAK": 0.05}
    if f.contradiction_strength in strength_pts:
        pts = strength_pts[f.contradiction_strength]
        score += pts
        add(f"contradiction_{f.contradiction_strength.lower()}", pts,
            f"Policy Analyzer found a {f.contradiction_strength} contradiction in the plan document")

    if f.nsa_violation_detected or f.triage_method == "deterministic_nsa":
        score += 0.35
        add("nsa_violation", 0.35, "No Surprises Act protection applies — balance billing is prohibited by statute")
    elif f.nsa_applies:
        score += 0.15
        add("nsa_applies", 0.15, "Intake flagged NSA applicability (not independently confirmed by the cost engine)")

    if f.is_emergency and f.denial_reason == "PRIOR_AUTH_MISSING":
        score += 0.20
        add("emergency_prior_auth", 0.20, "Prior authorization cannot be required for emergency services")

    if f.denial_carc_code in _PAYER_VIOLATION_CARCS:
        score += 0.05
        add("payer_violation_carc", 0.05, f"CARC {f.denial_carc_code} is a recognised payer-side denial code")

    if f.triage_confidence == "HIGH":
        score += 0.05
        add("triage_confidence_high", 0.05, "Triage classified the denial with high confidence")
    elif f.triage_confidence == "LOW":
        score -= 0.05
        add("triage_confidence_low", -0.05, "Triage classification is low confidence")

    if f.appeal_framework == "STATE_EXTERNAL_REVIEW":
        score += 0.05
        add("binding_external_review", 0.05, "Independent external review is available and binding on the insurer")

    if not f.policy_indexed:
        score -= 0.10
        add("no_policy_document", -0.10, "No indexed policy document — no page-cited contradiction evidence")

    if f.grounding_score is not None and f.grounding_score < 0.5:
        score -= 0.10
        add("weak_citation_grounding", -0.10, "Fewer than half of the letter's citations could be verified")

    if f.quality_gate_status == "WARN":
        score -= 0.05
        add("quality_gate_warn", -0.05, "Some claim facts were missing at drafting time")

    # ── Hard rules (applied last) ──────────────────────────────────
    hard_rule = None
    caps = {"CLAIM_CORRECTLY_DENIED": 0.10, "UNLIKELY_TO_WIN": 0.20, "EXCEPTION_REQUEST": 0.60}
    if f.appeal_recommendation in caps and score > caps[f.appeal_recommendation]:
        add(f"cap_{f.appeal_recommendation.lower()}", caps[f.appeal_recommendation] - score,
            f"Policy Analyzer recommendation {f.appeal_recommendation} caps the score")
        score = caps[f.appeal_recommendation]
        hard_rule = f"CAP_{f.appeal_recommendation}"

    if f.days_remaining is not None and f.days_remaining <= 0:
        add("deadline_expired", SCORE_FLOOR - score, "The appeal deadline has passed")
        score = SCORE_FLOOR
        hard_rule = "DEADLINE_EXPIRED"

    score = max(SCORE_FLOOR, min(SCORE_CEILING, round(score, 3)))
    return SuccessScore(score=score, band=_band(score), factors=factors, hard_rule=hard_rule)


def attach_success_score(
    appeal_output: dict,
    claim_case: dict | None = None,
    cost_breakdown: dict | None = None,
    triage_decision: dict | None = None,
    contradiction_analysis: dict | None = None,
    policy_indexed: bool = False,
    quality_gate: dict | None = None,
) -> dict:
    """Return a copy of appeal_output with additive success_score* keys. Never raises."""
    out = dict(appeal_output or {})
    try:
        features = build_success_features(
            out, claim_case, cost_breakdown, triage_decision, contradiction_analysis, policy_indexed, quality_gate
        )
        result = compute_success_score(features)
        out["success_score"] = result.score
        out["success_score_band"] = result.band
        out["success_score_factors"] = result.factors
        out["success_score_version"] = result.version
        logger.info(f"Success scorer: {result.score} ({result.band}) hard_rule={result.hard_rule}")
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Success scorer failed (non-fatal): {e}", exc_info=True)
    return out
