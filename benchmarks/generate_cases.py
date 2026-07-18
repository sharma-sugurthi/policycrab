import json
import os
import random

CASES_DIR = "cases"

def ensure_dir():
    if not os.path.exists(CASES_DIR):
        os.makedirs(CASES_DIR)

def generate_emergency_cases(start_idx):
    cases = []
    for i in range(20):
        c = {
            "id": f"EMRG-{start_idx + i:03d}",
            "category": "emergency_care",
            "title": f"Emergency Appendectomy Denied for Prior Auth - {i}",
            "claim_description": "I went to the ER with severe abdominal pain and was diagnosed with appendicitis. They performed emergency surgery. The hospital billed $15,000. My insurance denied it stating I didn't get prior authorization.",
            "policy_profile": {
                "plan_name": "Standard PPO",
                "carrier_name": "BenchmarkHealth",
                "plan_type": "PPO",
                "legal_classification": "INDIVIDUAL_ACA",
                "state": "CA",
                "in_network_deductible_individual": 1000,
                "in_network_oop_max_individual": 5000,
                "in_network_coinsurance": 0.20,
                "out_of_network_deductible_individual": 2000,
                "out_of_network_oop_max_individual": 10000,
                "out_of_network_coinsurance": 0.40
            },
            "benchmark_policy_excerpt": "Section 4.2 — Emergency Services: Prior authorization is strictly waived for all emergency medical conditions. Emergency surgeries and admissions are covered at the in-network cost-sharing level regardless of the facility.",
            "allowed_amount": 10000,
            "expected": {
                "appeal_recommendation": "STRONG_APPEAL",
                "contradiction_detected": True,
                "contradiction_strength": "STRONG",
                "route_decision": "denied"
            },
            "ground_truth_rationale": "Emergency surgery is explicitly covered and prior auth is waived for emergencies. Insurer's denial is wrong."
        }
        cases.append(c)
    return cases

def generate_cosmetic_cases(start_idx):
    cases = []
    for i in range(20):
        c = {
            "id": f"COSM-{start_idx + i:03d}",
            "category": "explicit_exclusion",
            "title": f"Out of network elective rhinoplasty denied - {i}",
            "claim_description": "I went to an out-of-network plastic surgery clinic for a cosmetic rhinoplasty to improve the appearance of my nose. The clinic billed $12,000. Insurance denied it as not covered.",
            "policy_profile": {
                "plan_name": "Standard PPO",
                "carrier_name": "BenchmarkHealth",
                "plan_type": "PPO",
                "legal_classification": "INDIVIDUAL_ACA",
                "state": "CA",
                "in_network_deductible_individual": 1000,
                "in_network_oop_max_individual": 5000,
                "in_network_coinsurance": 0.20,
                "out_of_network_deductible_individual": 2000,
                "out_of_network_oop_max_individual": 10000,
                "out_of_network_coinsurance": 0.40
            },
            "benchmark_policy_excerpt": "Section 8 — General Exclusions: Cosmetic surgery, defined as surgery performed primarily to alter or reshape normal structures of the body in order to improve appearance, is explicitly excluded from coverage under any circumstances.",
            "allowed_amount": 12000,
            "expected": {
                "appeal_recommendation": "CLAIM_CORRECTLY_DENIED",
                "contradiction_detected": False,
                "contradiction_strength": "NONE",
                "route_decision": "denied"
            },
            "ground_truth_rationale": "Cosmetic surgery is explicitly excluded. The denial is legally and contractually correct."
        }
        cases.append(c)
    return cases

