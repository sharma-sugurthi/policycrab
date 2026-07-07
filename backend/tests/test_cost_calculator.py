"""
Tests for the Deterministic Cost Calculator Engine.

Covers the full waterfall:
- Prior auth denial
- HMO out-of-network denial
- PCP referral denial
- Standard in-network calculation
- NSA override for emergencies
- OOP max cap
- Deductible partially met
- ACA ceiling warning
"""

from datetime import date
from app.engine.cost_calculator import calculate_cost
from app.models.claim import ClaimCase
from app.models.policy import PolicyProfile, CopaySchedule
from app.models.enums import (
    NetworkStatus, PlanType, PlanLegalClassification,
    ClaimStatus, DenialReason,
)


class TestPriorAuthDenial:
    """Step 1: Claims denied for missing prior authorization."""

    def test_prior_auth_required_not_obtained(self, sample_ppo_policy, sample_claim_in_network):
        """Non-emergency claim without required prior auth → DENY."""
        claim = sample_claim_in_network.model_copy(
            update={"prior_auth_obtained": False, "prior_auth_required": True}
        )
        result = calculate_cost(sample_ppo_policy, claim, allowed_amount=30000)

        assert result.claim_status == ClaimStatus.DENIED
        assert result.denial_reason == DenialReason.PRIOR_AUTH_MISSING
        assert result.total_patient_responsibility == 0
        assert result.total_insurer_payout == 0

    def test_prior_auth_waived_for_emergency(self, sample_ppo_policy, sample_claim_in_network):
        """Emergency claim without prior auth → NOT denied (EMTALA/NSA waiver)."""
        claim = sample_claim_in_network.model_copy(
            update={"prior_auth_obtained": False, "prior_auth_required": True, "is_emergency": True}
        )
        result = calculate_cost(sample_ppo_policy, claim, allowed_amount=30000)

        assert result.claim_status == ClaimStatus.APPROVED
        assert any("Emergency exception" in n for n in result.calculation_notes)


class TestNetworkDenial:
    """Step 2: HMO/EPO out-of-network denials."""

    def test_hmo_oon_non_emergency_denied(self, sample_hmo_policy):
        """HMO + out-of-network + non-emergency → DENY."""
        claim = ClaimCase(
            cpt_code="99213",
            cpt_description="Office Visit, Established Patient",
            icd_10_code="J06.9",
            icd_10_description="Upper respiratory infection",
            date_of_service=date(2025, 6, 1),
            billed_amount=250.0,
            network_status=NetworkStatus.OUT_OF_NETWORK,
            is_emergency=False,
        )
        result = calculate_cost(sample_hmo_policy, claim, allowed_amount=150)

        assert result.claim_status == ClaimStatus.DENIED
        assert result.denial_reason == DenialReason.OUT_OF_NETWORK_DENIAL

    def test_hmo_oon_emergency_approved(self, sample_hmo_policy):
        """HMO + out-of-network + emergency → APPROVED (NSA/EMTALA)."""
        claim = ClaimCase(
            cpt_code="99285",
            cpt_description="ER Visit, High Severity",
            icd_10_code="I21.0",
            icd_10_description="Heart attack",
            date_of_service=date(2025, 7, 1),
            billed_amount=25000.0,
            network_status=NetworkStatus.OUT_OF_NETWORK,
            is_emergency=True,
            nsa_applies=True,
        )
        result = calculate_cost(sample_hmo_policy, claim, allowed_amount=15000)

        assert result.claim_status == ClaimStatus.APPROVED
        assert any("No Surprises Act" in n for n in result.calculation_notes)


class TestReferralDenial:
    """Step 2b: HMO/POS PCP referral check."""

    def test_hmo_no_referral_denied(self, sample_hmo_policy):
        """HMO + no PCP referral + non-emergency → DENY."""
        claim = ClaimCase(
            cpt_code="99214",
            cpt_description="Specialist Visit",
            icd_10_code="M54.5",
            icd_10_description="Low back pain",
            date_of_service=date(2025, 6, 1),
            billed_amount=300.0,
            network_status=NetworkStatus.IN_NETWORK,
            pcp_referral_obtained=False,
        )
        result = calculate_cost(sample_hmo_policy, claim, allowed_amount=200)

        assert result.claim_status == ClaimStatus.DENIED
        assert result.denial_reason == DenialReason.REFERRAL_MISSING

    def test_ppo_no_referral_approved(self, sample_ppo_policy):
        """PPO + no referral → APPROVED (PPOs don't require referrals)."""
        claim = ClaimCase(
            cpt_code="99214",
            cpt_description="Specialist Visit",
            icd_10_code="M54.5",
            icd_10_description="Low back pain",
            date_of_service=date(2025, 6, 1),
            billed_amount=300.0,
            network_status=NetworkStatus.IN_NETWORK,
            pcp_referral_obtained=False,
        )
        result = calculate_cost(sample_ppo_policy, claim, allowed_amount=200)

        assert result.claim_status == ClaimStatus.APPROVED


