"""
Deterministic Cost Calculator Engine — the core financial logic.

This module performs the cost-sharing waterfall calculation using
ONLY deterministic Python math. No LLMs are involved.

Waterfall sequence:
1. Prior Authorization check
2. Network/Referral check
3. NSA override (if applicable)
4. Deductible accumulation
5. Coinsurance application
6. OOP Max cap
"""

from app.models.policy import PolicyProfile
from app.models.claim import ClaimCase, CostBreakdown
from app.models.enums import (
    NetworkStatus,
    PlanType,
    ClaimStatus,
    DenialReason,
)


# ACA federal OOP max ceiling (2025 values — update annually)
ACA_OOP_MAX_INDIVIDUAL_2025 = 9_200.00
ACA_OOP_MAX_FAMILY_2025 = 18_400.00


def calculate_cost(
    policy: PolicyProfile,
    claim: ClaimCase,
    allowed_amount: float | None = None,
) -> CostBreakdown:
    """
    Execute the deterministic cost-sharing waterfall.

    Args:
        policy: The patient's parsed PolicyProfile.
        claim: The structured ClaimCase.
        allowed_amount: The plan's allowed amount (negotiated rate).
                       If None, defaults to billed_amount (worst case for uninsured).

    Returns:
        CostBreakdown with all calculation details.
    """
    notes: list[str] = []
    effective_allowed = allowed_amount if allowed_amount is not None else claim.billed_amount

    # ── Step 1: Prior Authorization Check ─────────────────────────
    if claim.prior_auth_required and not claim.prior_auth_obtained:
        if not claim.is_emergency:
            notes.append(
                f"DENIED: Prior authorization required for CPT {claim.cpt_code} "
                f"but was not obtained. Emergency exception does not apply."
            )
            return _create_denial(
                claim=claim,
                allowed=effective_allowed,
                reason=DenialReason.PRIOR_AUTH_MISSING,
                notes=notes,
                policy=policy,
            )
        else:
            notes.append(
                "Prior authorization was required but not obtained. "
                "Emergency exception applies — prior auth requirement waived per EMTALA/NSA."
            )

    # ── Step 2: Network Check ─────────────────────────────────────
    if claim.network_status == NetworkStatus.OUT_OF_NETWORK and not claim.is_emergency:
        if policy.plan_type in (PlanType.HMO, PlanType.EPO):
            notes.append(
                f"DENIED: {policy.plan_type.value} plan does not cover "
                f"out-of-network services for non-emergency care."
            )
            return _create_denial(
                claim=claim,
                allowed=effective_allowed,
                reason=DenialReason.OUT_OF_NETWORK_DENIAL,
                notes=notes,
                policy=policy,
            )

    # ── Step 2b: PCP Referral Check (HMO/POS) ────────────────────
    if policy.requires_pcp_referral and not claim.is_emergency:
        if claim.pcp_referral_obtained is False:
            notes.append(
                f"DENIED: {policy.plan_type.value} plan requires a PCP referral "
                f"for specialist services. No referral was obtained."
            )
            return _create_denial(
                claim=claim,
                allowed=effective_allowed,
                reason=DenialReason.REFERRAL_MISSING,
                notes=notes,
                policy=policy,
            )

    # ── Step 3: NSA Override ──────────────────────────────────────
    use_in_network_rates = True
    if claim.network_status == NetworkStatus.OUT_OF_NETWORK:
        if claim.nsa_applies or claim.is_emergency:
            notes.append(
                "No Surprises Act applies: patient cost-sharing calculated at "
                "IN-NETWORK rates despite out-of-network provider."
            )
            use_in_network_rates = True
        elif policy.out_of_network_coinsurance is not None:
            use_in_network_rates = False
            notes.append(
                "Out-of-network rates applied. Patient is responsible for "
                "OON deductible and higher coinsurance percentage."
            )
        else:
            # PPO/POS with no OON benefits defined — unusual, deny
            notes.append(
                "DENIED: Plan does not define out-of-network benefits."
            )
            return _create_denial(
                claim=claim,
                allowed=effective_allowed,
                reason=DenialReason.OUT_OF_NETWORK_DENIAL,
                notes=notes,
                policy=policy,
            )

    # ── Select cost-sharing parameters based on network ───────────
    if use_in_network_rates:
        deductible_total = policy.in_network_deductible_individual
        oop_max_total = policy.in_network_oop_max_individual
        coinsurance_rate = policy.in_network_coinsurance
    else:
        deductible_total = policy.out_of_network_deductible_individual or 0
        oop_max_total = policy.out_of_network_oop_max_individual or policy.in_network_oop_max_individual
        coinsurance_rate = policy.out_of_network_coinsurance or policy.in_network_coinsurance

    # ── Step 4: Deductible Accumulation ───────────────────────────
    deductible_remaining = max(deductible_total - policy.deductible_met, 0)
    applied_to_deductible = min(effective_allowed, deductible_remaining)
    post_deductible_amount = effective_allowed - applied_to_deductible

    if applied_to_deductible > 0:
        notes.append(
            f"Deductible: ${applied_to_deductible:,.2f} applied to remaining "
            f"${deductible_remaining:,.2f} deductible."
        )

    # ── Step 5: Coinsurance Application ───────────────────────────
    coinsurance_amount = post_deductible_amount * coinsurance_rate

    if coinsurance_amount > 0:
        notes.append(
            f"Coinsurance: {coinsurance_rate * 100:.0f}% of ${post_deductible_amount:,.2f} "
            f"= ${coinsurance_amount:,.2f} patient responsibility."
        )

    # ── Copay (if applicable) ─────────────────────────────────────
    # Note: copay handling depends on plan design. Some plans apply copay
    # instead of coinsurance for certain visit types. For now, copay = 0
    # unless explicitly provided. This can be enhanced per plan rules.
    copay_amount = 0.0

    # ── Step 6: Calculate totals ──────────────────────────────────
    patient_total = applied_to_deductible + coinsurance_amount + copay_amount

    # ── Step 7: OOP Max Cap ───────────────────────────────────────
    oop_remaining = max(oop_max_total - policy.oop_met, 0)
    hit_oop_max = False

    if patient_total > oop_remaining:
        notes.append(
            f"OOP Max reached: Patient responsibility capped at "
            f"${oop_remaining:,.2f} (remaining OOP max). "
            f"Plan pays the excess ${patient_total - oop_remaining:,.2f}."
        )
        patient_total = oop_remaining
        hit_oop_max = True

    insurer_payout = effective_allowed - patient_total

    # ── Validate against ACA OOP ceiling ──────────────────────────
    if policy.in_network_oop_max_individual > ACA_OOP_MAX_INDIVIDUAL_2025:
        notes.append(
            f"⚠️ WARNING: Plan OOP max (${policy.in_network_oop_max_individual:,.2f}) "
            f"exceeds ACA federal ceiling (${ACA_OOP_MAX_INDIVIDUAL_2025:,.2f}). "
            f"This may indicate a non-compliant or grandfathered plan."
        )

    return CostBreakdown(
        billed_amount=claim.billed_amount,
        allowed_amount=effective_allowed,
        applied_to_deductible=applied_to_deductible,
        coinsurance_amount=coinsurance_amount if not hit_oop_max else max(patient_total - applied_to_deductible, 0),
        copay_amount=copay_amount,
        total_patient_responsibility=patient_total,
        total_insurer_payout=insurer_payout,
        deductible_remaining_after=max(deductible_remaining - applied_to_deductible, 0),
        oop_remaining_after=max(oop_remaining - patient_total, 0),
        hit_oop_max=hit_oop_max,
        claim_status=ClaimStatus.APPROVED,
        calculation_notes=notes,
    )


def _create_denial(
    claim: ClaimCase,
    allowed: float,
    reason: DenialReason,
    notes: list[str],
    policy: PolicyProfile,
) -> CostBreakdown:
    """Create a CostBreakdown representing a denial."""
    return CostBreakdown(
        billed_amount=claim.billed_amount,
        allowed_amount=allowed,
        applied_to_deductible=0,
        coinsurance_amount=0,
        copay_amount=0,
        total_patient_responsibility=0,
        total_insurer_payout=0,
        deductible_remaining_after=max(
            policy.in_network_deductible_individual - policy.deductible_met, 0
        ),
        oop_remaining_after=max(
            policy.in_network_oop_max_individual - policy.oop_met, 0
        ),
        hit_oop_max=False,
        claim_status=ClaimStatus.DENIED,
        denial_reason=reason,
        calculation_notes=notes,
    )
