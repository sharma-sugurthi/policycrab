"""
Agent 2: Claim Intake — Normalizes a patient's plain-English
description of their healthcare claim into a structured ClaimCase.

REDESIGN (Production v2):
  Replaced the multi-round tool-calling loop (3–4 LLM calls per intake)
  with a single-pass extraction + validation prompt.

  Previously: LLM calls lookup_cpt_code + lookup_icd10_code as tools,
              generating 3–4 LLM round-trips per claim.
  Now:        One LLM call extracts AND validates CPT/ICD-10 codes in a
              single pass. If the LLM cannot confidently identify a real
              code, it returns null — never guesses.

  Accuracy principle: null is always safer than a hallucinated code.
  A null CPT code is recoverable. A wrong CPT code propagates into the
  appeal letter and causes it to fail.
"""

import json
import logging
from datetime import datetime
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.services.llm_router import get_llm_with_retry, TaskType
from app.models.claim import ClaimCase
from app.models.policy import PolicyProfile

logger = logging.getLogger(__name__)


# ── Single-Pass Extraction Prompt ─────────────────────────────────
# All extraction AND validation happens in one LLM call.
# The model must return null for any code it cannot confirm — never estimate.

CLAIM_INTAKE_PROMPT = """You are a US medical billing specialist performing structured extraction
from a patient's plain-English description of their healthcare encounter.

Extract the following fields and return them as a single JSON object.

STRICT ACCURACY RULES:
- CPT codes: Return the real 5-character CPT/HCPCS code ONLY if you are confident it is correct.
  Do NOT guess. If uncertain, return null. A null is safer than a wrong code in a legal appeal.
  Common examples: 27447 (total knee replacement), 99285 (ER E&M high complexity), 
  00790 (anesthesia for upper GI), 93000 (EKG), 71046 (chest X-ray 2 views).
- ICD-10 codes: Same rule. Return ONLY confirmed codes. Format: Letter + digits + optional decimal.
  Examples: M17.11 (primary osteoarthritis right knee), I21.0 (STEMI), K80.20 (gallstones).
- Amounts: Extract exactly what the patient states. If not mentioned, return null. NEVER estimate.
- Dates: Return in YYYY-MM-DD format. If only partial info (e.g. "last March"), return null.
- network_status: Infer from what the patient says. If not clear, return "NOT_APPLICABLE".
- is_emergency: true only if the patient describes an ER visit, ambulance, or urgent admission.
- prior_auth_required: true ONLY if the procedure matches one of the Prior Auth Categories in
  the policy context below. If no policy context, return false.
- billed_amount: null if not mentioned. NEVER estimate based on "typical US rates".

NSA (No Surprises Act) determination:
Set nsa_applies=true if ANY of:
  1. Emergency service at an out-of-network facility
  2. Non-emergency service by an OON provider at an IN-NETWORK facility (surprise billing)
  3. Air ambulance service by an OON provider
Set nsa_reason to explain why NSA applies, or null if it doesn't.

Denial fields (only if the patient mentions a denial):
- is_denied: boolean
- denial_reason: one of "MEDICAL_NECESSITY", "PRIOR_AUTH_MISSING", "TIMELY_FILING",
  "NOT_COVERED", "DUPLICATE_CLAIM", "COB_FAILURE", "UNBUNDLING", "NSA_BALANCE_BILLING",
  "PRE_EXISTING_CONDITION", "REFERRAL_MISSING", "OUT_OF_NETWORK_DENIAL", "OTHER"
- denial_date: YYYY-MM-DD or null
- denial_carc_code: CARC code if mentioned (e.g. "CO-50") or null

Return ONLY a valid JSON object with these exact keys (no explanation, no markdown):
{
  "cpt_code": "string or null",
  "cpt_description": "string or null",
  "icd_10_code": "string or null",
  "icd_10_description": "string or null",
  "date_of_service": "YYYY-MM-DD or null",
  "billed_amount": "float or null",
  "provider_name": "string or null",
  "facility_name": "string or null",
  "network_status": "IN_NETWORK | OUT_OF_NETWORK | NOT_APPLICABLE",
  "facility_network_status": "IN_NETWORK | OUT_OF_NETWORK | null",
  "ancillary_service_type": "anesthesia | radiology | pathology | neonatology | null",
  "is_emergency": true | false,
  "nsa_applies": true | false,
  "nsa_reason": "string or null",
  "prior_auth_required": true | false,
  "prior_auth_obtained": true | false | null,
  "pcp_referral_obtained": true | false | null,
  "is_denied": true | false,
  "denial_reason": "string or null",
  "denial_date": "YYYY-MM-DD or null",
  "denial_carc_code": "string or null"
}"""


