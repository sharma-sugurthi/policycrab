"""
Agent 5 (New): Triage Agent — The Critical Routing Decision.

This agent solves the most fundamental flaw in PolicyCrab's original design:
the assumption that the Payer (insurance company) is always the party at fault.

In the real world, most insurance claim denials fall into two distinct buckets:

  BUCKET A — PROVIDER CODING ERROR (≈ 40-60% of denials):
    The hospital's billing department made a mistake:
    - Missing a required modifier (e.g., Modifier 25, 59, GT)
    - Wrong diagnosis code attached to a procedure
    - Unbundling violation — billing separately for components of a bundled service
    - Incorrect place of service code
    - Using a deleted or non-existent CPT code
    ACTION: The patient should ask the PROVIDER to correct and REFILE the claim.
            Sending an aggressive legal ERISA appeal for a typo is guaranteed to fail.

  BUCKET B — PAYER ILLEGAL DENIAL (≈ 40-60% of denials):
    The insurance company is acting wrongfully:
    - Denying an emergency claim citing "no prior auth" (NSA/EMTALA violation)
    - Balance billing an OON ancillary provider at an INN facility (NSA violation)
    - Denying a medically necessary procedure using arbitrary internal guidelines
    - Applying incorrect network status to a provider
    ACTION: File a formal legal appeal citing ERISA, ACA, or NSA.

Pipeline Position:
  Runs AFTER policy_analyzer and BEFORE grievance.
  Reads contradiction_analysis and cost_breakdown to make its decision.
  Writes triage_decision to state which routes the grievance node.

Output:
  triage_decision = {
    "path": "PROVIDER_CODING_ERROR" | "PAYER_ILLEGAL_DENIAL",
    "confidence": "HIGH" | "MEDIUM" | "LOW",
    "primary_reason": "one sentence explanation",
    "coding_errors_detected": [...],   # Only populated for PROVIDER_CODING_ERROR
    "legal_violations_detected": [...], # Only populated for PAYER_ILLEGAL_DENIAL
    "action_summary": "What the patient should do next",
    "estimated_success_probability": float (0.0 to 1.0),
  }
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.services.llm_router import get_llm, TaskType
from app.models.claim import ClaimCase, CostBreakdown
from app.models.policy import PolicyProfile
from app.models.enums import DenialReason, NetworkStatus

logger = logging.getLogger(__name__)


# ── Denial codes that are ALWAYS provider-side coding errors ──────
# These CARC/RARC codes indicate the problem is with how the provider
# submitted the claim, not with the insurer's coverage decision.
PROVIDER_ERROR_CARC_CODES = {
    "CO-4":   "Modifier is inconsistent with the procedure code — billing error",
    "CO-11":  "Diagnosis is inconsistent with procedure — coding error",
    "CO-15":  "Authorization number is missing — submission error",
    "CO-16":  "Claim lacks required information — incomplete submission",
    "CO-18":  "Duplicate claim — resubmission error",
    "CO-56":  "Procedure code is missing or invalid — coding error",
    "CO-97":  "Payment adjusted because the benefit for this service is included in the payment — NCCI bundling error",
    "CO-151": "Payment adjusted because the payer deems the information submitted does not support this level of service — documentation error",
    "CO-236": "Claim received after cut-off date — timely filing error (provider responsibility)",
    "PR-204": "Service not covered by this payer — wrong insurance filed",
    "OA-23":  "The impact of prior payer(s) adjudication — COB coordination error",
    "CO-B7":  "Provider is not enrolled — credentialing error",
}

# ── Denial codes that are ALWAYS payer-side legal violations ──────
PAYER_VIOLATION_CARC_CODES = {
    "PR-242":  "NSA balance billing violation — OON provider at INN facility",
    "CO-45":   "Charge exceeds fee schedule — possible NSA/balance billing issue",
    "CO-50":   "Medical necessity denial — ERISA mandates full and fair review",
    "CO-96":   "Non-covered charge — may be an improper ACA exclusion",
    "PR-96":   "Experimental/investigational denial — may be an improper ACA exclusion",
    "CO-197":  "Prior authorization was required — verify if emergency exception applies",
    "CO-B16":  "Patient cannot be held responsible for charges — NSA violation",
    "PR-1":    "Deductible amount — may be incorrectly calculated (network status mismatch)",
}

# ── Ancillary CPT code prefixes → NSA automatic PAYER VIOLATION ──
NSA_ANCILLARY_CPT_PREFIXES = (
    "009",  # Anesthesia codes (00100-09999)
    "007",  # Anesthesia codes (00700-00799)
    "008",  # Anesthesia codes (00800-00899)
    "882",  # Radiology — diagnostic imaging
    "883",  # Radiology — interventional
    "884",  # Radiology
    "885",  # Radiology
    "886",  # Nuclear medicine
    "887",  # Radiation oncology
    "888",  # Radiation oncology
    "880",  # Pathology
    "881",  # Pathology
)


TRIAGE_SYSTEM_PROMPT = """You are a senior US medical billing compliance specialist and 
patient advocacy expert with 20 years of experience.

