"""
Bill Auditor Agent — AI-powered medical bill auditing.

Scans medical bill service lines for 7 categories of billing errors:
  1. Upcoding         — CPT code too high for the diagnosis
  2. Unbundling        — Multiple codes that should be a single bundled code
  3. Duplicate Charges — Same service billed multiple times
  4. Excessive Pricing — Billed amount far above fair market rates
  5. Coding Mismatch   — CPT code doesn't match the ICD-10 diagnosis
  6. Modifier Errors   — Incorrect or missing CPT modifiers
  7. Balance Billing   — Illegal patient charges under NSA / network agreements

Processes bills in batches of 10 lines to stay within context limits.
Returns structured BillAuditResult with per-line findings and savings estimates.
"""

import json
import logging
import math
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.llm_router import get_llm_with_retry, TaskType
from app.models.bill_audit_models import (
    ServiceLineInput,
    AuditFlag,
    BillAuditResult,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 10  # Process 10 service lines per LLM call

# ── System Prompt ─────────────────────────────────────────────────
AUDIT_SYSTEM_PROMPT = """You are a certified medical coder (CPC-A, CCS) and forensic billing auditor
with 15 years of experience auditing US hospital bills and Explanation of Benefits documents.

Your job: Review each service line for billing errors and return structured findings.

AUDIT CATEGORIES (check ALL that apply for EACH line):

1. **Upcoding**: The CPT code represents a higher-level service than the diagnosis supports.
   Example: CPT 99285 (highest ER level) billed for a simple cold (ICD J00).
   
2. **Unbundling**: Multiple CPT codes billed separately when they should be bundled.
   Example: Billing 29881 + 29880 separately when 29881 includes the work of 29880.
   
3. **Duplicate Charges**: Same CPT code, same date, same provider billed more than once
   without a valid reason (e.g., bilateral procedure modifier -50).
   
4. **Excessive Pricing**: Billed amount is significantly above fair market rates.
   Use your knowledge of typical US pricing by region. Flag if >2x the typical range.
   For common services, typical ranges:
   - ER Visit (99281-99285): $150-$3,500
   - MRI (70553): $400-$3,500
   - CT Scan (74177): $300-$3,000
   - X-Ray (71046): $50-$500
   - Office Visit (99213): $100-$250
   - Total Knee Replacement (27447): $30,000-$70,000
   - Anesthesia per unit: $50-$150
   
5. **Coding Mismatch**: CPT procedure code doesn't logically correspond to the ICD-10 diagnosis.
   Example: CPT 27447 (knee replacement) with ICD K80.20 (gallstones).
   
6. **Modifier Errors**: Missing or incorrect modifiers that could cause denial or overbilling.
   Example: Bilateral procedure without -50 modifier, or professional component without -26.
   
7. **Balance Billing**: If the service was at an in-network facility or was an emergency,
   check if the patient responsibility seems to include illegal balance billing
   (difference between billed and allowed amounts charged to patient).

RULES:
- Be ACCURATE. Only flag issues you are confident about. False positives erode trust.
- For each flag, estimate potential dollar savings if corrected (null if uncertain).
- Estimate a "fair price" for each service line based on typical US rates.
- If a line looks clean, do NOT flag it.
- Return findings as a JSON array of objects.

OUTPUT FORMAT — return ONLY this JSON, no markdown fences:
{
  "flags": [
    {
      "line_number": <int>,
      "issue_type": "upcoding|unbundling|duplicate|excessive_charge|coding_mismatch|modifier_error|balance_billing",
      "severity": "critical|warning|info",
      "description": "<detailed explanation>",
      "recommendation": "<actionable step for patient>",
      "estimated_savings": <float or null>
    }
  ],
  "line_fair_prices": [
    {"line_number": <int>, "estimated_fair_price": <float or null>}
  ],
  "batch_summary": "<1-2 sentence summary of findings for this batch>"
}

If no issues found in the batch, return: {"flags": [], "line_fair_prices": [...], "batch_summary": "No billing errors detected in this batch."}
"""

DISPUTE_LETTER_PROMPT = """You are a patient advocate and medical billing dispute specialist.
Draft a formal dispute letter to the hospital/provider billing department based on the audit findings below.

The letter should:
1. Be addressed to the billing department (use "[Provider/Facility Name]" as placeholder if unknown)
2. Reference specific CPT codes, dates of service, and billed amounts
3. Cite the specific billing errors found (upcoding, unbundling, etc.)
4. Request an itemized bill review and correction
5. Reference the patient's rights under the No Surprises Act (if applicable)
6. Reference the right to request an itemized bill under 42 CFR § 405.1803
7. Include a deadline for response (30 days is standard)
8. Be professional, firm, and factual — NOT aggressive
9. End with patient signature line

AUDIT FINDINGS:
{audit_summary}

FLAGGED ISSUES:
{flagged_issues}

TOTAL BILLED: ${total_billed}
ESTIMATED FAIR TOTAL: ${fair_total}
POTENTIAL SAVINGS: ${potential_savings}

Write the complete letter. Return ONLY the letter text, no markdown fences or commentary."""


def _format_lines_for_prompt(lines: list[ServiceLineInput]) -> str:
    """Format service lines into a readable table for the LLM."""
    parts = []
    for line in lines:
        parts.append(
            f"Line {line.line_number}: "
            f"CPT={line.cpt_code or 'N/A'} ({line.cpt_description or 'N/A'}), "
            f"ICD-10={line.icd_10_code or 'N/A'} ({line.icd_10_description or 'N/A'}), "
            f"Billed=${line.billed_amount or 'N/A'}, "
            f"Allowed=${line.allowed_amount or 'N/A'}, "
            f"Units={line.units}, "
            f"Modifier={line.modifier or 'none'}, "
            f"Date={line.date_of_service or 'N/A'}, "
            f"Provider={line.provider_name or 'N/A'}"
        )
    return "\n".join(parts)


def _parse_audit_response(raw: str) -> dict:
    """Parse the LLM's JSON response, handling markdown fences."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return json.loads(raw.strip())


async def audit_batch(lines: list[ServiceLineInput], policy_context: str = "") -> dict:
    """Audit a single batch of service lines (up to BATCH_SIZE)."""
    # Fail fast on timeouts (max_retries=1) to prevent long-running endpoint hangs
    llm = get_llm_with_retry(TaskType.REASONING, max_retries=1)

    formatted = _format_lines_for_prompt(lines)
    user_message = f"Audit these service lines:\n\n{formatted}"
    if policy_context:
        user_message += f"\n\nPolicy context (if relevant):\n{policy_context}"

    messages = [
        SystemMessage(content=AUDIT_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = await llm.ainvoke(messages)
    return _parse_audit_response(response.content)


async def run_bill_audit(
    lines: list[ServiceLineInput],
    policy_context: str = "",
) -> BillAuditResult:
    """
    Run a full bill audit across all service lines.
    Processes in batches of BATCH_SIZE for reliability.
    """
    if not lines:
        return BillAuditResult(
            overall_risk="low",
            total_billed=0.0,
            summary="No service lines provided for audit.",
            line_count=0,
        )

    total_billed = sum(l.billed_amount or 0 for l in lines)
    all_flags: list[AuditFlag] = []
    fair_prices: dict[int, float | None] = {}
    batch_summaries: list[str] = []

    # Process in batches
    num_batches = math.ceil(len(lines) / BATCH_SIZE)
    for i in range(num_batches):
        batch = lines[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        logger.info(
            f"Bill Audit: Processing batch {i + 1}/{num_batches} "
            f"(lines {batch[0].line_number}-{batch[-1].line_number})"
        )

        try:
            result = await audit_batch(batch, policy_context)

            # Parse flags
            for flag_data in result.get("flags", []):
                try:
                    all_flags.append(AuditFlag(**flag_data))
                except Exception as e:
                    logger.warning(f"Skipping malformed flag: {e}")

            # Parse fair prices
            for fp in result.get("line_fair_prices", []):
                fair_prices[fp["line_number"]] = fp.get("estimated_fair_price")

            if result.get("batch_summary"):
                batch_summaries.append(result["batch_summary"])

        except Exception as e:
            logger.error(f"Bill Audit batch {i + 1} failed: {e}")
            
            err_msg = str(e).lower()
            if "504" in err_msg or "timeout" in err_msg or "deadline_exceeded" in err_msg:
                friendly_desc = "AI Servers are currently very busy. Please try again later."
            else:
                friendly_desc = f"Automated audit could not complete for lines {batch[0].line_number}-{batch[-1].line_number}: {str(e)[:100]}"
                
            all_flags.append(
                AuditFlag(
                    line_number=batch[0].line_number,
                    issue_type="general_warning",
                    severity="info",
                    description=friendly_desc,
                    recommendation="Review these lines manually.",
                )
            )

    # Calculate totals
    estimated_fair_total = None
    if fair_prices:
        valid_prices = [v for v in fair_prices.values() if v is not None]
        if valid_prices:
            estimated_fair_total = sum(valid_prices)

    potential_savings = sum(
        f.estimated_savings for f in all_flags if f.estimated_savings
    )

    # Determine overall risk
    critical_count = sum(1 for f in all_flags if f.severity == "critical")
    warning_count = sum(1 for f in all_flags if f.severity == "warning")

    if critical_count >= 2 or (critical_count >= 1 and warning_count >= 2):
        overall_risk = "high"
    elif critical_count >= 1 or warning_count >= 2:
        overall_risk = "medium"
    elif warning_count >= 1:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    # Build summary
    if not all_flags:
        summary = (
            f"Audit complete. {len(lines)} service line(s) reviewed — "
            f"no billing errors detected. Total billed: ${total_billed:,.2f}."
        )
    else:
        summary = (
            f"Audit complete. {len(lines)} service line(s) reviewed — "
            f"{len(all_flags)} issue(s) found "
            f"({critical_count} critical, {warning_count} warnings). "
            f"Total billed: ${total_billed:,.2f}."
        )
        if potential_savings:
            summary += f" Estimated potential savings: ${potential_savings:,.2f}."

    return BillAuditResult(
        overall_risk=overall_risk,
        total_billed=total_billed,
        estimated_fair_total=estimated_fair_total,
        potential_savings=potential_savings if potential_savings else None,
        flags=all_flags,
        summary=summary,
        line_count=len(lines),
    )


async def generate_dispute_letter(audit_result: BillAuditResult) -> str:
    """Generate a formal dispute letter from audit findings."""
    llm = get_llm_with_retry(TaskType.LEGAL_WRITING)

    flagged_issues = "\n".join(
        f"- Line {f.line_number} ({f.issue_type}): {f.description} → {f.recommendation}"
        for f in audit_result.flags
    )
    if not flagged_issues:
        flagged_issues = "No specific issues flagged."

    prompt = DISPUTE_LETTER_PROMPT.format(
        audit_summary=audit_result.summary,
        flagged_issues=flagged_issues,
        total_billed=f"{audit_result.total_billed:,.2f}",
        fair_total=f"{audit_result.estimated_fair_total:,.2f}" if audit_result.estimated_fair_total else "N/A",
        potential_savings=f"{audit_result.potential_savings:,.2f}" if audit_result.potential_savings else "N/A",
    )

    messages = [HumanMessage(content=prompt)]
    response = await llm.ainvoke(messages)
    return response.content
