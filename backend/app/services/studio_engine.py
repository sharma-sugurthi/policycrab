"""
Appeal Studio Engine — AI Co-Pilot revision service + evidence dossier compiler.

Two responsibilities:

1. apply_revision()
   Runs one of four one-click AI Co-Pilot rewrites against the current letter:
     - assertive         → Make Tone More Assertive
     - state_penalties   → Emphasize State Legal Penalties
     - simplify_online   → Simplify for Online Form Submission
     - medical_urgency   → Add Medical Urgency Context
   The LLM returns structured JSON {revised_letter, summary, focus_changes}.
   On any failure (rate limit, bad JSON, provider error) we return the ORIGINAL
   letter untouched with an error note — the Studio UI never loses the patient's work.

2. compile_dossier()
   Deterministic (no LLM) compilation of the evaluation result into a normalized
   DossierPackage. The frontend renders this as the official multi-page PDF.

Both functions are pure-ish (no FastAPI dependency) so they are unit-testable
with mocked LLMs.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage

from app.models.studio import RevisionRequest, RevisionResponse, DossierPackage, DossierSection
from app.services.llm_router import get_llm, TaskType, LLMRateLimitError

logger = logging.getLogger(__name__)

# ── Revision Type Registry ────────────────────────────────────────

REVISION_TYPES: dict[str, dict[str, str]] = {
    "assertive": {
        "label": "Make Tone More Assertive",
        "description": "Sharpen the language so the insurer understands this is being pursued seriously.",
        "instructions": (
            "Rewrite the appeal letter in a more assertive, confident, and demanding tone. "
            "Use strong verbs, direct declarative sentences, and explicit demands for corrective action "
            "(e.g. 'The denial must be reversed', 'I require a written response'). "
            "Keep every fact, name, date, dollar amount, page reference, and legal citation EXACTLY as-is. "
            "Do not add new legal claims. Do not become rude or abusive — remain professional but firm."
        ),
    },
    "state_penalties": {
        "label": "Emphasize State Legal Penalties",
        "description": "Foreground the insurer's regulatory exposure (state DOI fines, prompt-pay penalties).",
        "instructions": (
            "Rewrite the appeal letter to EMPHASIZE the state-specific legal penalties and consequences "
            "the insurer faces for non-compliance. Highlight: (1) the state's Unfair Claims Settlement "
            "Practices Act, (2) statutory prompt-payment penalties and interest, (3) the patient's right to "
            "file a formal complaint with the State Department of Insurance, and (4) that state DOI violations "
            "can trigger market-conduct examinations and monetary fines. Use the STATE CONTEXT provided below "
            "for accurate state-specific references. Keep all existing citations and facts intact. "
            "Add a 'CONSEQUENCES OF NON-COMPLIANCE' emphasis in the closing paragraphs."
        ),
    },
    "simplify_online": {
        "label": "Simplify for Online Form Submission",
        "description": "Condense the letter for web portals with character limits and plain-language readers.",
        "instructions": (
            "Rewrite the appeal letter so it fits comfortably in an online appeal form. "
            "Use shorter sentences and shorter paragraphs. Replace complex legal phrasing with plain, "
            "professional language an intake reviewer can scan quickly. Remove redundant boilerplate and "
            "repetitive emphasis. Target roughly 60-70% of the original length. "
            "Keep every material fact, dollar amount, CARC code, deadline, and legal citation intact. "
            "Keep a clear statement of the relief requested and the reason the denial is wrong."
        ),
    },
    "medical_urgency": {
        "label": "Add Medical Urgency Context",
        "description": "Add a clinical urgency section to request expedited review.",
        "instructions": (
            "Rewrite the appeal letter to add a 'MEDICAL URGENCY' section that explains why this care "
            "cannot be safely delayed and requests EXPEDITED review. Use ONLY the medical context provided "
            "below (procedure, diagnosis, date of service, emergency status). Do NOT fabricate symptoms, "
            "prognoses, or clinical outcomes. If the claim is an emergency service, emphasize the emergency "
            "nature and the statutory expedited-review obligation (45 CFR § 147.136 / ACA § 2719). "
            "Keep all existing facts and citations intact."
        ),
    },
}

REVISION_SYSTEM_PROMPT = """You are a senior patient-advocacy attorney polishing an appeal letter
drafted for a US health insurance claim. You make surgical edits only.