class TestStandardCostCalculation:
    """Steps 4-6: Deductible → Coinsurance → OOP Max waterfall."""

    def test_full_deductible_not_met(self, sample_ppo_policy, sample_claim_in_network):
        """$0 deductible met, $30K allowed → full waterfall."""
        result = calculate_cost(sample_ppo_policy, sample_claim_in_network, allowed_amount=30000)

        assert result.claim_status == ClaimStatus.APPROVED
        # $1,500 deductible applied
        assert result.applied_to_deductible == 1500.0
        # 20% of ($30,000 - $1,500) = 20% of $28,500 = $5,700
        # But total patient = $1,500 + $5,700 = $7,200
        # OOP max is $6,000, so capped at $6,000
        assert result.total_patient_responsibility == 6000.0
        assert result.hit_oop_max is True
        assert result.total_insurer_payout == 24000.0  # $30,000 - $6,000

    def test_deductible_partially_met(self, sample_ppo_policy, sample_claim_in_network):
        """$1,000 deductible already met → only $500 remaining."""
        policy = sample_ppo_policy.model_copy(update={"deductible_met": 1000.0})
        # Small claim that won't hit OOP max
        claim = sample_claim_in_network.model_copy(update={"billed_amount": 2000.0})

        result = calculate_cost(policy, claim, allowed_amount=1500)

        assert result.applied_to_deductible == 500.0  # Only $500 remaining
        # 20% of ($1,500 - $500) = 20% of $1,000 = $200
        assert result.coinsurance_amount == 200.0
        assert result.total_patient_responsibility == 700.0  # $500 + $200

    def test_deductible_fully_met(self, sample_ppo_policy, sample_claim_in_network):
        """Deductible already fully met → straight to coinsurance."""
        policy = sample_ppo_policy.model_copy(update={"deductible_met": 1500.0})
        claim = sample_claim_in_network.model_copy(update={"billed_amount": 5000.0})

        result = calculate_cost(policy, claim, allowed_amount=3500)

        assert result.applied_to_deductible == 0.0
        # 20% of $3,500 = $700
        assert result.coinsurance_amount == 700.0
        assert result.total_patient_responsibility == 700.0


class TestOOPMaxCap:
    """Step 7: Out-of-pocket maximum cap."""

    def test_oop_max_reached_during_claim(self, sample_ppo_policy, sample_claim_in_network):
        """OOP partially met, claim pushes past max → cap applied."""
        policy = sample_ppo_policy.model_copy(
            update={"deductible_met": 1500.0, "oop_met": 5500.0}
        )
        # OOP remaining = $6,000 - $5,500 = $500
        claim = sample_claim_in_network.model_copy(update={"billed_amount": 10000.0})

        result = calculate_cost(policy, claim, allowed_amount=8000)

        # 20% of $8,000 = $1,600 coinsurance, but OOP cap = $500
        assert result.total_patient_responsibility == 500.0
        assert result.hit_oop_max is True
        assert result.oop_remaining_after == 0.0

    def test_oop_already_maxed(self, sample_ppo_policy, sample_claim_in_network):
        """OOP already maxed out → patient pays $0."""
        policy = sample_ppo_policy.model_copy(
            update={"deductible_met": 1500.0, "oop_met": 6000.0}
        )

        result = calculate_cost(policy, claim=sample_claim_in_network, allowed_amount=30000)

        assert result.total_patient_responsibility == 0.0
        assert result.total_insurer_payout == 30000.0
        assert result.hit_oop_max is True


class TestNSAOverride:
    """Step 3: No Surprises Act forces in-network rates for emergencies."""

    def test_nsa_forces_in_network_rates(self, sample_ppo_policy, sample_claim_oon_emergency):
        """OON emergency with NSA → uses in-network coinsurance (20%, not 40%)."""
        result = calculate_cost(sample_ppo_policy, sample_claim_oon_emergency, allowed_amount=15000)

        assert result.claim_status == ClaimStatus.APPROVED
        # Should use in-network rates (20%) not OON (40%)
        assert any("No Surprises Act" in n for n in result.calculation_notes)
        # Deductible: $1,500 → Coinsurance: 20% of $13,500 = $2,700
        # Total: $1,500 + $2,700 = $4,200 (under $6K OOP max)
        assert result.applied_to_deductible == 1500.0
        assert result.total_patient_responsibility == 4200.0


class TestACACeilingWarning:
    """ACA OOP max validation."""

    def test_warns_if_oop_exceeds_aca_ceiling(self, sample_claim_in_network):
        """Plan with OOP max above ACA ceiling → warning note."""
        policy = PolicyProfile(
            plan_name="Overpriced Plan",
            carrier_name="BadInsurer",
            plan_type=PlanType.PPO,
            legal_classification=PlanLegalClassification.FULLY_INSURED,
            state="TX",
            in_network_deductible_individual=5000.0,
            in_network_oop_max_individual=15000.0,  # Above $9,200 ACA ceiling
            in_network_coinsurance=0.30,
        )
        result = calculate_cost(policy, sample_claim_in_network, allowed_amount=10000)

        assert any("ACA federal ceiling" in n for n in result.calculation_notes)