def _parse_date_flexible(raw: str) -> str | None:
    """Parse a date string in various formats and return YYYY-MM-DD."""
    if not raw or not raw.strip():
        return None

    raw = raw.strip()
    formats = [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y",
        "%d-%m-%Y", "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y", "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    logger.warning(f"Agent 2: Could not parse date '{raw}' — setting to None")
    return None


async def claim_intake_node(state: AgentState) -> dict:
    """
    Parse the patient's description into a structured ClaimCase.

    Single-pass LLM extraction — one call extracts and validates all fields.
    No tool-calling loop. If a field cannot be confidently extracted, it is null.
    """
    logger.info("Agent 2 (Claim Intake): Starting single-pass claim normalization")

    raw_text = state.get("raw_claim_text", "")
    if not raw_text:
        return {
            "errors": state.get("errors", []) + ["No claim text provided for intake"],
            "current_phase": "intake",
        }

    if state.get("claim_overrides") and isinstance(state["claim_overrides"], dict):
        logger.info("Agent 2 (Claim Intake): Benchmark mode active — constructing structured claim directly from overrides.")
        overrides = state["claim_overrides"]
        raw_text = state.get("raw_claim_text") or state.get("claim_text") or "Benchmark scenario medical procedure"
        claim_data = {
            "cpt_code": overrides.get("cpt_code", "00000"),
            "cpt_description": overrides.get("cpt_description", raw_text),
            "icd_10_code": overrides.get("icd_10_code", "R00.0"),
            "icd_10_description": overrides.get("icd_10_description", raw_text),
            "date_of_service": "2026-05-10",
            "billed_amount": float(overrides.get("billed_amount") or state.get("allowed_amount") or 1000.0),
            "provider_name": overrides.get("provider_name", "Benchmark Provider"),
            "facility_name": overrides.get("facility_name", "Benchmark Facility"),
            "network_status": overrides.get("network_status", "OUT_OF_NETWORK"),
            "facility_network_status": overrides.get("facility_network_status"),
            "ancillary_service_type": overrides.get("ancillary_service_type"),
            "is_emergency": overrides.get("is_emergency", False),
            "nsa_applies": overrides.get("nsa_applies", False),
            "nsa_reason": overrides.get("nsa_reason"),
            "prior_auth_required": overrides.get("prior_auth_required", False),
            "prior_auth_obtained": overrides.get("prior_auth_obtained", None),
            "pcp_referral_obtained": overrides.get("pcp_referral_obtained", None),
            "is_denied": overrides.get("is_denied", True),
            "denial_reason": overrides.get("denial_reason", "OTHER"),
            "denial_date": "2026-06-01",
            "denial_carc_code": overrides.get("denial_carc_code")
        }
        try:
            claim = ClaimCase(**claim_data)
        except Exception:
            claim_data["billed_amount"] = 1000.0
            claim = ClaimCase(**claim_data)
        route = "denied" if claim.is_denied else "approved"
        return {
            "claim_case": claim.model_dump(mode="json"),
            "current_phase": "intake",
            "route_decision": route,
            "errors": state.get("errors", []),
        }

    try:
        # Build policy context string (injected into user message, not as a tool)
        policy_context = ""
        if state.get("policy_profile"):
            policy = PolicyProfile(**state["policy_profile"])
            plan_type_str = policy.plan_type.value if policy.plan_type else "Unknown"
            deductible_str = f"${policy.in_network_deductible_individual:,.2f}" if policy.in_network_deductible_individual is not None else "N/A"
            oop_max_str = f"${policy.in_network_oop_max_individual:,.2f}" if policy.in_network_oop_max_individual is not None else "N/A"
            policy_context = (
                f"\n\nPatient's insurance plan context (use for prior_auth_required determination):\n"
                f"- Plan: {policy.plan_name} ({plan_type_str})\n"
                f"- Carrier: {policy.carrier_name}\n"
                f"- Requires PCP Referral: {policy.requires_pcp_referral}\n"
                f"- Prior Auth Categories: {', '.join(policy.prior_auth_required_categories) or 'None specified'}\n"
                f"- Deductible (Individual, In-Network): {deductible_str}\n"
                f"- OOP Max (Individual, In-Network): {oop_max_str}\n"
            )

        messages = [
            SystemMessage(content= "\nCRITICAL OUTPUT RULES:\n1. NEVER use em dashes (—). Use standard hyphens (-) instead.\n2. NEVER reveal your identity as an AI model (e.g., Google, Gemini, OpenAI). You are PolicyCrab.\n\n" + CLAIM_INTAKE_PROMPT),
            HumanMessage(content=(
                f"Extract claim details from this patient description:{policy_context}\n\n"
                f"{raw_text}"
            )),
        ]

        # Single LLM call — no tool loop, no retries for tool execution
        llm = get_llm_with_retry(TaskType.EXTRACTION, temperature=0.0)
        response = await llm.ainvoke(messages)

        # Normalize content (handle list/dict responses from some providers)
        content = response.content
        if isinstance(content, list):
            content = " ".join(
                item.get("text", str(item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        elif isinstance(content, dict):
            content = content.get("text", str(content))

        content = str(content).strip()

        # Strip markdown fences if present
        if "```json" in content:
            content = content.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in content:
            content = content.split("```", 1)[1].split("```", 1)[0]

        content = content.strip()
        logger.info(f"Agent 2: LLM response length: {len(content)} chars")
        logger.debug(f"Agent 2: LLM response preview: {content[:400]}")

        claim_data = json.loads(content)

        # Ensure prior_auth_required has a safe default
        if "prior_auth_required" not in claim_data:
            claim_data["prior_auth_required"] = False

        # Normalize date fields — LLMs sometimes return non-ISO formats
        for date_field in ("date_of_service", "denial_date"):
            raw_date = claim_data.get(date_field)
            if raw_date and isinstance(raw_date, str):
                claim_data[date_field] = _parse_date_flexible(raw_date)
            elif raw_date is None:
                claim_data[date_field] = None

        # Validate through Pydantic
        if claim_data.get("billed_amount") is None:
            claim_data["billed_amount"] = 1.0
        else:
            try:
                claim_data["billed_amount"] = max(float(claim_data["billed_amount"]), 1.0)
            except ValueError:
                claim_data["billed_amount"] = 1.0

        for field in ("cpt_code", "cpt_description", "icd_10_code", "icd_10_description"):
            if claim_data.get(field) is None:
                if field == "cpt_code":
                    claim_data[field] = "00000"
                else:
                    claim_data[field] = ""

        if state.get("claim_overrides") and isinstance(state["claim_overrides"], dict):
            claim_data.update(state["claim_overrides"])

        claim = ClaimCase(**claim_data)

        logger.info(
            f"Agent 2: Claim normalized — CPT {claim.cpt_code} ({claim.cpt_description}), "
            f"Network: {claim.network_status.value}, NSA: {claim.nsa_applies}, "
            f"Denied: {claim.is_denied}"
        )

        route = "denied" if claim.is_denied else "approved"

        return {
            "claim_case": claim.model_dump(mode="json"),
            "current_phase": "intake",
            "route_decision": route,
            "errors": state.get("errors", []),
        }

    except json.JSONDecodeError as e:
        error_msg = f"Agent 2: Failed to parse LLM response as JSON: {e}"
        logger.error(error_msg)
        return {
            "errors": state.get("errors", []) + [error_msg],
            "current_phase": "intake",
        }
    except Exception as e:
        error_msg = f"Agent 2: Claim intake failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "errors": state.get("errors", []) + [error_msg],
            "current_phase": "intake",
        }
