"""
Extraction Quality Gate — deterministic completeness check before drafting.

Pure logic, no LLM. Looks at the structured claim the intake agent produced (and,
when available, the raw EOB extraction with per-field confidence) and answers:
"Do we actually know enough to write a legally grounded appeal, or would the LLM
be filling gaps with guesses?"

Sentinel awareness — claim_intake.py substitutes these when data is missing:
    billed_amount -> 1.0          cpt_code -> "00000"
    denial_date  -> None          (grievance then uses date.today(), inflating days_remaining)
    denial_reason -> "OTHER"
The gate treats each sentinel as "missing".

Severity:
    CRITICAL   — drafting on this gap produces a materially wrong letter
                 (wrong deadline, wrong legal framework, unreconciled dollars)
    IMPORTANT  — weakens the letter / forces the LLM to guess triage inputs
    NICE_TO_HAVE — reduces depth (e.g. no document-level contradiction analysis)

Status:
    PASS  — nothing missing
    WARN  — something missing; drafting proceeds with placeholders (default mode)
    BLOCK — a CRITICAL field is missing AND mode == "block"
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

QUALITY_GATE_VERSION = "v1"

CRITICAL = "CRITICAL"
IMPORTANT = "IMPORTANT"
NICE_TO_HAVE = "NICE_TO_HAVE"

# Sentinels written by claim_intake when the LLM could not extract a value.
BILLED_AMOUNT_SENTINEL = 1.0
CPT_SENTINEL = "00000"

# EOB extraction confidence keys we care about (pdf_extractor GEMINI_EOB_EXTRACTION_PROMPT).
EOB_CRITICAL_CONFIDENCE_FIELDS = ("billed_amount", "denial_carc_code", "network_status", "date_of_service")


@dataclass(frozen=True)
class ChecklistItem:
    field: str
    severity: str
    why_it_matters: str
    where_to_find_it: str
    current_value: str | None = None
    confidence: str | None = None


@dataclass
class QualityGateResult:
    status: str                                   # PASS | WARN | BLOCK
    mode: str                                     # off | warn | block
    critical_missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_information_checklist: list[ChecklistItem] = field(default_factory=list)
    field_confidence: dict[str, str] = field(default_factory=dict)
    completeness_score: float = 1.0
    version: str = QUALITY_GATE_VERSION

    def to_dict(self) -> dict:
        d = asdict(self)
        d["missing_information_checklist"] = [asdict(i) for i in self.missing_information_checklist]
        return d


def _passing(mode: str) -> QualityGateResult:
    return QualityGateResult(status="PASS", mode=mode)


def _s(value) -> str | None:
    return None if value is None else str(value)


def _is_missing_amount(value) -> bool:
    try:
        return value is None or float(value) <= BILLED_AMOUNT_SENTINEL
    except (TypeError, ValueError):
        return True


def evaluate_quality_gate(
    claim_case: dict | None,
    policy_profile: dict | None,
    eob_extraction: dict | None,
    policy_indexed: bool,
    route_decision: str,
    mode: str = "warn",
    benchmark_mode: bool = False,
) -> QualityGateResult:
    """Deterministic completeness evaluation. Never raises on malformed input."""
    mode = (mode or "warn").lower()
    if mode == "off" or benchmark_mode:
        # Benchmark cases construct claims from ground-truth overrides (dates/amounts always set).
        return _passing(mode)

    claim = claim_case if isinstance(claim_case, dict) else {}
    policy = policy_profile if isinstance(policy_profile, dict) else {}
    eob = eob_extraction if isinstance(eob_extraction, dict) else {}
    eob_conf = eob.get("confidence") if isinstance(eob.get("confidence"), dict) else {}

    items: list[ChecklistItem] = []
    is_denied = bool(claim.get("is_denied")) or route_decision == "denied"

    # ── Claim-level checks ────────────────────────────────────────
    if _is_missing_amount(claim.get("billed_amount")):
        items.append(ChecklistItem(
            field="billed_amount", severity=CRITICAL,
            why_it_matters="Cost-sharing math and the amount in dispute cannot be stated without it.",
            where_to_find_it="EOB / itemized bill: 'Amount Billed' or 'Provider Charges' column.",
            current_value=_s(claim.get("billed_amount")), confidence=eob_conf.get("billed_amount"),
        ))

    if not claim.get("cpt_code") or str(claim.get("cpt_code")) == CPT_SENTINEL:
        items.append(ChecklistItem(
            field="cpt_code", severity=IMPORTANT,
            why_it_matters="Identifies the exact service; needed for coding-error triage and copay category.",
            where_to_find_it="EOB service line 'Procedure' / 'CPT' column, or the itemized bill.",
            current_value=_s(claim.get("cpt_code")), confidence=eob_conf.get("cpt_code"),
        ))

    if is_denied:
        if not claim.get("denial_date"):
            items.append(ChecklistItem(
                field="denial_date", severity=CRITICAL,
                why_it_matters=(
                    "The appeal deadline is counted from this date. Without it the pipeline "
                    "assumes 'today', which overstates the days remaining."
                ),
                where_to_find_it="Top of the denial letter / Adverse Benefit Determination notice, or the EOB issue date.",
                current_value=None, confidence=eob_conf.get("date_of_service"),
            ))
        if not claim.get("denial_carc_code"):
            items.append(ChecklistItem(
                field="denial_carc_code", severity=IMPORTANT,
                why_it_matters=(
                    "CARC codes route the case deterministically (provider error vs payer violation) "
                    "and anchor legal citations."
                ),
                where_to_find_it="EOB 'Claim Adjustment Reason Code' / 'Remark Code' column (e.g. CO-50, PR-242).",
                current_value=None, confidence=eob_conf.get("denial_carc_code"),
            ))
        if not claim.get("denial_reason") or str(claim.get("denial_reason")).upper() == "OTHER":
            items.append(ChecklistItem(
                field="denial_reason", severity=IMPORTANT,
                why_it_matters="Selects the denial-specific policy queries, legal arguments and RAG retrieval.",
                where_to_find_it=(
                    "Denial letter: the stated reason (medical necessity, not covered, prior auth, network, etc.)."
                ),
                current_value=_s(claim.get("denial_reason")),
            ))

    if str(claim.get("network_status") or "").upper() == "NOT_APPLICABLE" and not claim.get("is_emergency"):
        items.append(ChecklistItem(
            field="network_status", severity=IMPORTANT,
            why_it_matters="Determines deductible/coinsurance tier and whether No Surprises Act protections apply.",
            where_to_find_it="EOB 'Network' / 'Participating Provider' indicator, or the carrier provider directory.",
            current_value=_s(claim.get("network_status")), confidence=eob_conf.get("network_status"),
        ))

    # ── Policy-level checks ───────────────────────────────────────
    if not policy.get("legal_classification"):
        items.append(ChecklistItem(
            field="legal_classification", severity=CRITICAL,
            why_it_matters=(
                "Decides the appeal framework (ERISA vs state external review vs Medicare/Medicaid); "
                "the wrong framework means the wrong deadline and the wrong addressee."
            ),
            where_to_find_it="SBC page 1 / plan documents: 'self-funded' or 'insured by' language; HR benefits office.",
            current_value=None,
        ))
    if not policy.get("state"):
        items.append(ChecklistItem(
            field="state", severity=IMPORTANT,
            why_it_matters="State determines external review deadlines, surprise-billing law and DOI contact.",
            where_to_find_it="Policy cover page / SBC header (state of issue), or the member ID card.",
            current_value=None,
        ))

    if not policy_indexed:
        items.append(ChecklistItem(
            field="policy_document", severity=NICE_TO_HAVE,
            why_it_matters="Without the indexed policy PDF no page-cited contradiction analysis is possible.",
            where_to_find_it="Upload the full plan document (SBC/EOC) on the Policy page.",
            current_value=None,
        ))

    # ── EOB extraction checks (only when the caller supplied it) ──
    if eob:
        low = [f for f in EOB_CRITICAL_CONFIDENCE_FIELDS if str(eob_conf.get(f, "")).lower() == "low"]
        for f in low:
            if any(i.field == f for i in items):
                continue
            items.append(ChecklistItem(
                field=f, severity=IMPORTANT,
                why_it_matters="The document reader was not confident in this value; confirm it before relying on it.",
                where_to_find_it="Re-check the original EOB / bill for this field.",
                current_value=_s(eob.get(f)), confidence="low",
            ))
        math_errors = eob.get("validation_errors")
        if isinstance(math_errors, list) and math_errors:
            items.append(ChecklistItem(
                field="eob_math", severity=CRITICAL,
                why_it_matters="Billed / allowed / paid / patient-responsibility amounts do not reconcile: "
                               + "; ".join(str(e) for e in math_errors[:3]),
                where_to_find_it="EOB totals row — confirm allowed <= billed and plan paid + patient share = allowed.",
                current_value=None,
            ))

    # ── Aggregate ─────────────────────────────────────────────────
    critical = [i.field for i in items if i.severity == CRITICAL]
    warnings = [f"{i.severity}: {i.field}" for i in items if i.severity != NICE_TO_HAVE]

    weights = {CRITICAL: 0.3, IMPORTANT: 0.1, NICE_TO_HAVE: 0.05}
    completeness = max(0.0, round(1.0 - sum(weights[i.severity] for i in items), 3))

    if critical and mode == "block":
        status = "BLOCK"
    elif items and any(i.severity != NICE_TO_HAVE for i in items):
        status = "WARN"
    else:
        status = "PASS"

    field_confidence = {k: str(v) for k, v in eob_conf.items()} if eob_conf else {}

    return QualityGateResult(
        status=status,
        mode=mode,
        critical_missing=critical,
        warnings=warnings,
        missing_information_checklist=items,
        field_confidence=field_confidence,
        completeness_score=completeness,
    )


def render_checklist_text(gate: dict | None) -> str:
    """Plain-English checklist used by explain_blocked (no LLM)."""
    gate = gate or {}
    items = gate.get("missing_information_checklist") or []
    if not items:
        return "The claim information looks complete."
    lines = [
        "We paused before drafting your appeal because some key facts are missing. "
        "Adding them will make the letter accurate and enforceable.",
        "",
    ]
    order = {CRITICAL: 0, IMPORTANT: 1, NICE_TO_HAVE: 2}
    for n, item in enumerate(sorted(items, key=lambda i: order.get(i.get("severity"), 9)), start=1):
        lines.append(f"{n}. {str(item.get('field', '')).replace('_', ' ').title()} ({item.get('severity')})")
        lines.append(f"   Why it matters: {item.get('why_it_matters', '')}")
        lines.append(f"   Where to find it: {item.get('where_to_find_it', '')}")
    lines.append("")
    lines.append("Add the missing details to your claim description or upload the EOB, then run the evaluation again.")
    return "\n".join(lines)