TASK: {instructions}

OUTPUT FORMAT — respond with a single JSON object:
{{
  "revised_letter": "The complete revised letter text, with all original content that was not intentionally changed preserved verbatim.",
  "summary": "One sentence describing what changed.",
  "focus_changes": ["2-5 concrete bullets describing the specific edits made"]
}}

RULES:
- NEVER change facts, dates, dollar amounts, statute names, or policy page numbers.
- NEVER fabricate medical facts or legal citations that were not provided.
- Preserve the formal letter structure (salutation, body, closing).
- Return ONLY the JSON object — no markdown fences, no commentary.
"""


# ── Context Builders (deterministic) ──────────────────────────────

def _build_case_context(request: RevisionRequest) -> str:
    """Serialize the available claim/plan/appeal context for the LLM prompt."""
    parts: list[str] = []
    pc = request.policy_profile or {}
    cc = request.claim_case or {}
    ao = request.appeal_output or {}

    plan_bits = [
        f"Plan: {pc.get('plan_name', 'Unknown')}",
        f"Carrier: {pc.get('carrier_name', 'Unknown')}",
        f"Plan Type: {pc.get('plan_type', 'Unknown')}",
        f"Legal Classification: {pc.get('legal_classification', 'Unknown')}",
        f"State: {pc.get('state') or 'XX'}",
    ]
    parts.append("PLAN CONTEXT:\n- " + "\n- ".join(plan_bits))

    claim_bits = []
    if cc.get("cpt_code"):
        claim_bits.append(f"Procedure: CPT {cc['cpt_code']} — {cc.get('cpt_description') or 'N/A'}")
    if cc.get("icd_10_code"):
        claim_bits.append(f"Diagnosis: ICD-10 {cc['icd_10_code']} — {cc.get('icd_10_description') or 'N/A'}")
    if cc.get("date_of_service"):
        claim_bits.append(f"Date of Service: {cc['date_of_service']}")
    if cc.get("billed_amount") is not None:
        claim_bits.append(f"Billed Amount: ${cc['billed_amount']:,.2f}")
    if cc.get("network_status"):
        claim_bits.append(f"Network Status: {cc['network_status']}")
    if cc.get("is_emergency"):
        claim_bits.append("Emergency Service: YES")
    if cc.get("denial_reason"):
        claim_bits.append(f"Denial Reason: {cc['denial_reason']}")
    if cc.get("denial_carc_code"):
        claim_bits.append(f"CARC Code: {cc['denial_carc_code']}")
    if cc.get("denial_date"):
        claim_bits.append(f"Denial Date: {cc['denial_date']}")
    parts.append("CLAIM CONTEXT:\n- " + "\n- ".join(claim_bits))

    appeal_bits = []
    if ao.get("appeal_framework"):
        appeal_bits.append(f"Appeal Framework: {ao['appeal_framework']}")
    if ao.get("appeal_deadline"):
        appeal_bits.append(f"Appeal Deadline: {ao['appeal_deadline']}")
    if ao.get("days_remaining") is not None:
        appeal_bits.append(f"Days Remaining: {ao['days_remaining']}")
    if ao.get("contradiction_detected"):
        appeal_bits.append(f"Policy Contradiction Detected: {ao.get('contradiction_strength', 'YES')}")
    if appeal_bits:
        parts.append("APPEAL CONTEXT:\n- " + "\n- ".join(appeal_bits))

    if request.eob_highlights:
        e = request.eob_highlights
        eob_bits = []
        for label, key in [
            ("Billed Amount", "billed_amount"),
            ("Allowed Amount", "allowed_amount"),
            ("Plan Paid", "plan_paid_amount"),
            ("Patient Responsibility", "patient_responsibility"),
            ("Denial Reason", "denial_reason_text"),
            ("CARC Code", "denial_carc_code"),
        ]:
            val = e.get(key)
            if val is not None:
                eob_bits.append(f"{label}: {val}")
        if eob_bits:
            parts.append("EOB HIGHLIGHTS:\n- " + "\n- ".join(eob_bits))

    return "\n\n".join(parts)


def _build_state_penalty_context(request: RevisionRequest) -> str:
    """
    State-specific regulatory context for the 'state_penalties' revision.
    Pulls the deterministic state profile (external review org, mandates).
    """
    state = (request.policy_profile or {}).get("state") or "XX"
    try:
        from app.engine.state_profiles import get_state_profile
        profile = get_state_profile(state)
    except Exception as e:
        logger.warning(f"Studio: state profile lookup failed for '{state}': {e}")
        return "STATE CONTEXT:\nNo state-specific profile available — use general Unfair Claims Settlement Practices Act and prompt-payment penalty references."

    mandates = "\n".join(f"  • {m}" for m in (profile.notable_mandates or [])[:4])
    return (
        f"STATE CONTEXT ({profile.state_name}):\n"
        f"- External Review Org: {profile.external_review_org}\n"
        f"- External Review Deadline: {profile.external_review_deadline_days} days\n"
        f"- State Surprise Billing Law: {profile.state_surprise_billing_law or 'None (federal NSA applies)'}\n"
        f"- Notable State Mandates:\n{mandates}"
    )


# ── LLM JSON parsing (shared with grievance agent pattern) ────────

def parse_llm_json(content: str) -> dict | None:
    """Extract a JSON object from an LLM response, tolerating fence markers."""
    if not content:
        return None
    text = content.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1]
        text = text.split("```", 1)[0]
    elif text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text.strip())
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError as e:
        logger.warning(f"Studio: LLM JSON parse failed: {e}")
        return None


# ── Revision Engine ───────────────────────────────────────────────

async def apply_revision(request: RevisionRequest) -> RevisionResponse:
    """
    Apply a single AI Co-Pilot revision to the letter.

    Resilient by design: if the LLM fails or returns unparseable output,
    we return the ORIGINAL letter with an explanatory error so the patient
    never loses their draft.
    """
    config = REVISION_TYPES.get(request.revision_type)
    if not config:
        return RevisionResponse(
            success=False,
            revision_type=request.revision_type,
            revised_letter=request.letter_text,
            errors=[f"Unknown revision type: {request.revision_type}"],
        )

    context = _build_case_context(request)
    if request.revision_type == "state_penalties":
        context += "\n\n" + _build_state_penalty_context(request)

    llm = get_llm(TaskType.LEGAL_WRITING, temperature=0.3)
    messages = [
        SystemMessage(content=REVISION_SYSTEM_PROMPT.format(instructions=config["instructions"])),
        HumanMessage(content=(
            f"{context}\n\n"
            f"CURRENT APPEAL LETTER:\n"
            f"\"\"\"\n{request.letter_text}\n\"\"\"\n\n"
            f"Apply the revision now and return the JSON object."
        )),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        data = parse_llm_json(content)

        if not data or not data.get("revised_letter"):
            # LLM returned something unusable — fall back to original.
            logger.warning(
                f"Studio: revision '{request.revision_type}' returned unusable output. "
                "Keeping original letter."
            )
            return RevisionResponse(
                success=False,
                revision_type=request.revision_type,
                revised_letter=request.letter_text,
                summary="The AI could not produce a clean revision. Your original letter was kept.",
                errors=["LLM returned unparseable output; original letter preserved."],
            )

        revised = str(data["revised_letter"]).strip()
        if not revised:
            return RevisionResponse(
                success=False,
                revision_type=request.revision_type,
                revised_letter=request.letter_text,
                errors=["Revision came back empty; original letter preserved."],
            )

        logger.info(
            f"Studio: revision '{request.revision_type}' applied — "
            f"{len(request.letter_text)} → {len(revised)} chars"
        )
        return RevisionResponse(
            success=True,
            revision_type=request.revision_type,
            revised_letter=revised,
            summary=str(data.get("summary") or config["label"]),
            focus_changes=[str(c) for c in data.get("focus_changes", []) if str(c).strip()],
        )

    except LLMRateLimitError as e:
        logger.warning(f"Studio: revision '{request.revision_type}' rate-limited — {e}")
        return RevisionResponse(
            success=False,
            revision_type=request.revision_type,
            revised_letter=request.letter_text,
            summary="All AI providers are temporarily rate-limited. Your original letter was kept.",
            errors=["AI providers rate-limited; original letter preserved."],
        )
    except Exception as e:
        logger.error(f"Studio: revision '{request.revision_type}' failed: {e}", exc_info=True)
        return RevisionResponse(
            success=False,
            revision_type=request.revision_type,
            revised_letter=request.letter_text,
            summary="The AI revision could not be completed. Your original letter was kept.",
            errors=[f"Revision failed: {e}"],
        )


# ── Dossier Compiler (deterministic) ──────────────────────────────

def _fmt_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def build_case_summary(evidence: dict) -> str:
    """One-paragraph patient-facing summary for the dossier cover page."""
    cc = evidence.get("claim_case") or {}
    cb = evidence.get("cost_breakdown") or {}
    ao = evidence.get("appeal_output") or {}

    procedure = f"CPT {cc.get('cpt_code')} — {cc.get('cpt_description') or 'procedure'}"
    if cc.get("icd_10_code"):
        procedure += f" (ICD-10 {cc['icd_10_code']})"

    billed = _fmt_money(cc.get("billed_amount") or cb.get("billed_amount"))
    patient_owes = _fmt_money(cb.get("total_patient_responsibility"))
    denial = (cc.get("denial_reason") or "Denied").replace("_", " ").title()
    carc = cc.get("denial_carc_code")
    if carc:
        denial += f" (CARC {carc})"

    summary = (
        f"This dossier documents the denial of a health insurance claim for {procedure}. "
        f"The provider billed {billed}. "
    )
    if patient_owes != "N/A":
        summary += f"The insurer assigned {patient_owes} in patient responsibility. "
    summary += (
        f"The claim was denied on the basis of {denial}. "
        f"Policy and regulatory evidence below shows why the denial is appealable under "
        f"{ao.get('appeal_framework') or 'the applicable legal framework'}."
    )
    if ao.get("contradiction_detected") and ao.get("policy_citations"):
        n = len(ao["policy_citations"])
        summary += (
            f" Specifically, {n} direct policy contradictio{'n' if n == 1 else 'ns'} "
            f"w{'as' if n == 1 else 'ere'} identified between the denial and the patient's own plan document."
        )
    return summary


def compile_dossier(evidence: dict) -> DossierPackage:
    """
    Compile raw evaluation output into a normalized DossierPackage.

    Deterministic — no LLM calls. Assembles the cover metadata, case summary,
    and ordered sections (letter, EOB highlights, policy citations, regulatory
    citations, next steps) that the frontend renders as the official PDF.
    """
    errors: list[str] = []
    cc = evidence.get("claim_case") or {}
    cb = evidence.get("cost_breakdown") or {}
    pc = evidence.get("policy_profile") or {}
    ao = evidence.get("appeal_output") or {}
    eob = evidence.get("eob_highlights") or {}

    # ── Cover metadata ────────────────────────────────────────────
    cover = {
        "title": "Health Insurance Appeal — Evidence Dossier",
        "subtitle": "Compiled by PolicyCrab",
        "plan_name": pc.get("plan_name") or ao.get("plan_name") or "Not specified",
        "carrier_name": pc.get("carrier_name") or "Not specified",
        "state": pc.get("state") or "XX",
        "plan_type": pc.get("plan_type") or "N/A",
        "legal_classification": pc.get("legal_classification") or "N/A",
        "appeal_framework": ao.get("appeal_framework") or "N/A",
        "appeal_deadline": ao.get("appeal_deadline"),
        "days_remaining": ao.get("days_remaining"),
        "estimated_success_probability": ao.get("estimated_success_probability"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "disclaimer": (
            "This dossier is an informational compilation generated by PolicyCrab. "
            "It is not legal or medical advice. Verify all citations and deadlines with "
            "your insurer and the relevant regulatory authority before submission."
        ),
    }

    case_summary = build_case_summary(evidence)

    # ── Section: Appeal Letter ────────────────────────────────────
    letter_text = (ao.get("appeal_letter") or "").strip()
    if not letter_text:
        errors.append("No appeal letter text was available to include in the dossier.")
    letter_section = DossierSection(
        id="letter",
        title="Appeal Letter",
        body=letter_text or "— No letter text available —",
    )

    # ── Section: EOB Highlights ───────────────────────────────────
    eob_items: list[dict] = []
    eob_sources = [("EOB", eob), ("Claim", cc), ("Cost Breakdown", cb)]
    eob_fields = [
        ("date_of_service", "Date of Service"),
        ("billed_amount", "Billed Amount"),
        ("allowed_amount", "Allowed Amount"),
        ("total_patient_responsibility", "Patient Responsibility"),
        ("total_insurer_payout", "Insurer Payout"),
        ("denial_carc_code", "CARC Code"),
        ("denial_reason_text", "Denial Reason"),
        ("denial_date", "Denial Date"),
        ("network_status", "Network Status"),
        ("facility_network_status", "Facility Network Status"),
        ("ancillary_service_type", "Ancillary Service Type"),
    ]
    for key, label in eob_fields:
        value = None
        for source_name, source in eob_sources:
            raw = source.get(key)
            if raw not in (None, "", "null"):
                value = raw
                break
        if value is None:
            continue
        if key in ("billed_amount", "allowed_amount", "total_patient_responsibility", "total_insurer_payout"):
            value = _fmt_money(value)
        eob_items.append({"label": label, "value": value})

    if cb.get("nsa_violation_detected"):
        eob_items.append({
            "label": "NSA Balance Billing Violation",
            "value": f"Illegal balance-billed amount: {_fmt_money(cb.get('illegal_balance_billed_amount'))}",
        })

    eob_section = DossierSection(
        id="eob",
        title="Explanation of Benefits (EOB) Highlights",
        items=eob_items,
    )

    # ── Section: Policy Contradictions ────────────────────────────
    policy_items: list[dict] = []
    for c in ao.get("policy_citations") or []:
        if not isinstance(c, dict):
            continue
        policy_items.append({
            "page_number": c.get("page_number"),
            "section": c.get("section", "Policy Document"),
            "exact_clause_text": c.get("exact_clause_text") or "",
            "contradiction_explanation": c.get("contradiction_explanation") or "",
            "insurer_mistake": c.get("insurer_mistake") or "",
        })
    policy_section = DossierSection(
        id="policy",
        title="Policy Contradiction Citations",
        items=policy_items,
    )

    # ── Section: Regulatory Citations ─────────────────────────────
    reg_items: list[dict] = []
    for r in ao.get("cited_regulations") or []:
        if not isinstance(r, dict):
            continue
        reg_items.append({
            "statute": r.get("statute") or "Unknown",
            "description": r.get("description") or "",
            "relevance": r.get("relevance") or "",
        })
    reg_section = DossierSection(
        id="regulations",
        title="Cited Regulations & Precedents",
        items=reg_items,
    )

    # ── Section: Recommended Next Steps ───────────────────────────
    steps = [s for s in (ao.get("recommended_next_steps") or []) if isinstance(s, str) and s.strip()]
    if not steps and ao.get("triage_action_summary"):
        steps = [ao["triage_action_summary"]]
    next_steps_section = DossierSection(
        id="next_steps",
        title="Recommended Next Steps",
        items=steps,
    )

    sections = [letter_section, eob_section, policy_section, reg_section, next_steps_section]

    # ── Totals ────────────────────────────────────────────────────
    totals = {
        "letter_word_count": len(letter_text.split()) if letter_text else 0,
        "eob_highlight_count": len(eob_items),
        "policy_citation_count": len(policy_items),
        "regulatory_citation_count": len(reg_items),
        "next_step_count": len(steps),
        "section_count": len(sections),
        # Rough page estimate: ~400 words per page for the letter + 1 cover
        # + 0.5 page per evidence section, rounded up.
        "page_estimate": max(
            2,
            1 + (len(letter_text.split()) // 400) + (1 if eob_items else 0)
            + (1 if policy_items else 0) + (1 if reg_items else 0) + (1 if steps else 0),
        ),
    }

    return DossierPackage(
        success=True,
        generated_at=cover["generated_at"],
        cover=cover,
        case_summary=case_summary,
        sections=sections,
        totals=totals,
        errors=errors,
    )
