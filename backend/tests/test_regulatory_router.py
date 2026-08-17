"""
Tests for the Regulatory Router — verifies correct appeal framework
selection for every plan legal classification.
"""

from datetime import date
from app.engine.regulatory_router import route_to_appeal_framework, get_appeal_framework_details
from app.models.claim import ClaimCase
from app.models.policy import PolicyProfile
from app.models.enums import (
    AppealFramework, PlanLegalClassification, PlanType, NetworkStatus,
)


def _make_policy(classification: PlanLegalClassification) -> PolicyProfile:
    """Helper to create a minimal policy with a given legal classification."""
    return PolicyProfile(
        plan_name="Test Plan",
        carrier_name="Test Carrier",
        plan_type=PlanType.PPO,
        legal_classification=classification,
        state="TX",
        in_network_deductible_individual=1000,
        in_network_oop_max_individual=5000,
        in_network_coinsurance=0.20,
    )


def _make_claim(nsa_applies: bool = False, is_emergency: bool = False) -> ClaimCase:
    """Helper to create a minimal claim."""
    return ClaimCase(
        cpt_code="99213",
        cpt_description="Office Visit",
        icd_10_code="J06.9",
        icd_10_description="URI",
        date_of_service=date(2025, 6, 1),
        billed_amount=200,
        network_status=NetworkStatus.IN_NETWORK,
        nsa_applies=nsa_applies,
        is_emergency=is_emergency,
    )


class TestNSAPriority:
    """NSA IDR takes priority over all other frameworks."""

    def test_nsa_overrides_erisa(self):
        policy = _make_policy(PlanLegalClassification.SELF_FUNDED_ERISA)
        claim = _make_claim(nsa_applies=True)
        assert route_to_appeal_framework(policy, claim) == AppealFramework.NSA_IDR

    def test_nsa_overrides_state(self):
        policy = _make_policy(PlanLegalClassification.FULLY_INSURED)
        claim = _make_claim(nsa_applies=True)
        assert route_to_appeal_framework(policy, claim) == AppealFramework.NSA_IDR

    def test_nsa_overrides_medicare(self):
        policy = _make_policy(PlanLegalClassification.MEDICARE_ADVANTAGE)
        claim = _make_claim(nsa_applies=True)
        assert route_to_appeal_framework(policy, claim) == AppealFramework.NSA_IDR


class TestPlanClassificationRouting:
    """Each plan classification routes to the correct framework."""

    def test_self_funded_erisa(self):
        policy = _make_policy(PlanLegalClassification.SELF_FUNDED_ERISA)
        claim = _make_claim()
        assert route_to_appeal_framework(policy, claim) == AppealFramework.ERISA_FEDERAL

    def test_fully_insured(self):
        policy = _make_policy(PlanLegalClassification.FULLY_INSURED)
        claim = _make_claim()
        assert route_to_appeal_framework(policy, claim) == AppealFramework.STATE_EXTERNAL_REVIEW

    def test_individual_aca(self):
        policy = _make_policy(PlanLegalClassification.INDIVIDUAL_ACA)
        claim = _make_claim()
        assert route_to_appeal_framework(policy, claim) == AppealFramework.ACA_MARKETPLACE_APPEAL

    def test_medicare_advantage(self):
        policy = _make_policy(PlanLegalClassification.MEDICARE_ADVANTAGE)
        claim = _make_claim()
        assert route_to_appeal_framework(policy, claim) == AppealFramework.MEDICARE_ADVANTAGE_5LEVEL

    def test_medicare_original(self):
        policy = _make_policy(PlanLegalClassification.MEDICARE_ORIGINAL)
        claim = _make_claim()
        assert route_to_appeal_framework(policy, claim) == AppealFramework.MEDICARE_ORIGINAL_5LEVEL

    def test_medicaid_managed(self):
        policy = _make_policy(PlanLegalClassification.MEDICAID_MANAGED)
        claim = _make_claim()
        assert route_to_appeal_framework(policy, claim) == AppealFramework.MEDICAID_FAIR_HEARING


class TestFrameworkDetails:
    """Verify detail retrieval for each framework."""

    def test_erisa_details_have_deadline(self):
        details = get_appeal_framework_details(AppealFramework.ERISA_FEDERAL)
        assert details["deadline_days"] == 180
        assert "29 CFR" in details["regulation"]

    def test_medicare_details_have_5_levels(self):
        details = get_appeal_framework_details(AppealFramework.MEDICARE_ADVANTAGE_5LEVEL)
        assert len(details["process"]) == 5

    def test_nsa_details_mention_qpa(self):
        details = get_appeal_framework_details(AppealFramework.NSA_IDR)
        assert any("QPA" in step for step in details["process"])

    def test_medicare_original_details_have_5_levels(self):
        """Original Medicare also has 5 levels but uses MAC and QIC, not MA plan and IRE."""
        details = get_appeal_framework_details(AppealFramework.MEDICARE_ORIGINAL_5LEVEL)
        assert len(details["process"]) == 5
        assert details["deadline_days"] == 120
        assert "MAC" in details["process"][0]
        assert "QIC" in details["process"][1]
        assert "42 CFR Part 405" in details["governing_law"]

    def test_medicaid_fair_hearing_details(self):
        """Medicaid uses a fair hearing process, not DOI complaints."""
        details = get_appeal_framework_details(AppealFramework.MEDICAID_FAIR_HEARING)
        assert details["deadline_days"] == 60
        assert "438.402" in details["governing_law"]
        assert any("Fair Hearing" in step for step in details["process"])
        assert "aid paid pending" in details["key_requirement"]

    def test_medicare_original_is_distinct_from_ma(self):
        """Original Medicare and Medicare Advantage should have different processes."""
        ma_details = get_appeal_framework_details(AppealFramework.MEDICARE_ADVANTAGE_5LEVEL)
        orig_details = get_appeal_framework_details(AppealFramework.MEDICARE_ORIGINAL_5LEVEL)
        # MA uses IRE at Level 2; Original uses QIC
        assert "IRE" in ma_details["process"][1]
        assert "QIC" in orig_details["process"][1]
        # Different deadline windows
        assert ma_details["deadline_days"] == 60
        assert orig_details["deadline_days"] == 120

    def test_aca_marketplace_details(self):
        details = get_appeal_framework_details(AppealFramework.ACA_MARKETPLACE_APPEAL)
        assert details["deadline_days"] == 180
        assert "147.136" in details["governing_law"]
        assert "External Review" in details["process"][1]
