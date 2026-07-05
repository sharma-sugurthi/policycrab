"""
Agent 2: Claim Intake — Normalizes a patient's plain-English
description of their healthcare claim into a structured ClaimCase.

This agent:
1. Extracts procedure and diagnosis from natural language
2. Maps them to CPT and ICD-10 codes using the lookup tools
3. Determines NSA applicability
4. Cross-references against the PolicyProfile for prior auth requirements
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.services.llm_router import get_llm, TaskType
from app.models.claim import ClaimCase
from app.models.policy import PolicyProfile
from app.models.enums import NetworkStatus

logger = logging.getLogger(__name__)

CLAIM_INTAKE_PROMPT = """You are a US medical billing intake specialist. Analyze the patient's 
description of their healthcare encounter and extract structured claim information.

You MUST extract:
- cpt_code: The CPT/HCPCS procedure code (e.g., "27447" for knee replacement)
- cpt_description: Human-readable procedure name
- icd_10_code: The ICD-10-CM diagnosis code (e.g., "M17.11")
- icd_10_description: Human-readable diagnosis
- date_of_service: Date the service was rendered (YYYY-MM-DD format)
- billed_amount: The amount billed (if mentioned; otherwise estimate based on typical US rates)
- provider_name: Doctor's name (if mentioned)
- facility_name: Hospital/clinic name (if mentioned)
- network_status: "IN_NETWORK", "OUT_OF_NETWORK", or "NOT_APPLICABLE"
- is_emergency: Boolean — was this an emergency?
- prior_auth_obtained: true/false/null (null if not mentioned)
- pcp_referral_obtained: true/false/null (null if not mentioned)

NSA (No Surprises Act) determination:
- Set nsa_applies=true if ANY of these conditions are met:
  1. Emergency service at an out-of-network facility
  2. Non-emergency service by an OON provider at an IN-NETWORK facility (surprise billing)
  3. Air ambulance service by an OON provider
- Set nsa_reason to explain why NSA applies (or null if it doesn't)

Denial information (if the patient mentions a denial):
- is_denied: Boolean
- denial_reason: One of "MEDICAL_NECESSITY", "PRIOR_AUTH_MISSING", "TIMELY_FILING", 
  "NOT_COVERED", "DUPLICATE_CLAIM", "COB_FAILURE", "UNBUNDLING", "NSA_BALANCE_BILLING",
  "PRE_EXISTING_CONDITION", "REFERRAL_MISSING", "OUT_OF_NETWORK_DENIAL", "OTHER"
- denial_date: Date of denial (YYYY-MM-DD)
- denial_carc_code: CARC code if mentioned (e.g., "CO-50")

Respond ONLY with a valid JSON object. No explanations."""


async def claim_intake_node(state: AgentState) -> dict:
    """
    Parse the patient's description into a structured ClaimCase.
    Cross-reference against PolicyProfile for prior auth and referral requirements.
    """
    logger.info("Agent 2 (Claim Intake): Starting claim normalization")

    raw_text = state.get("raw_claim_text", "")
    if not raw_text:
        return {
            "errors": state.get("errors", []) + ["No claim text provided for intake"],
            "current_phase": "intake",
        }

    try:
        llm = get_llm(TaskType.EXTRACTION, temperature=0.0)

        # Include policy context if available
        policy_context = ""
        if state.get("policy_profile"):
            policy = PolicyProfile(**state["policy_profile"])
            policy_context = (
                f"\n\nPatient's insurance plan context:\n"
                f"- Plan: {policy.plan_name} ({policy.plan_type.value})\n"
                f"- Carrier: {policy.carrier_name}\n"
                f"- Requires PCP Referral: {policy.requires_pcp_referral}\n"
                f"- Prior Auth Categories: {', '.join(policy.prior_auth_required_categories) or 'None specified'}\n"
                f"- Deductible Met: ${policy.deductible_met:,.2f} of ${policy.in_network_deductible_individual:,.2f}\n"
                f"- OOP Met: ${policy.oop_met:,.2f} of ${policy.in_network_oop_max_individual:,.2f}\n"
            )

        messages = [
            SystemMessage(content=CLAIM_INTAKE_PROMPT),
            HumanMessage(content=f"Extract claim details from this patient description:{policy_context}\n\n{raw_text}"),
        ]

        response = await llm.ainvoke(messages)
        content = response.content

        # Parse JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        claim_data = json.loads(content.strip())

        # Cross-reference prior auth requirements from policy
        if state.get("policy_profile"):
            policy = PolicyProfile(**state["policy_profile"])
            cpt_desc = claim_data.get("cpt_description", "").lower()

            # Check if any prior auth category matches
            for category in policy.prior_auth_required_categories:
                if category.lower() in cpt_desc or cpt_desc in category.lower():
                    claim_data["prior_auth_required"] = True
                    break

        # Validate through Pydantic
        claim = ClaimCase(**claim_data)

        logger.info(
            f"Agent 2: Claim normalized — CPT {claim.cpt_code} ({claim.cpt_description}), "
            f"Network: {claim.network_status.value}, NSA: {claim.nsa_applies}"
        )

        # Determine route decision
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
        logger.error(error_msg)
        return {
            "errors": state.get("errors", []) + [error_msg],
            "current_phase": "intake",
        }
