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


# ACA federal OOP max ceiling for plan year 2026.
# Source: CMS/HHS Notice of Benefit and Payment Parameters for 2026.
ACA_OOP_MAX_INDIVIDUAL_2026 = 10_600.00
ACA_OOP_MAX_FAMILY_2026 = 21_200.00


def _determine_copay(policy: PolicyProfile, claim: ClaimCase) -> float:
    """
    Determine the applicable copay by mapping the claim's CPT code
    to the correct tier in the policy's CopaySchedule.
    
    CPT code ranges follow AMA conventions:
    - 99201-99215: Office/outpatient E&M (PCP and specialist visits)
    - 99281-99285: Emergency department visits
    - 99241-99245: Consultations (specialist)
    - 99381-99397: Preventive visits
    - 90000-90999: Psychiatric/therapy
    - Prescription drugs are identified by HCPCS J-codes
    """
    copay = policy.copay_schedule
    cpt = claim.cpt_code.upper().strip()
    desc = claim.cpt_description.lower()

    val = 0.0
    # Emergency Room
    if cpt.startswith("9928") or "emergency" in desc or "er visit" in desc:
        val = copay.emergency_room

    # Urgent Care
    elif "urgent care" in desc:
        val = copay.urgent_care

    # Specialty Rx (HCPCS J-codes are injectable/infusion drugs)
    elif cpt.startswith("J"):
        val = copay.specialty_rx

    # Psychiatry / Therapy
    elif cpt.startswith("908") or cpt.startswith("909") or "therapy" in desc or "psychiatr" in desc:
        val = copay.specialist

    # Preventive care visits (typically $0 copay under ACA, but use schedule)
    elif cpt.startswith("9938") or cpt.startswith("9939"):
        val = copay.primary_care

    # Office visits — determine PCP vs Specialist
    elif cpt.startswith("992"):
        # 99201-99215 are standard office visits
        # Specialist keywords in description
        specialist_keywords = [
            "specialist", "cardio", "ortho", "neuro", "derma", "gastro",
            "oncol", "pulmon", "endocrin", "rheumat", "urolog", "surgeon",
        ]
        if any(kw in desc for kw in specialist_keywords):
            val = copay.specialist
        else:
            val = copay.primary_care

    # Surgical and hospital-based procedures typically don't have copays
    # (they go through deductible + coinsurance waterfall)
    return float(val or 0.0)



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
    # The No Surprises Act has two main triggering scenarios that we must detect:
    #
    # Scenario A (Emergency): Patient receives emergency services at any facility.
    #   → Force in-network cost-sharing.
    #
    # Scenario B (Ancillary Provider at INN Facility): An OON ancillary provider
    #   (e.g., anesthesiologist, radiologist, pathologist) renders services at an
    #   IN-NETWORK facility. The patient had no meaningful opportunity to choose
    #   this provider, so balance billing is ILLEGAL.
    #   → Force in-network cost-sharing for the ancillary provider.
    #   → Flag the ILLEGAL BALANCE BILLED AMOUNT for the appeal agent.
    #
    # Scenario C (Standard OON): Patient voluntarily chose an OON provider
    #   at a non-emergency, non-ancillary context.
    #   → Apply OON cost-sharing rates.
    use_in_network_rates = True
    nsa_violation_detected = False
    illegal_balance_billed_amount = 0.0

    # NSA Ancillary types per 45 CFR § 149.410(b) and the NSA regulations
    NSA_ANCILLARY_TYPES = {
        "anesthesiology", "anesthesia", "radiology", "pathology",
        "neonatology", "assistant surgeon", "hospitalist", "intensivist",
        "diagnostic imaging",
    }

    if claim.network_status == NetworkStatus.OUT_OF_NETWORK:
        # ── Scenario A: Emergency (pre-existing check, enhanced) ──────
        if claim.is_emergency:
            notes.append(
                "No Surprises Act / EMTALA (Scenario A — Emergency): Patient cost-sharing "
                "calculated at IN-NETWORK rates. Emergency services are protected regardless "
                "of facility or provider network status."
            )
            use_in_network_rates = True

        # ── Scenario B: OON Ancillary Provider at INN Facility ────────
        elif (
            claim.facility_network_status == NetworkStatus.IN_NETWORK
            and claim.ancillary_service_type is not None
            and claim.ancillary_service_type.lower() in NSA_ANCILLARY_TYPES
        ):
            nsa_violation_detected = True
            use_in_network_rates = True
            # The "illegal balance" is the full billed amount, because the insurer
            # paid $0 and told the patient they owe 100% — which violates the NSA.
            # The legal patient responsibility will be capped at INN cost-sharing below.
            illegal_balance_billed_amount = effective_allowed
            notes.append(
                f"⚠️ NSA VIOLATION DETECTED (Scenario B — Ancillary Provider Balance Billing): "
                f"Provider '{claim.provider_name or 'Unknown'}' is OUT-OF-NETWORK for "
                f"{claim.ancillary_service_type} services, but the FACILITY "
                f"('{claim.facility_name or 'Unknown'}') is IN-NETWORK. "
                f"Under 45 CFR § 149.410(b) of the No Surprises Act, this provider CANNOT "
                f"balance bill the patient. Patient cost-sharing is capped at the IN-NETWORK "
                f"rate. Provider must bill the plan directly and negotiate via the IDR process."
            )
            notes.append(
                f"ILLEGAL AMOUNT ATTEMPTED: The EOB incorrectly assigns "
                f"${illegal_balance_billed_amount:,.2f} as patient responsibility. "
                f"Legal maximum patient responsibility is calculated below using INN rates."
            )
            # Also trigger the nsa_applies flag for downstream agents
            claim = claim.model_copy(update={"nsa_applies": True, "nsa_reason": (
                f"OON {claim.ancillary_service_type} provider at INN facility — "
                "NSA balance billing prohibition applies per 45 CFR § 149.410(b)."
            )})

        # ── Scenario C: Standard OON — apply OON rates ────────────────
        elif policy.out_of_network_coinsurance is not None:
            use_in_network_rates = False
            notes.append(
                "Out-of-network rates applied: Patient voluntarily used an OON provider "
                "in a non-emergency, non-ancillary context. OON deductible and higher "
                "coinsurance rates apply per the plan's schedule of benefits."
            )
        else:
            # PPO/POS with no OON benefits defined — unusual, deny
            notes.append(
                "DENIED: Plan does not define out-of-network benefits and no NSA "
                "exception applies."
            )
            return _create_denial(
                claim=claim,
                allowed=effective_allowed,
                reason=DenialReason.OUT_OF_NETWORK_DENIAL,
                notes=notes,
                policy=policy,
            )

        # If explicitly flagged by upstream agent (e.g., claim intake), honor it
        if claim.nsa_applies and not nsa_violation_detected and not claim.is_emergency:
            notes.append(
                "No Surprises Act applies (flagged by intake agent): "
                "Patient cost-sharing calculated at IN-NETWORK rates."
            )
            use_in_network_rates = True

    # ── Select cost-sharing parameters based on network ───────────
    if use_in_network_rates:
        deductible_total = float(policy.in_network_deductible_individual or 0.0)
        oop_max_total = float(policy.in_network_oop_max_individual or 0.0)
        coinsurance_rate = float(policy.in_network_coinsurance or 0.0)
    else:
        deductible_total = float(policy.out_of_network_deductible_individual or policy.in_network_deductible_individual or 0.0)
        oop_max_total = float(policy.out_of_network_oop_max_individual or policy.in_network_oop_max_individual or 0.0)
        coinsurance_rate = float(policy.out_of_network_coinsurance or policy.in_network_coinsurance or 0.0)

    # ── Step 4: Deductible Accumulation ───────────────────────────
    deductible_remaining = max(deductible_total - float(policy.deductible_met or 0.0), 0.0)
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

    # ── Copay (category-based from CopaySchedule) ──────────────────
    copay_amount = _determine_copay(policy, claim)
    standard_patient_total = applied_to_deductible + coinsurance_amount

    if copay_amount > 0:
        cpt = claim.cpt_code.upper().strip()
        desc = claim.cpt_description.lower()

        # Emergency visits: NSA/EMTALA mandate in-network cost-sharing treatment.
        # The deductible + coinsurance waterfall already applies — do not stack copay.
        if claim.is_emergency:
            notes.append(
                f"Copay waived: Emergency visit — deductible + coinsurance waterfall applies "
                f"instead of stacking ${copay_amount:,.2f} copay (NSA/EMTALA)."
            )
            patient_total = standard_patient_total

        else:
            copay_can_replace_waterfall = (
                cpt.startswith("992")
                or cpt.startswith("908")
                or cpt.startswith("909")
                or "urgent care" in desc
                or "therapy" in desc
                or "psychiatr" in desc
            )

            if copay_can_replace_waterfall and copay_amount < standard_patient_total:
                notes.append(
                    f"Copay protection: ${copay_amount:,.2f} used for this visit category "
                    "instead of stacking deductible and coinsurance, because the parsed plan "
                    "does not prove both should apply. Verify this against the SBC/EOB."
                )
                applied_to_deductible = 0.0
                coinsurance_amount = 0.0
                patient_total = copay_amount
            else:
                notes.append(
                    f"Copay: ${copay_amount:,.2f} applied for this service category."
                )
                patient_total = standard_patient_total + copay_amount
    else:
        patient_total = standard_patient_total

    # ── Step 7: OOP Max Cap ───────────────────────────────────────
    oop_remaining = max(oop_max_total - float(policy.oop_met or 0.0), 0.0)
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
    if policy.in_network_oop_max_individual > ACA_OOP_MAX_INDIVIDUAL_2026:
        notes.append(
            f"⚠️ WARNING: Plan OOP max (${policy.in_network_oop_max_individual:,.2f}) "
            f"exceeds ACA federal ceiling (${ACA_OOP_MAX_INDIVIDUAL_2026:,.2f}). "
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
        nsa_violation_detected=nsa_violation_detected,
        illegal_balance_billed_amount=illegal_balance_billed_amount,
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
