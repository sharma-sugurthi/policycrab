import json
import os
import shutil

CASES_DIR = os.path.join(os.path.dirname(__file__), "cases")

def ensure_clean_dir():
    if os.path.exists(CASES_DIR):
        for f in os.listdir(CASES_DIR):
            if f.endswith(".json"):
                os.remove(os.path.join(CASES_DIR, f))
    else:
        os.makedirs(CASES_DIR, exist_ok=True)

def generate_emergency_cases(count=30):
    cases = []
    for i in range(1, count + 1):
        c = {
            "id": f"EMRG-{i:03d}",
            "category": "emergency_care",
            "title": f"Emergency Surgery Denied for Prior Auth - Scenario {i}",
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
            "claim_overrides": {
                "is_emergency": True,
                "is_denied": True,
                "denial_reason": "PRIOR_AUTH_MISSING",
                "denial_carc_code": "CO-197"
            },
            "expected": {
                "appeal_recommendation": "STRONG_APPEAL",
                "contradiction_detected": True,
                "contradiction_strength": "STRONG",
                "route_decision": "denied"
            },
            "ground_truth_rationale": "Emergency surgery is explicitly covered and prior auth is waived for emergencies under federal law and policy terms. Insurer's denial is wrong."
        }
        cases.append(c)
    return cases

def generate_cosmetic_cases(count=30):
    cases = []
    for i in range(1, count + 1):
        c = {
            "id": f"COSM-{i:03d}",
            "category": "explicit_exclusion",
            "title": f"Elective Rhinoplasty Denied as Cosmetic - Scenario {i}",
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
            "claim_overrides": {
                "is_emergency": False,
                "is_denied": True,
                "denial_reason": "NOT_COVERED",
                "denial_carc_code": "CO-96"
            },
            "expected": {
                "appeal_recommendation": "CLAIM_CORRECTLY_DENIED",
                "contradiction_detected": False,
                "contradiction_strength": "NONE",
                "route_decision": "denied"
            },
            "ground_truth_rationale": "Cosmetic surgery is explicitly excluded in Section 8 of the policy. The denial is legally and contractually accurate."
        }
        cases.append(c)
    return cases

def generate_formulary_cases(count=30):
    cases = []
    for i in range(1, count + 1):
        c = {
            "id": f"FORM-{i:03d}",
            "category": "formulary_exception",
            "title": f"Non-Formulary Diabetes Medication Denied - Scenario {i}",
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
            "claim_overrides": {
                "is_emergency": False,
                "is_denied": True,
                "denial_reason": "NOT_COVERED",
                "denial_carc_code": "CO-96"
            },
            "expected": {
                "appeal_recommendation": "EXCEPTION_REQUEST",
                "contradiction_detected": False,
                "contradiction_strength": "NONE",
                "route_decision": "denied"
            },
            "ground_truth_rationale": "Medication is not on the formulary. A standard appeal will fail; an exception request is legally required."
        }
        cases.append(c)
    return cases

def generate_annual_limit_cases(count=30):
    cases = []
    for i in range(1, count + 1):
        c = {
            "id": f"LMIT-{i:03d}",
            "category": "annual_limit",
            "title": f"Physical Therapy Visits Exceeded Annual Cap - Scenario {i}",
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
            "claim_overrides": {
                "is_emergency": False,
                "is_denied": True,
                "denial_reason": "NOT_COVERED",
                "denial_carc_code": "CO-119"
            },
            "expected": {
                "appeal_recommendation": "CLAIM_CORRECTLY_DENIED",
                "contradiction_detected": False,
                "contradiction_strength": "NONE",
                "route_decision": "denied"
            },
            "ground_truth_rationale": "Patient exceeded the hard 20-visit limit stated in Section 5 of the policy."
        }
        cases.append(c)
    return cases

def generate_infertility_cases(count=30):
    cases = []
    for i in range(1, count + 1):
        c = {
            "id": f"INFR-{i:03d}",
            "category": "hard_exclusion",
            "title": f"IVF Treatment Denied Under Hard Exclusion - Scenario {i}",
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
            "claim_overrides": {
                "is_emergency": False,
                "is_denied": True,
                "denial_reason": "NOT_COVERED",
                "denial_carc_code": "CO-96"
            },
            "expected": {
                "appeal_recommendation": "UNLIKELY_TO_WIN",
                "contradiction_detected": False,
                "contradiction_strength": "NONE",
                "route_decision": "denied"
            },
            "ground_truth_rationale": "IVF is a hard exclusion under self-funded ERISA plan rules. Appealing is unlikely to succeed; honest assessment required."
        }
        cases.append(c)
    return cases