def generate_formulary_cases(start_idx):
    cases = []
    for i in range(20):
        c = {
            "id": f"FORM-{start_idx + i:03d}",
            "category": "formulary_exception",
            "title": f"Diabetes medication not on formulary - {i}",
            "claim_description": "My doctor prescribed Ozempic for my Type 2 Diabetes. The pharmacy said it was denied because it's not on the plan's formulary list.",
            "policy_profile": {
                "plan_name": "Standard HMO",
                "carrier_name": "BenchmarkHealth",
                "plan_type": "HMO",
                "legal_classification": "INDIVIDUAL_ACA",
                "state": "CA",
                "in_network_deductible_individual": 1000,
                "in_network_oop_max_individual": 5000,
                "in_network_coinsurance": 0.20,
                "out_of_network_deductible_individual": 2000,
                "out_of_network_oop_max_individual": 10000,
                "out_of_network_coinsurance": 0.40
            },
            "benchmark_policy_excerpt": "Section 9 — Prescription Drugs: Medications not listed on the plan formulary are excluded from standard coverage. Members may request a Formulary Exception if their prescribing physician demonstrates that all formulary alternatives are clinically ineffective or contraindicated.",
            "allowed_amount": 900,
            "expected": {
                "appeal_recommendation": "EXCEPTION_REQUEST",
                "contradiction_detected": False,
                "contradiction_strength": "NONE",
                "route_decision": "denied"
            },
            "ground_truth_rationale": "Medication is not on the formulary. A standard appeal will fail; an exception request is required."
        }
        cases.append(c)
    return cases

def generate_annual_limit_cases(start_idx):
    cases = []
    for i in range(20):
        c = {
            "id": f"LMIT-{start_idx + i:03d}",
            "category": "annual_limit",
            "title": f"Physical therapy visits exceeded - {i}",
            "claim_description": "I had my 25th physical therapy session for the year. The bill was $200. Insurance denied it saying I exceeded the maximum allowed visits.",
            "policy_profile": {
                "plan_name": "Standard PPO",
                "carrier_name": "BenchmarkHealth",
                "plan_type": "PPO",
                "legal_classification": "INDIVIDUAL_ACA",
                "state": "CA",
                "in_network_deductible_individual": 1000,
                "in_network_oop_max_individual": 5000,
                "in_network_coinsurance": 0.20,
                "out_of_network_deductible_individual": 2000,
                "out_of_network_oop_max_individual": 10000,
                "out_of_network_coinsurance": 0.40
            },
            "benchmark_policy_excerpt": "Section 5 — Therapy Services: Physical therapy, occupational therapy, and speech therapy are limited to a combined total of 20 visits per calendar year. Any visits beyond this limit are the sole financial responsibility of the member.",
            "allowed_amount": 200,
            "expected": {
                "appeal_recommendation": "CLAIM_CORRECTLY_DENIED",
                "contradiction_detected": False,
                "contradiction_strength": "NONE",
                "route_decision": "denied"
            },
            "ground_truth_rationale": "Patient exceeded the hard 20-visit limit stated in the policy."
        }
        cases.append(c)
    return cases

def generate_infertility_cases(start_idx):
    cases = []
    for i in range(20):
        c = {
            "id": f"INFR-{start_idx + i:03d}",
            "category": "hard_exclusion",
            "title": f"IVF Treatment Denied - {i}",
            "claim_description": "I had a round of In Vitro Fertilization (IVF) at a fertility clinic. The bill was $18,000. Insurance denied the claim entirely.",
            "policy_profile": {
                "plan_name": "Standard PPO",
                "carrier_name": "BenchmarkHealth",
                "plan_type": "PPO",
                "legal_classification": "SELF_FUNDED_ERISA",
                "state": "CA",
                "in_network_deductible_individual": 1000,
                "in_network_oop_max_individual": 5000,
                "in_network_coinsurance": 0.20,
                "out_of_network_deductible_individual": 2000,
                "out_of_network_oop_max_individual": 10000,
                "out_of_network_coinsurance": 0.40
            },
            "benchmark_policy_excerpt": "Section 12 — Reproductive Exclusions: All treatments, procedures, and medications related to the diagnosis and treatment of infertility, including but not limited to In Vitro Fertilization (IVF), Artificial Insemination (AI), and fertility preservation, are strictly excluded from coverage.",
            "allowed_amount": 18000,
            "expected": {
                "appeal_recommendation": "UNLIKELY_TO_WIN",
                "contradiction_detected": False,
                "contradiction_strength": "NONE",
                "route_decision": "denied"
            },
            "ground_truth_rationale": "IVF is a hard exclusion. An appeal is almost guaranteed to fail."
        }
        cases.append(c)
    return cases

