"""
Regulatory Router — deterministic legal framework routing.

Maps a PolicyProfile's legal classification to the correct
appeal framework. This is pure logic — no LLM involvement.
"""

from app.models.enums import AppealFramework, PlanLegalClassification
from app.models.policy import PolicyProfile
from app.models.claim import ClaimCase
from app.engine.state_profiles import get_state_summary, get_state_external_review_deadline


def route_to_appeal_framework(
    policy: PolicyProfile,
    claim: ClaimCase,
) -> AppealFramework:
    """
    Determine the correct legal appeal pathway based on the plan's
    legal classification and the claim's characteristics.

    Priority:
    1. NSA IDR — for No Surprises Act-qualifying services
    2. Plan classification — ERISA, state, Medicare, etc.
    """

    # ── NSA IDR takes priority for qualifying services ────────────
    if claim.nsa_applies:
        return AppealFramework.NSA_IDR

    # ── Route by plan legal classification ────────────────────────
    match policy.legal_classification:
        case PlanLegalClassification.SELF_FUNDED_ERISA:
            # Self-funded ERISA plans: federal law, state preempted
            # Internal appeal → external review (if plan allows) → federal court
            return AppealFramework.ERISA_FEDERAL

        case PlanLegalClassification.FULLY_INSURED:
            # State-regulated plans: state DOI external review available
            return AppealFramework.STATE_EXTERNAL_REVIEW

        case PlanLegalClassification.INDIVIDUAL_ACA:
            # ACA Marketplace plans: Internal appeal → State/Federal external review
            return AppealFramework.ACA_MARKETPLACE_APPEAL

        case PlanLegalClassification.MEDICARE_ADVANTAGE:
            # Medicare Advantage: CMS 5-level appeal process
            return AppealFramework.MEDICARE_ADVANTAGE_5LEVEL

        case PlanLegalClassification.MEDICARE_ORIGINAL:
            # Original Medicare (Parts A/B): MAC → QIC → ALJ → Appeals Council → Federal Court
            return AppealFramework.MEDICARE_ORIGINAL_5LEVEL

        case PlanLegalClassification.MEDICAID_MANAGED:
            # Medicaid managed care: internal plan appeal → state Medicaid fair hearing
            return AppealFramework.MEDICAID_FAIR_HEARING

        case _:
            # Default to state complaint — safest fallback
            return AppealFramework.STATE_DOI_COMPLAINT


