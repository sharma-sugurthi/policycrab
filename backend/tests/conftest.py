"""
Tests for pytest configuration.
"""
import pytest


@pytest.fixture
def sample_ppo_policy():
    """A standard PPO plan — covers in-network and out-of-network."""
    from app.models.policy import PolicyProfile, CopaySchedule
    from app.models.enums import PlanType, PlanLegalClassification

    return PolicyProfile(
        plan_name="Blue Shield PPO Gold",
        carrier_name="Blue Shield of California",
        plan_type=PlanType.PPO,
        legal_classification=PlanLegalClassification.FULLY_INSURED,
        state="CA",
        in_network_deductible_individual=1500.0,
        in_network_oop_max_individual=6000.0,
        in_network_coinsurance=0.20,
        out_of_network_deductible_individual=3000.0,
        out_of_network_oop_max_individual=12000.0,
        out_of_network_coinsurance=0.40,
        copay_schedule=CopaySchedule(
            primary_care=25, specialist=50, urgent_care=75, emergency_room=250
        ),
        requires_pcp_referral=False,
        prior_auth_required_categories=["elective surgery", "advanced imaging"],
        deductible_met=0.0,
        oop_met=0.0,
    )


@pytest.fixture
def sample_hmo_policy():
    """A strict HMO plan — in-network only, requires PCP referral."""
    from app.models.policy import PolicyProfile, CopaySchedule
    from app.models.enums import PlanType, PlanLegalClassification

    return PolicyProfile(
        plan_name="Kaiser HMO Silver",
        carrier_name="Kaiser Permanente",
        plan_type=PlanType.HMO,
        legal_classification=PlanLegalClassification.SELF_FUNDED_ERISA,
        state="CA",
        in_network_deductible_individual=2000.0,
        in_network_oop_max_individual=7500.0,
        in_network_coinsurance=0.20,
        copay_schedule=CopaySchedule(
            primary_care=20, specialist=40, urgent_care=50, emergency_room=200
        ),
        requires_pcp_referral=True,
        prior_auth_required_categories=["elective surgery", "advanced imaging", "specialty drugs"],
        deductible_met=0.0,
        oop_met=0.0,
    )


@pytest.fixture
def sample_claim_in_network():
    """A standard in-network claim for a knee replacement."""
    from datetime import date
    from app.models.claim import ClaimCase
    from app.models.enums import NetworkStatus

    return ClaimCase(
        cpt_code="27447",
        cpt_description="Total Knee Replacement",
        icd_10_code="M17.11",
        icd_10_description="Primary osteoarthritis, right knee",
        date_of_service=date(2025, 6, 15),
        billed_amount=45000.0,
        provider_name="Dr. Smith",
        facility_name="Cedar-Sinai Medical Center",
        network_status=NetworkStatus.IN_NETWORK,
        is_emergency=False,
        prior_auth_obtained=True,
        prior_auth_required=True,
        pcp_referral_obtained=True,
    )


@pytest.fixture
def sample_claim_oon_emergency():
    """An out-of-network emergency — NSA should apply."""
    from datetime import date
    from app.models.claim import ClaimCase
    from app.models.enums import NetworkStatus

    return ClaimCase(
        cpt_code="99285",
        cpt_description="Emergency Department Visit, High Severity",
        icd_10_code="I21.0",
        icd_10_description="Acute ST elevation myocardial infarction",
        date_of_service=date(2025, 7, 1),
        billed_amount=25000.0,
        facility_name="Community General Hospital",
        network_status=NetworkStatus.OUT_OF_NETWORK,
        is_emergency=True,
        nsa_applies=True,
        nsa_reason="Emergency service at out-of-network facility",
    )