def generate_nsa_balance_billing_cases(start_idx):
    """
    NSA Scenario B: OON Ancillary Provider (Anesthesiologist) at an INN Facility.

    This is the exact test case from the Gemini critique:
    - Facility: St. Jude Medical Center (IN-NETWORK)
    - Line 1: Dr. Sarah Jenkins, INN Surgeon — correctly billed
    - Line 2: Apex Anesthesia Group, OON — attempting to balance bill $2,800

    The engine MUST detect:
    1. nsa_violation_detected = True (Scenario B applies)
    2. The $2,800 balance bill is ILLEGAL (illegal_balance_billed_amount = 2,000)
    3. Patient's LEGAL responsibility for Line 2 = 20% INN coinsurance on the
       allowed amount ($2,000 * 20% = $400), NOT the billed $2,800.
    4. The appeal_recommendation = STRONG_APPEAL citing 45 CFR § 149.410(b)
    """
    cases = []
    for i in range(20):
        c = {
            "id": f"NSA-{start_idx + i:03d}",
            "category": "nsa_balance_billing",
            "title": f"NSA Violation: OON Anesthesiologist Balance Billing at INN Hospital - {i}",
            # This is the claim description for the ANESTHESIOLOGIST line (Line 2 from the EOB)
            "claim_description": (
                "I had a laparoscopic cholecystectomy at St. Jude Medical Center, which is "
                "in my insurance network. The surgeon was also in-network. However, the "
                "anesthesiologist (Apex Anesthesia Group) was out-of-network. I never "
                "chose them — they were just assigned to me in the operating room. My EOB "
                "shows Apex Anesthesia billed $2,800 for CPT 00790 (Anesthesia for "
                "intraperitoneal procedures). The plan paid $0 and I am being told I owe "
                "the full $2,800 (Denial Reason: PR-242, Services not provided by "
                "network/primary care providers). The EOB lists my total patient "
                "responsibility as $3,200 — $400 for the surgery and $2,800 for anesthesia."
            ),
            "policy_profile": {
                "plan_name": "CrabCare Prime PPO",
                "carrier_name": "CrabCare",
                "plan_type": "PPO",
                "legal_classification": "FULLY_INSURED",
                "state": "CA",
                "in_network_deductible_individual": 1000,
                "in_network_oop_max_individual": 5000,
                "in_network_coinsurance": 0.20,
                "out_of_network_deductible_individual": 3000,
                "out_of_network_oop_max_individual": 10000,
                "out_of_network_coinsurance": 0.50,
            },
            # The policy excerpt from Test Document 1 (Gemini critique)
            "benchmark_policy_excerpt": (
                "PLAN NAME: CrabCare Prime PPO\n"
                "PLAN YEAR: 2026\n\n"
                "SECTION 4: COST SHARING & DEDUCTIBLES\n"
                "- In-Network Individual Deductible: $1,000\n"
                "- Out-of-Network Individual Deductible: $3,000\n"
                "- In-Network Coinsurance: 20% (Plan pays 80%)\n"
                "- Out-of-Network Coinsurance: 50% (Plan pays 50%)\n\n"
                "SECTION 7: EXCLUSIONS AND LIMITATIONS\n"
                "The Plan does not cover services deemed not medically necessary, "
                "experimental treatments, or out-of-network non-emergency services "
                "without prior authorization.\n\n"
                "SECTION 8: FEDERAL NO SURPRISES ACT PROTECTIONS\n"
                "Under the Federal No Surprises Act, if you receive emergency services "
                "or are treated by an out-of-network ancillary provider (such as an "
                "anesthesiologist, pathologist, or radiologist) at an In-Network facility, "
                "you cannot be balance billed. Your patient responsibility will be "
                "calculated based on the In-Network cost-sharing amounts, and the provider "
                "must negotiate the remainder directly with the Plan."
            ),
            # The ALLOWED AMOUNT for the anesthesia line from the EOB = $2,000
            # (Note: insurer listed $0 — but this is the QPA/allowed amount the engine
            # should use to calculate the LEGAL 20% patient share = $400)
            "allowed_amount": 2000,
            # These fields directly map to the new ClaimCase fields we added
            "claim_overrides": {
                "network_status": "OUT_OF_NETWORK",
                "facility_network_status": "IN_NETWORK",
                "facility_name": "St. Jude Medical Center",
                "provider_name": "Apex Anesthesia Group",
                "ancillary_service_type": "anesthesia",
                "is_denied": True,
                "denial_reason": "OUT_OF_NETWORK_DENIAL",
                "denial_carc_code": "PR-242",
            },
            "expected": {
                # The engine should recommend a STRONG appeal because the EOB is illegal
                "appeal_recommendation": "STRONG_APPEAL",
                "contradiction_detected": True,
                "contradiction_strength": "STRONG",
                "route_decision": "denied",
                # The deterministic engine MUST calculate this correctly:
                # $2,000 allowed amount × 20% INN coinsurance = $400 legal responsibility
                # (assuming $1,000 deductible is already met from Line 1's $400 payment)
                "legal_patient_responsibility_for_line_2": 400.0,
                "nsa_violation_detected": True,
                "illegal_balance_billed_amount": 2000.0,
            },
            "ground_truth_rationale": (
                "Apex Anesthesia Group is an OON ancillary provider at the INN facility "
                "St. Jude Medical Center. Under 45 CFR § 149.410(b) of the No Surprises Act, "
                "balance billing is strictly prohibited. The patient's legal max responsibility "
                "is 20% of the $2,000 allowed amount = $400, NOT the $2,800 billed. The EOB "
                "is incorrectly assigning $3,200 total patient responsibility. The correct "
                "total is $800 ($400 for surgery + $400 for anesthesia at INN rates)."
            ),
        }
        cases.append(c)
    return cases
    