def get_appeal_framework_details(framework: AppealFramework) -> dict:
    """
    Return human-readable details about the appeal framework,
    including the governing law and general process description.
    """
    details = {
        AppealFramework.ERISA_FEDERAL: {
            "governing_law": "Employee Retirement Income Security Act (ERISA), 29 U.S.C. § 1132",
            "regulation": "29 CFR § 2560.503-1",
            "process": [
                "File internal appeal with the plan within 180 days of denial",
                "Plan must decide within 30 days (pre-service) or 60 days (post-service)",
                "If denied: request external review (if available under plan terms)",
                "If denied: file suit in federal court under ERISA Section 502(a)",
            ],
            "key_requirement": "Administrative record is CLOSED after internal appeal — submit ALL evidence during the appeal",
            "deadline_days": 180,
        },
        AppealFramework.STATE_EXTERNAL_REVIEW: {
            "governing_law": "State Department of Insurance regulations (varies by state)",
            "regulation": "ACA Section 2719 (minimum federal external review standards)",
            "process": [
                "File internal appeal with the insurer",
                "If denied: request external review through state DOI",
                "External review is conducted by an independent reviewer",
                "External review decision is binding on the insurer",
            ],
            "key_requirement": "External review is binding on the insurer — often more favorable than ERISA federal pathway",
            "deadline_days": 120,
        },
        AppealFramework.MEDICARE_ADVANTAGE_5LEVEL: {
            "governing_law": "42 CFR Part 422",
            "regulation": "CMS Medicare Advantage appeal regulations",
            "process": [
                "Level 1: Redetermination by the MA plan (60 days)",
                "Level 2: Reconsideration by IRE (60 days)",
                "Level 3: ALJ hearing at OMHA (Amount in Controversy ≥ $180)",
                "Level 4: Medicare Appeals Council review",
                "Level 5: Federal District Court (Amount in Controversy ≥ $1,840)",
            ],
            "key_requirement": "Each level must be exhausted before proceeding to the next",
            "deadline_days": 60,
        },
        AppealFramework.MEDICARE_ORIGINAL_5LEVEL: {
            "governing_law": "42 CFR Part 405, Subpart I",
            "regulation": "CMS Original Medicare (Parts A/B) appeal regulations",
            "process": [
                "Level 1: Redetermination by the Medicare Administrative Contractor (MAC) — 120 days to file, decision within 60 days",
                "Level 2: Reconsideration by a Qualified Independent Contractor (QIC) — 180 days to file, decision within 60 days",
                "Level 3: ALJ hearing at OMHA (Amount in Controversy ≥ $180 for 2025) — 60 days to file",
                "Level 4: Medicare Appeals Council (DAB) review — 60 days to file",
                "Level 5: Federal District Court (Amount in Controversy ≥ $1,840 for 2025) — 60 days to file",
            ],
            "key_requirement": "Level 1 must be filed with the MAC within 120 days of the initial determination. All evidence should be submitted at the QIC stage — the record may close after Level 2.",
            "deadline_days": 120,
        },
        AppealFramework.NSA_IDR: {
            "governing_law": "No Surprises Act, Consolidated Appropriations Act 2021",
            "regulation": "45 CFR Part 149",
            "process": [
                "Open negotiation period (30 business days from initial payment/denial)",
                "If unresolved: initiate federal IDR (binding arbitration)",
                "Each party submits offer; arbitrator selects one (baseball-style)",
                "Arbitrator considers QPA as primary factor",
            ],
            "key_requirement": "Patient is NOT a party to IDR — it's between provider and payer. Patient cost-sharing is capped at in-network rates.",
            "deadline_days": 30,
        },
        AppealFramework.MEDICAID_FAIR_HEARING: {
            "governing_law": "42 CFR § 438.402 (Managed Medicaid); 42 CFR § 431.200 (Fee-for-Service Medicaid)",
            "regulation": "State Medicaid agency fair hearing regulations",
            "process": [
                "Step 1: File internal appeal with the Medicaid managed care plan (MCO) within 60 days of the denial notice",
                "Step 2: MCO must issue a decision within 30 days (standard) or 72 hours (expedited)",
                "Step 3: If MCO upholds denial, request a State Fair Hearing through the state Medicaid agency within 120 days",
                "Step 4: An Administrative Law Judge (ALJ) conducts a formal hearing and issues a binding decision",
            ],
            "key_requirement": "The MCO must continue benefits during the appeal if the appeal is filed within 10 days of the denial AND the service was previously authorized. Request 'aid paid pending' to maintain coverage during the process.",
            "deadline_days": 60,
        },
        AppealFramework.ACA_MARKETPLACE_APPEAL: {
            "governing_law": "Affordable Care Act (ACA), 45 CFR § 147.136 & § 156.122",
            "regulation": "Federal ACA regulations governing non-grandfathered plans",
            "process": [
                "Step 1: Internal Appeal (180 days to file)",
                "Step 2: External Review by State DOI or HHS-administered Federal External Review Process (within 4 months of internal denial)",
            ],
            "key_requirement": "ACA protections enforce coverage for Essential Health Benefits (EHBs), prohibit pre-existing condition exclusions, and mandate standard/expedited formulary exception pathways.",
            "deadline_days": 180,
        },
        AppealFramework.STATE_DOI_COMPLAINT: {
            "governing_law": "State insurance code (varies by state)",
            "regulation": "State Department of Insurance complaint procedures",
            "process": [
                "File a formal complaint with the state Department of Insurance",
                "DOI investigates the insurer's conduct",
                "DOI may order corrective action if violations found",
            ],
            "key_requirement": "This is a regulatory complaint, not an appeal. It does not directly reverse a denial but may pressure the insurer.",
            "deadline_days": 365,
        },
    }
    return details.get(framework, {})


def get_state_enriched_context(
    policy: PolicyProfile,
    framework: AppealFramework,
) -> dict:
    """
    Return state-specific regulatory context for a given plan and framework.
    Used to enrich appeal letter prompts and API responses.

    For ERISA self-funded plans, state law is preempted — returns a note explaining this.
    For fully insured and ACA plans, returns full state profile.
    """
    state = policy.state or "XX"

    if framework == AppealFramework.ERISA_FEDERAL:
        return {
            "note": (
                f"ERISA self-funded plan — {state} state insurance law is PREEMPTED. "
                "Federal ERISA governs exclusively. State DOI has no jurisdiction over this plan."
            ),
            "state_code": state,
            "erisa_preempted": True,
        }

    state_summary = get_state_summary(state)
    return {
        **state_summary,
        "erisa_preempted": False,
    }