def generate_nsa_balance_billing_cases(count=25):
    cases = []
    for i in range(1, count + 1):
        c = {
            "id": f"NSA-{i:03d}",
            "category": "nsa_balance_billing",
            "title": f"NSA Violation: OON Anesthesia Balance Billing at INN Hospital - Scenario {i}",
            "claim_description": (
                "I had a laparoscopic cholecystectomy at St. Jude Medical Center, which is "
                "in my insurance network. The surgeon was also in-network. However, the "
                "anesthesiologist (Apex Anesthesia Group) was out-of-network. I never "
                "chose them — they were assigned in the operating room. My EOB "
                "shows Apex Anesthesia billed $2,800 for CPT 00790 (Anesthesia for "
                "intraperitoneal procedures). The plan paid $0 and I am being told I owe "
                "the full $2,800 (Denial Reason: PR-242, Services not provided by "
                "network/primary care providers). The EOB lists total patient "
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
            "benchmark_policy_excerpt": (
                "SECTION 8: FEDERAL NO SURPRISES ACT PROTECTIONS\n"
                "Under the Federal No Surprises Act, if you receive emergency services "
                "or are treated by an out-of-network ancillary provider (such as an "
                "anesthesiologist, pathologist, or radiologist) at an In-Network facility, "
                "you cannot be balance billed. Your patient responsibility will be "
                "calculated based on the In-Network cost-sharing amounts."
            ),
            "allowed_amount": 2000,
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
                "appeal_recommendation": "STRONG_APPEAL",
                "contradiction_detected": True,
                "contradiction_strength": "STRONG",
                "route_decision": "denied",
                "legal_patient_responsibility_for_line_2": 400.0,
                "nsa_violation_detected": True,
                "illegal_balance_billed_amount": 2000.0,
            },
            "ground_truth_rationale": (
                "Apex Anesthesia Group is an OON ancillary provider at an INN facility. "
                "Under 45 CFR § 149.410(b) of the No Surprises Act, balance billing is prohibited. "
                "Patient responsibility is capped at 20% of allowed amount ($400)."
            ),
        }
        cases.append(c)
    return cases

def generate_upcoding_billing_error_cases(count=25):
    cases = []
    for i in range(1, count + 1):
        c = {
            "id": f"UPCD-{i:03d}",
            "category": "upcoding_billing_error",
            "title": f"Upcoding and Unbundling Billing Fraud - Scenario {i}",
            "claim_description": (
                "I visited the hospital emergency room for a mild wrist sprain after slipping on steps. "
                "A doctor looked at it for 5 minutes, wrapped it in an elastic bandage without any X-rays or diagnostic lab work, and discharged me. "
                "My hospital billed $5,400 for CPT 99285 (Level 5 Emergency Department Trauma Visit) plus an extra $350 itemized charge for the routine bandage supply. "
                "My insurer adjusted and denied payment citing NCCI Unbundling edit CO-97 and improper Level 5 coding."
            ),
            "policy_profile": {
                "plan_name": "Standard PPO",
                "carrier_name": "BenchmarkHealth",
                "plan_type": "PPO",
                "legal_classification": "FULLY_INSURED",
                "state": "CA",
                "in_network_deductible_individual": 1000,
                "in_network_oop_max_individual": 5000,
                "in_network_coinsurance": 0.20,
                "out_of_network_deductible_individual": 2000,
                "out_of_network_oop_max_individual": 10000,
                "out_of_network_coinsurance": 0.40
            },
            "benchmark_policy_excerpt": (
                "Section 14 — Billing Standards & NCCI Bundling: Routine medical supplies (including dressings and elastic bandages) "
                "are incidental to evaluation and management services and cannot be billed separately under NCCI guidelines. "
                "Furthermore, facility charges must accurately reflect clinical acuity; Level 5 emergency codes (99285) are excluded for minor encounters lacking intensive diagnostic interventions."
            ),
            "allowed_amount": 450,
            "claim_overrides": {
                "is_emergency": False,
                "is_denied": True,
                "denial_reason": "UNBUNDLING",
                "denial_carc_code": "CO-97",
                "cpt_code": "99285",
                "cpt_description": "Emergency department visit level 5"
            },
            "expected": {
                "appeal_recommendation": "CLAIM_CORRECTLY_DENIED",
                "contradiction_detected": False,
                "contradiction_strength": "NONE",
                "route_decision": "denied"
            },
            "ground_truth_rationale": (
                "Hospital attempted illegal upcoding (Level 5 trauma code 99285 for minor sprain) and unbundling of routine medical supplies. "
                "The insurer's denial under CARC CO-97 is legally and contractually accurate; the patient must demand a corrected claim from the provider billing department."
            ),
        }
        cases.append(c)
    return cases

def generate_all_cases():
    ensure_clean_dir()
    all_cases = []
    
    all_cases.extend(generate_emergency_cases(30))
    all_cases.extend(generate_cosmetic_cases(30))
    all_cases.extend(generate_formulary_cases(30))
    all_cases.extend(generate_annual_limit_cases(30))
    all_cases.extend(generate_infertility_cases(30))
    all_cases.extend(generate_nsa_balance_billing_cases(25))
    all_cases.extend(generate_upcoding_billing_error_cases(25))
    
    for c in all_cases:
        filepath = os.path.join(CASES_DIR, f"{c['id']}.json")
        with open(filepath, "w") as f:
            json.dump(c, f, indent=2)

    print(f"Generated {len(all_cases)} synthetic benchmark cases in {CASES_DIR}/")
    print(f"  - Emergency Care (Prior Auth Waiver): 30 cases")
    print(f"  - Explicit Exclusions (Cosmetic):     30 cases")
    print(f"  - Formulary Exceptions:               30 cases")
    print(f"  - Annual Limit Exceeded:              30 cases")
    print(f"  - Infertility Hard Exclusion:         30 cases")
    print(f"  - NSA Balance Billing:                25 cases")
    print(f"  - Upcoding & Billing Fraud [NEW]:     25 cases")

if __name__ == "__main__":
    generate_all_cases()
