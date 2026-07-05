"""
PolicyProfile — structured representation of a health insurance plan's
cost-sharing rules, network model, and legal classification.
Extracted from SBC/EOB documents by the Policy Ingestion Agent.
"""

from pydantic import BaseModel, Field
from app.models.enums import PlanType, PlanLegalClassification, MetalTier


class CopaySchedule(BaseModel):
    """Fixed copay amounts by service category."""
    primary_care: float = Field(0.0, description="PCP office visit copay")
    specialist: float = Field(0.0, description="Specialist visit copay")
    urgent_care: float = Field(0.0, description="Urgent care visit copay")
    emergency_room: float = Field(0.0, description="ER visit copay (may be waived if admitted)")
    generic_rx: float = Field(0.0, description="Tier 1 generic drug copay")
    preferred_brand_rx: float = Field(0.0, description="Tier 3 preferred brand drug copay")
    specialty_rx: float = Field(0.0, description="Tier 5 specialty drug copay/coinsurance")


class PolicyProfile(BaseModel):
    """
    Complete structured representation of a US health insurance plan.
    Every field uses US-standard billing terminology.
    """

    # ── Plan Identification ───────────────────────────────────────
    plan_name: str = Field(..., description="Plan name as printed on the SBC")
    carrier_name: str = Field(..., description="Insurance carrier (e.g., UnitedHealthcare, Anthem)")
    plan_type: PlanType = Field(..., description="Network model: HMO, PPO, EPO, or POS")
    legal_classification: PlanLegalClassification = Field(
        ..., description="Legal classification — determines appeal framework"
    )
    state: str = Field(..., min_length=2, max_length=2, description="2-letter state code (e.g., CA, TX, NY)")
    metal_tier: MetalTier | None = Field(None, description="ACA metal tier (marketplace plans only)")
    group_number: str | None = Field(None, description="Employer group number (employer plans only)")

    # ── In-Network Cost Sharing ───────────────────────────────────
    in_network_deductible_individual: float = Field(
        ..., ge=0, description="Annual in-network individual deductible"
    )
    in_network_deductible_family: float | None = Field(
        None, ge=0, description="Annual in-network family deductible"
    )
    in_network_oop_max_individual: float = Field(
        ..., ge=0, description="Annual in-network individual out-of-pocket maximum"
    )
    in_network_oop_max_family: float | None = Field(
        None, ge=0, description="Annual in-network family out-of-pocket maximum"
    )
    in_network_coinsurance: float = Field(
        ..., ge=0, le=1, description="Patient coinsurance rate (e.g., 0.20 for 80/20 plan)"
    )
    copay_schedule: CopaySchedule = Field(
        default_factory=CopaySchedule, description="Fixed copay amounts by service category"
    )

    # ── Out-of-Network Cost Sharing ───────────────────────────────
    out_of_network_deductible_individual: float | None = Field(
        None, ge=0, description="Annual OON individual deductible (None = no OON coverage)"
    )
    out_of_network_oop_max_individual: float | None = Field(
        None, ge=0, description="Annual OON individual out-of-pocket maximum"
    )
    out_of_network_coinsurance: float | None = Field(
        None, ge=0, le=1, description="Patient OON coinsurance rate (e.g., 0.40 for 60/40)"
    )

    # ── Plan Features ─────────────────────────────────────────────
    is_hsa_eligible: bool = Field(False, description="True if this is an HDHP eligible for HSA")
    requires_pcp_referral: bool = Field(
        False, description="True for HMO and POS — specialist visits require PCP referral"
    )
    prior_auth_required_categories: list[str] = Field(
        default_factory=list,
        description="Service categories requiring prior authorization (e.g., 'elective surgery', 'advanced imaging')"
    )
    excluded_services: list[str] = Field(
        default_factory=list,
        description="Services explicitly excluded from coverage"
    )
    covered_essential_health_benefits: bool = Field(
        True, description="True if plan covers all 10 ACA Essential Health Benefits"
    )

    # ── Accumulations (current plan year) ─────────────────────────
    deductible_met: float = Field(0.0, ge=0, description="Amount of deductible already met this year")
    oop_met: float = Field(0.0, ge=0, description="Amount of OOP max already met this year")
