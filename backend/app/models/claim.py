"""
ClaimCase & CostBreakdown — models for claim evaluation.
ClaimCase is the structured input from the Claim Intake Agent.
CostBreakdown is the deterministic output of the Cost Calculator Engine.
"""

from datetime import date
from pydantic import BaseModel, Field
from app.models.enums import NetworkStatus, ClaimStatus, DenialReason


class ClaimCase(BaseModel):
    """
    Structured representation of a patient's healthcare claim.
    Populated by Agent 2 (Claim Intake) from unstructured patient input.
    """

    # ── Service Details ───────────────────────────────────────────
    cpt_code: str = Field(..., description="CPT/HCPCS procedure code (e.g., '27447')")
    cpt_description: str = Field("", description="Human-readable procedure name (e.g., 'Total Knee Replacement')")
    icd_10_code: str = Field("", description="ICD-10-CM diagnosis code (e.g., 'M17.11')")
    icd_10_description: str = Field("", description="Human-readable diagnosis (e.g., 'Primary osteoarthritis, right knee')")
    date_of_service: date | None = Field(None, description="Date the service was rendered (YYYY-MM-DD)")
    billed_amount: float = Field(..., gt=0, description="Provider's billed charge (chargemaster rate)")

    # ── Provider Context ──────────────────────────────────────────
    provider_name: str | None = Field(None, description="Treating provider name")
    facility_name: str | None = Field(None, description="Hospital or facility name")
    provider_npi: str | None = Field(None, description="National Provider Identifier (10-digit)")
    network_status: NetworkStatus = Field(..., description="Provider's network status under the patient's plan")
    # The facility (hospital) network status, which may DIFFER from the individual provider's status.
    # This is the critical field for NSA ancillary provider detection:
    # e.g., an OON anesthesiologist (network_status=OUT_OF_NETWORK) working at an INN hospital
    # (facility_network_status=IN_NETWORK) — the patient CANNOT be balance billed for this.
    facility_network_status: NetworkStatus | None = Field(
        None,
        description=(
            "The hospital/facility's network status. If this is IN_NETWORK while "
            "network_status is OUT_OF_NETWORK, an NSA ancillary provider violation may apply."
        ),
    )
    # Identifies whether this claim is for an ancillary service. Under the NSA, ancillary
    # providers (anesthesiology, pathology, radiology, neonatology, assistant surgeons, etc.)
    # at in-network facilities are specifically prohibited from balance billing.
    ancillary_service_type: str | None = Field(
        None,
        description=(
            "Type of ancillary service if applicable (e.g., 'anesthesiology', 'radiology', "
            "'pathology', 'neonatology'). Populated by Claim Intake Agent."
        ),
    )

    # ── Authorization & Referral Status ───────────────────────────
    is_emergency: bool = Field(False, description="True if this was an emergency service (triggers NSA/EMTALA)")
    prior_auth_obtained: bool | None = Field(
        None, description="True/False/None — None means not yet determined"
    )
    prior_auth_required: bool = Field(
        False, description="Set by cross-referencing CPT against PolicyProfile"
    )
    pcp_referral_obtained: bool | None = Field(
        None, description="True/False/None — relevant for HMO/POS plans only"
    )

    # ── NSA Applicability (set by Agent 2) ────────────────────────
    nsa_applies: bool = Field(
        False, description="True if No Surprises Act protections apply to this claim"
    )
    nsa_reason: str | None = Field(
        None, description="Why NSA applies (e.g., 'Emergency at OON facility', 'OON provider at INN facility')"
    )

    # ── Denial Info (populated if claim was already denied) ───────
    is_denied: bool = Field(False, description="True if this claim has been denied")
    denial_reason: DenialReason | None = Field(None, description="Reason for denial")
    denial_date: date | None = Field(None, description="Date the denial was issued (YYYY-MM-DD)")
    denial_carc_code: str | None = Field(None, description="CARC code from EOB/ERA (e.g., 'CO-50')")
    denial_rarc_code: str | None = Field(None, description="RARC code from EOB/ERA (e.g., 'N115')")


class CostBreakdown(BaseModel):
    """
    Deterministic output of the Cost Calculator Engine.
    All math is performed in Python — no LLM involvement.
    """

    # ── Input Echo ────────────────────────────────────────────────
    billed_amount: float = Field(..., description="Original billed charge")
    allowed_amount: float = Field(..., description="Plan's allowed amount (negotiated or QPA)")
    allowed_amount_source: str = Field(
        "estimate",
        description="'eob' when supplied by the user; 'billed_amount_estimate' when no EOB allowed amount is available",
    )

    # ── Waterfall Calculation ─────────────────────────────────────
    applied_to_deductible: float = Field(
        ..., description="Portion of allowed amount applied to remaining deductible"
    )
    coinsurance_amount: float = Field(
        ..., description="Patient's coinsurance share of post-deductible amount"
    )
    copay_amount: float = Field(0.0, description="Applicable copay (if any)")

    # ── Totals ────────────────────────────────────────────────────
    total_patient_responsibility: float = Field(
        ..., description="Total patient owes: deductible + coinsurance + copay"
    )
    total_insurer_payout: float = Field(
        ..., description="Total the insurer pays"
    )

    # ── Post-Calculation Accumulations ────────────────────────────
    deductible_remaining_after: float = Field(
        ..., description="Remaining deductible after this claim"
    )
    oop_remaining_after: float = Field(
        ..., description="Remaining OOP max after this claim"
    )
    hit_oop_max: bool = Field(
        False, description="True if patient hit the OOP max during this claim"
    )

    # ── NSA Violation Flags ───────────────────────────────────────
    # These are populated when the calculator detects an NSA Scenario B violation
    # (OON ancillary provider at INN facility). The grievance agent uses these to
    # draft a targeted NSA appeal letter citing the exact illegal balance billed amount.
    nsa_violation_detected: bool = Field(
        False,
        description="True if an NSA ancillary provider balance billing violation was detected",
    )
    illegal_balance_billed_amount: float = Field(
        0.0,
        description=(
            "The amount the provider/EOB attempted to illegally assign to the patient "
            "in violation of 45 CFR § 149.410(b). This is the amount the appeal letter "
            "must demand be corrected or refunded."
        ),
    )

    # ── Status & Notes ────────────────────────────────────────────
    claim_status: ClaimStatus = Field(ClaimStatus.PENDING, description="Claim evaluation status")
    denial_reason: DenialReason | None = Field(None, description="If denied, the reason")
    calculation_notes: list[str] = Field(
        default_factory=list, description="Explanatory notes about the calculation"
    )
