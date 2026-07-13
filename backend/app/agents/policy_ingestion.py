"""
Agent 1: Policy Ingestion — Parses raw SBC/EOB text into a
structured PolicyProfile using LLM extraction.

This agent takes unstructured policy document text and extracts
all cost-sharing parameters, network rules, and legal classification
into the PolicyProfile Pydantic model.
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.services.llm_router import get_llm, TaskType
from app.models.policy import PolicyProfile

logger = logging.getLogger(__name__)

POLICY_EXTRACTION_PROMPT = """You are a US health insurance policy analyst. Extract structured 
policy information from the provided document text (SBC, EOB, or policy summary).

You MUST extract ALL of the following fields. If a field is not explicitly stated in the 
document, use reasonable defaults based on US insurance norms and note it in your response.

Required fields:
- plan_name: The name of the insurance plan
- carrier_name: The insurance company name
- plan_type: One of "HMO", "PPO", "EPO", "POS"
- legal_classification: One of "FULLY_INSURED", "SELF_FUNDED_ERISA", "MEDICARE_ADVANTAGE", 
  "MEDICARE_ORIGINAL", "MEDICAID_MANAGED", "INDIVIDUAL_ACA"
  (Hint: If the document mentions "marketplace" or "exchange", use INDIVIDUAL_ACA.
   If it mentions an employer with 500+ employees, likely SELF_FUNDED_ERISA.
   If it mentions a specific state DOI, likely FULLY_INSURED.)
- state: 2-letter US state code
- in_network_deductible_individual: Annual in-network individual deductible ($)
- in_network_oop_max_individual: Annual in-network individual OOP maximum ($)
- in_network_coinsurance: Patient coinsurance rate as decimal (e.g., 0.20 for 80/20)
- out_of_network_deductible_individual: OON deductible (null if no OON coverage)
- out_of_network_oop_max_individual: OON OOP max (null if no OON coverage)
- out_of_network_coinsurance: OON coinsurance rate (null if no OON coverage)
- copay_schedule: Object with primary_care, specialist, urgent_care, emergency_room, 
  generic_rx, preferred_brand_rx, specialty_rx (all in $)
- is_hsa_eligible: Boolean
- requires_pcp_referral: Boolean (true for HMO and POS)
- prior_auth_required_categories: List of service categories requiring prior auth
- excluded_services: List of explicitly excluded services

Respond ONLY with a valid JSON object matching the schema above. No explanations."""


async def policy_ingestion_node(state: AgentState) -> dict:
    """
    Parse raw policy text into a structured PolicyProfile.
    """
    logger.info("Agent 1 (Policy Ingestion): Starting SBC/EOB extraction")

    raw_text = state.get("raw_policy_text", "")
    if not raw_text:
        return {
            "errors": state.get("errors", []) + ["No policy text provided for ingestion"],
            "current_phase": "ingestion",
        }

    try:
        llm = get_llm(TaskType.EXTRACTION, temperature=0.0)

        messages = [
            SystemMessage(content=POLICY_EXTRACTION_PROMPT),
            HumanMessage(content=f"Extract the policy details from this document:\n\n{raw_text}"),
        ]

        response = await llm.ainvoke(messages)
        content = response.content

        # Parse JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        policy_data = json.loads(content.strip())

        # Validate through Pydantic
        policy = PolicyProfile(**policy_data)

        # ── Post-extraction sanity checks ─────────────────────
        warnings = []
        ded = policy.in_network_deductible_individual
        oop = policy.in_network_oop_max_individual
        coins = policy.in_network_coinsurance

        if ded is not None and (ded < 0 or ded > 20000):
            warnings.append(f"In-network deductible (${ded:,.0f}) is outside the typical $0–$20,000 range — please verify.")
        if oop is not None and (oop < 0 or oop > 50000):
            warnings.append(f"In-network OOP max (${oop:,.0f}) is outside the typical $0–$50,000 range — please verify.")
        if ded is not None and oop is not None and oop < ded:
            warnings.append(f"OOP max (${oop:,.0f}) is less than deductible (${ded:,.0f}) — this is unusual. Please verify.")
        if coins is not None and (coins < 0 or coins > 1):
            warnings.append(f"Coinsurance ({coins}) should be between 0.0 and 1.0 — please verify.")

        copay = policy.copay_schedule
        if copay:
            for field_name, val in [
                ("primary_care", copay.primary_care),
                ("specialist", copay.specialist),
                ("emergency_room", copay.emergency_room),
            ]:
                if val is not None and val > 1000:
                    warnings.append(f"Copay for {field_name} (${val:,.0f}) seems high — please verify.")

        # Confidence scoring
        if len(warnings) == 0:
            confidence = "HIGH"
        elif len(warnings) <= 2:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        if warnings:
            logger.warning(f"Agent 1: Extraction warnings ({confidence}): {warnings}")

        logger.info(f"Agent 1: Successfully extracted policy: {policy.plan_name} ({policy.carrier_name})")

        return {
            "policy_profile": policy.model_dump(),
            "extraction_warnings": warnings,
            "extraction_confidence": confidence,
            "current_phase": "ingestion",
            "errors": state.get("errors", []),
        }

    except json.JSONDecodeError as e:
        error_msg = f"Agent 1: Failed to parse LLM response as JSON: {e}"
        logger.error(error_msg)
        return {
            "errors": state.get("errors", []) + [error_msg],
            "current_phase": "ingestion",
        }
    except Exception as e:
        error_msg = f"Agent 1: Policy extraction failed: {e}"
        logger.error(error_msg)
        return {
            "errors": state.get("errors", []) + [error_msg],
            "current_phase": "ingestion",
        }