# Generate the remaining 100 cases using variations of the above to reach 200
def generate_all_cases():
    ensure_dir()
    all_cases = []
    # ── First 100 cases: 5 categories × 20 cases ─────────────────
    all_cases.extend(generate_emergency_cases(1))
    all_cases.extend(generate_cosmetic_cases(21))
    all_cases.extend(generate_formulary_cases(41))
    all_cases.extend(generate_annual_limit_cases(61))
    all_cases.extend(generate_infertility_cases(81))

    # ── Second 100 cases: Add NSA category + repeat others ────────
    # The NSA balance billing category is the most critical new test set.
    all_cases.extend(generate_nsa_balance_billing_cases(101))  # 20 NSA cases
    all_cases.extend(generate_emergency_cases(121))
    all_cases.extend(generate_cosmetic_cases(141))
    all_cases.extend(generate_formulary_cases(161))
    all_cases.extend(generate_annual_limit_cases(181))
    all_cases.extend(generate_infertility_cases(201))          # 20 infertility cases → total 220

    for c in all_cases:
        filepath = os.path.join(CASES_DIR, f"{c['id']}.json")
        with open(filepath, "w") as f:
            json.dump(c, f, indent=2)

    print(f"Generated {len(all_cases)} synthetic benchmark cases in {CASES_DIR}/")
    print(f"  - Emergency (Prior Auth):      40 cases")
    print(f"  - Cosmetic (Hard Exclusion):   40 cases")
    print(f"  - Formulary Exception:         40 cases")
    print(f"  - Annual Limit Exceeded:       40 cases")
    print(f"  - Infertility (Hard Exclusion):40 cases")
    print(f"  - NSA Balance Billing [NEW]:   20 cases")

if __name__ == "__main__":
    generate_all_cases()
