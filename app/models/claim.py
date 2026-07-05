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
    cpt_description: str = Field(..., description="Human-readable procedure name (e.g., 'Total Knee Replacement')")
    icd_10_code: str = Field(..., description="ICD-10-CM diagnosis code (e.g., 'M17.11')")
    icd_10_description: str = Field(..., description="Human-readable diagnosis (e.g., 'Primary osteoarthritis, right knee')")
    date_of_service: date = Field(..., description="Date the service was rendered")
    billed_amount: float = Field(..., gt=0, description="Provider's billed charge (chargemaster rate)")

    # ── Provider Context ──────────────────────────────────────────
    provider_name: str | None = Field(None, description="Treating provider name")
    facility_name: str | None = Field(None, description="Hospital or facility name")
    provider_npi: str | None = Field(None, description="National Provider Identifier (10-digit)")
    network_status: NetworkStatus = Field(..., description="Provider's network status under the patient's plan")

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
    denial_date: date | None = Field(None, description="Date the denial was issued")
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

    # ── Status & Notes ────────────────────────────────────────────
    claim_status: ClaimStatus = Field(ClaimStatus.PENDING, description="Claim evaluation status")
    denial_reason: DenialReason | None = Field(None, description="If denied, the reason")
    calculation_notes: list[str] = Field(
        default_factory=list, description="Explanatory notes about the calculation"
    )