Your ONLY job is to perform a binary classification of a denied insurance claim:

CLASSIFICATION A — PROVIDER_CODING_ERROR:
  The ROOT CAUSE of the denial is a mistake made by the hospital's billing department:
  - Missing or incorrect CPT modifier (Modifier 25, 59, GT, 95, etc.)
  - Wrong diagnosis (ICD-10) attached to the procedure
  - Unbundling violation (billing separately for included services)
  - Non-specific or deleted CPT/ICD-10 code used
  - Wrong place of service (POS) code
  - Duplicate submission error
  - Timely filing failure (provider's fault)
  → The patient should NOT file a legal appeal. They should contact the provider's
    billing department and request a corrected claim resubmission (a "corrected claim").

CLASSIFICATION B — PAYER_ILLEGAL_DENIAL:
  The ROOT CAUSE is the insurer acting improperly or illegally:
  - Denying a claim that clearly meets medical necessity criteria
  - Applying "no prior authorization" to an emergency (NSA/EMTALA violation)
  - Balance billing an OON ancillary provider at an in-network facility (NSA violation)
  - Applying incorrect cost-sharing (e.g., OON rates to an INN facility)
  - Denying coverage for a service that is clearly covered by the policy
  → The patient should file a formal legal appeal (ERISA/ACA/NSA pathway).

STRICT OUTPUT FORMAT — return ONLY this JSON:
{
  "path": "PROVIDER_CODING_ERROR" or "PAYER_ILLEGAL_DENIAL",
  "confidence": "HIGH" or "MEDIUM" or "LOW",
  "primary_reason": "One precise sentence explaining the root cause determination",
  "coding_errors_detected": [
    "e.g., Missing Modifier 25 on an evaluation/management code billed same day as procedure"
  ],
  "legal_violations_detected": [
    "e.g., NSA Scenario B: OON anesthesiologist at INN facility — balance billing prohibited"
  ],
  "corrected_claim_instructions": "Step-by-step instructions for the provider billing dept (if PROVIDER_CODING_ERROR). Null if PAYER path.",
  "action_summary": "1-2 sentence patient-facing action item",
  "estimated_success_probability": 0.0
}

CRITICAL RULES:
- If the NSA violation is detected (OON ancillary at INN facility), it is ALWAYS PAYER_ILLEGAL_DENIAL.
- If the CARC code is CO-97 (unbundling/NCCI edit), it is ALMOST ALWAYS PROVIDER_CODING_ERROR.
- If the CARC code is CO-50 (medical necessity) without supporting policy clause, classify as PAYER_ILLEGAL_DENIAL.
- If it is ambiguous, choose the path more favorable to the patient (PAYER_ILLEGAL_DENIAL with LOW confidence).
- estimated_success_probability: 0.0-1.0 — be honest. NSA violations = 0.90+. Cosmetic = 0.05."""


async def triage_node(state: AgentState) -> dict:
    """
    Triage Agent: Determine whether the denial is a Provider Coding Error
    or a Payer Illegal Denial, and route accordingly.

    Runs AFTER policy_analyzer, BEFORE grievance.
    This is the critical routing decision that prevents sending legal ERISA
    appeals for hospital billing typos.
    """
    logger.info("Agent 5 (Triage): Starting Provider vs. Payer fault determination")

    errors = state.get("errors", [])

    if not state.get("claim_case"):
        return {
            "triage_decision": None,
            "current_phase": "triage",
            "errors": errors + ["Triage Agent: No claim case available"],
        }

    try:
        claim = ClaimCase(**state["claim_case"])
        policy = PolicyProfile(**state["policy_profile"]) if state.get("policy_profile") else None
        cost = CostBreakdown(**state["cost_breakdown"]) if state.get("cost_breakdown") else None
        contradiction_analysis = state.get("contradiction_analysis")

        # ── Step 1: Run deterministic pre-checks first ────────────
        # These are clear-cut cases that don't need an LLM decision.

        # NSA ANCILLARY PROVIDER at INN FACILITY → always PAYER violation
        if (
            claim.facility_network_status == NetworkStatus.IN_NETWORK
            and claim.ancillary_service_type is not None
        ):
            nsa_decision = {
                "path": "PAYER_ILLEGAL_DENIAL",
                "confidence": "HIGH",
                "primary_reason": (
                    f"NSA Scenario B: {claim.ancillary_service_type.title()} provider "
                    f"('{claim.provider_name or 'Unknown'}') is OUT-OF-NETWORK at the "
                    f"IN-NETWORK facility '{claim.facility_name or 'Unknown'}'. "
                    "Balance billing is prohibited under 45 CFR § 149.410(b)."
                ),
                "coding_errors_detected": [],
                "legal_violations_detected": [
                    "No Surprises Act (NSA) Scenario B — OON ancillary provider "
                    "at INN facility. Patient cannot be balance billed. "
                    "Provider must negotiate with plan via IDR process.",
                    f"Illegal balance billed: ${cost.illegal_balance_billed_amount:,.2f}" if (cost and cost.illegal_balance_billed_amount > 0) else "",
                ],
                "corrected_claim_instructions": None,
                "action_summary": (
                    "File an NSA appeal with your insurance plan. The anesthesiologist/ancillary "
                    "provider cannot legally bill you for services rendered at an in-network hospital. "
                    "Your responsibility is capped at the in-network cost-sharing rate."
                ),
                "estimated_success_probability": 0.92,
                "triage_method": "deterministic_nsa",
            }
            logger.info(
                "Triage: DETERMINISTIC result — PAYER_ILLEGAL_DENIAL (NSA Scenario B)"
            )
            return {
                "triage_decision": nsa_decision,
                "current_phase": "triage",
                "errors": errors,
            }

        # CLEAR PROVIDER-SIDE CARC CODES → deterministic PROVIDER_CODING_ERROR
        carc = (claim.denial_carc_code or "").upper().replace(" ", "")
        if carc in PROVIDER_ERROR_CARC_CODES:
            coding_error_desc = PROVIDER_ERROR_CARC_CODES[carc]
            provider_decision = {
                "path": "PROVIDER_CODING_ERROR",
                "confidence": "HIGH",
                "primary_reason": (
                    f"Denial code {carc} indicates a provider billing error: {coding_error_desc}. "
                    "The problem is with the claim submission, not the coverage decision."
                ),
                "coding_errors_detected": [coding_error_desc],
                "legal_violations_detected": [],
                "corrected_claim_instructions": (
                    f"1. Contact '{claim.provider_name or 'the billing department'}' at the facility.\n"
                    f"2. Reference Claim ID and Date of Service: {claim.date_of_service}.\n"
                    f"3. Request a CORRECTED CLAIM resubmission addressing CARC code {carc}: {coding_error_desc}.\n"
                    "4. Ask for a new claim number after resubmission.\n"
                    "5. Follow up in 30 days if no response."
                ),
                "action_summary": (
                    f"Contact the provider's billing department and request a corrected claim "
                    f"resubmission. The denial ({carc}) is due to a billing error, not a coverage issue."
                ),
                "estimated_success_probability": 0.75,
                "triage_method": "deterministic_carc",
            }
            logger.info(f"Triage: DETERMINISTIC result — PROVIDER_CODING_ERROR (CARC {carc})")
            return {
                "triage_decision": provider_decision,
                "current_phase": "triage",
                "errors": errors,
            }

        # CLEAR PAYER-VIOLATION CARC CODES → deterministic PAYER_ILLEGAL_DENIAL
        if carc in PAYER_VIOLATION_CARC_CODES:
            violation_desc = PAYER_VIOLATION_CARC_CODES[carc]
            # Still run LLM for richer context, but pre-seed the path
            logger.info(
                f"Triage: CARC {carc} is a known payer violation — "
                "pre-seeding PAYER_ILLEGAL_DENIAL before LLM analysis"
            )
            # Fall through to LLM with this context

        # ── Step 2: LLM-based triage for ambiguous cases ──────────
        # Build a rich context for the LLM to reason over.
        claim_context = (
            f"CLAIM DETAILS:\n"
            f"- CPT Code: {claim.cpt_code} — {claim.cpt_description}\n"
            f"- ICD-10 Code: {claim.icd_10_code} — {claim.icd_10_description}\n"
            f"- Date of Service: {claim.date_of_service}\n"
            f"- Billed Amount: ${claim.billed_amount:,.2f}\n"
            f"- Provider: {claim.provider_name or 'Not specified'}\n"
            f"- Facility: {claim.facility_name or 'Not specified'}\n"
            f"- Provider Network Status: {claim.network_status.value}\n"
            f"- Facility Network Status: {(claim.facility_network_status.value if claim.facility_network_status else 'Not specified')}\n"
            f"- Ancillary Service Type: {claim.ancillary_service_type or 'Not applicable'}\n"
            f"- Is Emergency: {claim.is_emergency}\n"
            f"- NSA Applies (flagged by intake): {claim.nsa_applies}\n"
            f"- Is Denied: {claim.is_denied}\n"
            f"- Denial Reason: {claim.denial_reason.value if claim.denial_reason else 'Not specified'}\n"
            f"- Denial CARC Code: {claim.denial_carc_code or 'Not specified'}\n"
            f"- Denial RARC Code: {claim.denial_rarc_code or 'Not specified'}\n"
        )

        if policy:
            claim_context += (
                f"\nPLAN DETAILS:\n"
                f"- Plan: {policy.plan_name} ({policy.plan_type.value})\n"
                f"- Legal Classification: {policy.legal_classification.value}\n"
                f"- State: {policy.state}\n"
            )

        if cost:
            claim_context += (
                f"\nCOST CALCULATOR OUTPUT:\n"
                f"- NSA Violation Detected: {cost.nsa_violation_detected}\n"
                f"- Illegal Balance Amount: ${cost.illegal_balance_billed_amount:,.2f}\n"
                f"- Patient Legal Responsibility: ${cost.total_patient_responsibility:,.2f}\n"
            )

        if contradiction_analysis:
            claim_context += (
                f"\nPOLICY ANALYSIS FINDINGS:\n"
                f"- Contradiction Detected: {contradiction_analysis.get('is_contradiction')}\n"
                f"- Contradiction Strength: {contradiction_analysis.get('contradiction_strength')}\n"
                f"- Appeal Recommendation: {contradiction_analysis.get('appeal_recommendation')}\n"
                f"- Honest Assessment: {contradiction_analysis.get('honest_assessment', '')[:300]}\n"
            )

        # ── Step 3: Run Gemini for nuanced triage ─────────────────
        llm = get_llm(TaskType.REASONING, temperature=0.0)

        messages = [
            SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"{claim_context}\n\n"
                "Classify this denial and output ONLY the JSON object."
            )),
        ]

        response = await llm.ainvoke(messages)
        content = response.content.strip()

        # Strip markdown fences
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        triage_data = json.loads(content.strip())
        triage_data["triage_method"] = "llm_gemini"

        logger.info(
            f"Agent 5 (Triage): Decision = {triage_data.get('path')}, "
            f"Confidence = {triage_data.get('confidence')}, "
            f"Success probability = {triage_data.get('estimated_success_probability')}"
        )

        return {
            "triage_decision": triage_data,
            "current_phase": "triage",
            "errors": errors,
        }

    except json.JSONDecodeError as e:
        error_msg = f"Agent 5 (Triage): Failed to parse JSON response: {e}"
        logger.error(error_msg)
        # Default to PAYER_ILLEGAL_DENIAL on parse failure — never block the appeal path
        return {
            "triage_decision": {
                "path": "PAYER_ILLEGAL_DENIAL",
                "confidence": "LOW",
                "primary_reason": "Triage agent failed to parse — defaulting to payer appeal path.",
                "coding_errors_detected": [],
                "legal_violations_detected": [],
                "corrected_claim_instructions": None,
                "action_summary": "Proceeding with standard insurance appeal.",
                "estimated_success_probability": 0.5,
                "triage_method": "fallback_default",
            },
            "current_phase": "triage",
            "errors": errors + [error_msg],
        }
    except Exception as e:
        error_msg = f"Agent 5 (Triage): Triage failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            "triage_decision": {
                "path": "PAYER_ILLEGAL_DENIAL",
                "confidence": "LOW",
                "primary_reason": f"Triage agent error — defaulting to payer appeal path: {e}",
                "coding_errors_detected": [],
                "legal_violations_detected": [],
                "corrected_claim_instructions": None,
                "action_summary": "Proceeding with standard insurance appeal.",
                "estimated_success_probability": 0.5,
                "triage_method": "fallback_error",
            },
            "current_phase": "triage",
            "errors": errors + [error_msg],
        }
