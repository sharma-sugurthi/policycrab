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
import ast
import logging
from datetime import date, datetime
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.services.llm_router import get_llm, get_llm_with_retry, TaskType
from app.models.claim import ClaimCase
from app.models.policy import PolicyProfile
from app.models.enums import NetworkStatus
from app.tools.cpt_icd_lookup import lookup_cpt_code, lookup_icd10_code
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)


def _normalize_llm_content(content) -> str:
    if isinstance(content, str):
        text = content.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                parsed = ast.literal_eval(text)
                if isinstance(parsed, dict) and "text" in parsed:
                    return _normalize_llm_content(parsed["text"])
                if isinstance(parsed, list):
                    return " ".join(_normalize_llm_content(item) for item in parsed)
            except Exception:
                pass
        return text

    if isinstance(content, dict):
        if "text" in content:
            return _normalize_llm_content(content["text"])
        return json.dumps(content)

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(_normalize_llm_content(item))
        return "".join(parts)

    return str(content)


def _extract_json_text(content: str) -> str:
    normalized = _normalize_llm_content(content)

    if "```json" in normalized:
        normalized = normalized.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in normalized:
        normalized = normalized.split("```", 1)[1].split("```", 1)[0]

    normalized = normalized.strip()
    if not normalized:
        return normalized

    if normalized.startswith("{") and normalized.endswith("}"):
        try:
            parsed = json.loads(normalized)
            if isinstance(parsed, dict) and "text" in parsed:
                return _extract_json_text(parsed["text"])
        except Exception:
            pass

    return normalized


def _parse_date_flexible(raw: str) -> str | None:
    """
    Parse a date string in various formats and return YYYY-MM-DD.
    Handles: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, MM-DD-YYYY, etc.
    Returns None if parsing fails entirely.
    """
    if not raw or not raw.strip():
        return None

    raw = raw.strip()

    # Try ISO format first (YYYY-MM-DD)
    formats = [
        "%Y-%m-%d",      # 2026-05-14
        "%m/%d/%Y",      # 05/14/2026
        "%d/%m/%Y",      # 14/05/2026
        "%m-%d-%Y",      # 05-14-2026
        "%d-%m-%Y",      # 14-05-2026
        "%Y/%m/%d",      # 2026/05/14
        "%B %d, %Y",     # May 14, 2026
        "%b %d, %Y",     # May 14, 2026
        "%d %B %Y",      # 14 May 2026
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    logger.warning(f"Agent 2: Could not parse date '{raw}' — setting to None")
    return None


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
- prior_auth_required: Boolean — True ONLY if the procedure semantically matches one of the 'Prior Auth Categories' in the policy context.
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
        tools = [lookup_cpt_code, lookup_icd10_code]
        
        # Include policy context if available
        policy_context = ""
        if state.get("policy_profile"):
            policy = PolicyProfile(**state["policy_profile"])
            plan_type_str = policy.plan_type.value if policy.plan_type else "Unknown"
            deductible_str = f"${policy.in_network_deductible_individual:,.2f}" if policy.in_network_deductible_individual is not None else "N/A"
            oop_max_str = f"${policy.in_network_oop_max_individual:,.2f}" if policy.in_network_oop_max_individual is not None else "N/A"
            policy_context = (
                f"\n\nPatient's insurance plan context:\n"
                f"- Plan: {policy.plan_name} ({plan_type_str})\n"
                f"- Carrier: {policy.carrier_name}\n"
                f"- Requires PCP Referral: {policy.requires_pcp_referral}\n"
                f"- Prior Auth Categories: {', '.join(policy.prior_auth_required_categories) or 'None specified'}\n"
                f"- Deductible Met: ${policy.deductible_met:,.2f} of {deductible_str}\n"
                f"- OOP Met: ${policy.oop_met:,.2f} of {oop_max_str}\n"
            )

        messages = [
            SystemMessage(content=CLAIM_INTAKE_PROMPT),
            HumanMessage(content=f"Extract claim details from this patient description:{policy_context}\n\n{raw_text}"),
        ]

        # Tool execution loop with retry logic for rate limits
        max_steps = 3
        current_step = 0
        content = ""
        max_llm_retries = 3

        for llm_attempt in range(max_llm_retries):
            try:
                # Use retry logic to handle rate limits and fallback to other providers
                llm = get_llm_with_retry(TaskType.EXTRACTION, temperature=0.0).bind_tools(tools)

                while current_step < max_steps:
                    response = await llm.ainvoke(messages)
                    messages.append(response)

                    if not response.tool_calls:
                        content = response.content
                        # Handle case where content might be a list or dict
                        if isinstance(content, list):
                            content = content[0] if content else ""
                        elif isinstance(content, dict):
                            content = str(content)
                        break

                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]

                        try:
                            if tool_name == "lookup_cpt_code":
                                tool_result = lookup_cpt_code.invoke(tool_args)
                            elif tool_name == "lookup_icd10_code":
                                tool_result = lookup_icd10_code.invoke(tool_args)
                            else:
                                tool_result = f"Error: Unknown tool {tool_name}"
                        except Exception as e:
                            tool_result = f"Error executing {tool_name}: {e}"

                        messages.append(ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call["id"]
                        ))

                    current_step += 1

                if content:
                    break

            except Exception as e:
                logger.warning(f"Agent 2: LLM attempt {llm_attempt + 1} failed: {e}")
                if llm_attempt == max_llm_retries - 1:
                    raise

        # Parse JSON from response
        content = _extract_json_text(content)
        logger.info(f"Agent 2: LLM response content type: {type(content)}, length: {len(content)}")
        logger.info(f"Agent 2: LLM response preview: {content[:500]}")

        claim_data = json.loads(content.strip())

        # The LLM now semantically determines prior_auth_required based on the policy context.
        # Ensure it falls back to False if omitted by the LLM.
        if "prior_auth_required" not in claim_data:
            claim_data["prior_auth_required"] = False

        # Normalize date fields — LLMs often return dates in wrong formats
        for date_field in ('date_of_service', 'denial_date'):
            raw_date = claim_data.get(date_field)
            if raw_date and isinstance(raw_date, str):
                claim_data[date_field] = _parse_date_flexible(raw_date)
            elif raw_date is None:
                claim_data[date_field] = None

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
