"""
CPT/ICD-10 Lookup Tool — normalizes medical terminology to
standardized billing codes.

Maps colloquial patient descriptions (e.g., "knee replacement")
to CPT procedure codes and ICD-10-CM diagnosis codes.

Note: In production, this would query a live medical coding database
(e.g., CMS HCPCS, AMA CPT). For now, we use a curated lookup table
covering the most common procedures, supplemented by LLM inference
for less common terms.
"""

from langchain_core.tools import tool


# ── Common CPT Code Lookup Table ──────────────────────────────────
# Format: keyword → (CPT code, description, typical billed amount range)
_CPT_LOOKUP: dict[str, dict] = {
    # Evaluation & Management
    "office visit": {"cpt": "99213", "desc": "Office Visit, Established Patient, Low Complexity", "range": "$100-$250"},
    "new patient visit": {"cpt": "99203", "desc": "Office Visit, New Patient, Low Complexity", "range": "$150-$350"},
    "annual physical": {"cpt": "99395", "desc": "Preventive Visit, Established, 18-39 years", "range": "$200-$400"},
    "wellness visit": {"cpt": "99395", "desc": "Preventive Visit, Established, 18-39 years", "range": "$200-$400"},

    # Emergency
    "emergency room": {"cpt": "99285", "desc": "Emergency Department Visit, High Severity", "range": "$500-$3,000"},
    "er visit": {"cpt": "99285", "desc": "Emergency Department Visit, High Severity", "range": "$500-$3,000"},
    "emergency visit": {"cpt": "99284", "desc": "Emergency Department Visit, Moderate Severity", "range": "$400-$2,000"},

    # Orthopedic
    "knee replacement": {"cpt": "27447", "desc": "Total Knee Arthroplasty", "range": "$30,000-$70,000"},
    "total knee replacement": {"cpt": "27447", "desc": "Total Knee Arthroplasty", "range": "$30,000-$70,000"},
    "hip replacement": {"cpt": "27130", "desc": "Total Hip Arthroplasty", "range": "$30,000-$65,000"},
    "total hip replacement": {"cpt": "27130", "desc": "Total Hip Arthroplasty", "range": "$30,000-$65,000"},
    "rotator cuff repair": {"cpt": "29827", "desc": "Arthroscopic Rotator Cuff Repair", "range": "$10,000-$25,000"},
    "acl surgery": {"cpt": "29888", "desc": "ACL Reconstruction, Arthroscopic", "range": "$15,000-$35,000"},

    # Cardiac
    "heart bypass": {"cpt": "33533", "desc": "Coronary Artery Bypass Graft (CABG), Single", "range": "$70,000-$200,000"},
    "cabg": {"cpt": "33533", "desc": "Coronary Artery Bypass Graft (CABG), Single", "range": "$70,000-$200,000"},
    "cardiac catheterization": {"cpt": "93458", "desc": "Left Heart Catheterization", "range": "$5,000-$20,000"},
    "stent": {"cpt": "92928", "desc": "Percutaneous Coronary Stent Placement", "range": "$15,000-$50,000"},

    # Imaging
    "mri": {"cpt": "70553", "desc": "MRI Brain Without/With Contrast", "range": "$1,000-$5,000"},
    "mri brain": {"cpt": "70553", "desc": "MRI Brain Without/With Contrast", "range": "$1,000-$5,000"},
    "mri knee": {"cpt": "73721", "desc": "MRI Lower Extremity Without Contrast", "range": "$800-$3,500"},
    "ct scan": {"cpt": "74177", "desc": "CT Abdomen/Pelvis With Contrast", "range": "$500-$3,000"},
    "ct scan chest": {"cpt": "71260", "desc": "CT Chest With Contrast", "range": "$500-$3,000"},
    "x-ray": {"cpt": "71046", "desc": "Chest X-Ray, 2 Views", "range": "$100-$400"},
    "mammogram": {"cpt": "77067", "desc": "Screening Mammography, Bilateral", "range": "$150-$500"},
    "ultrasound": {"cpt": "76856", "desc": "Ultrasound, Pelvic, Complete", "range": "$200-$800"},
    "pet scan": {"cpt": "78816", "desc": "PET Scan, Whole Body", "range": "$3,000-$10,000"},

    # General Surgery
    "appendectomy": {"cpt": "44970", "desc": "Laparoscopic Appendectomy", "range": "$10,000-$35,000"},
    "cholecystectomy": {"cpt": "47562", "desc": "Laparoscopic Cholecystectomy (Gallbladder Removal)", "range": "$10,000-$30,000"},
    "gallbladder removal": {"cpt": "47562", "desc": "Laparoscopic Cholecystectomy", "range": "$10,000-$30,000"},
    "hernia repair": {"cpt": "49650", "desc": "Laparoscopic Inguinal Hernia Repair", "range": "$5,000-$15,000"},
    "colonoscopy": {"cpt": "45378", "desc": "Diagnostic Colonoscopy", "range": "$1,500-$5,000"},
    "endoscopy": {"cpt": "43239", "desc": "Upper GI Endoscopy with Biopsy", "range": "$1,000-$4,000"},
    "c-section": {"cpt": "59510", "desc": "Cesarean Delivery", "range": "$15,000-$40,000"},
    "cesarean section": {"cpt": "59510", "desc": "Cesarean Delivery", "range": "$15,000-$40,000"},
    "vaginal delivery": {"cpt": "59400", "desc": "Routine Obstetric Care, Vaginal Delivery", "range": "$10,000-$30,000"},

    # Mental Health
    "therapy session": {"cpt": "90837", "desc": "Psychotherapy, 60 Minutes", "range": "$100-$300"},
    "psychiatry visit": {"cpt": "99214", "desc": "Psychiatric Evaluation", "range": "$150-$400"},

    # Lab
    "blood work": {"cpt": "80053", "desc": "Comprehensive Metabolic Panel", "range": "$30-$300"},
    "blood test": {"cpt": "80053", "desc": "Comprehensive Metabolic Panel", "range": "$30-$300"},
    "cbc": {"cpt": "85025", "desc": "Complete Blood Count (CBC) with Differential", "range": "$20-$100"},
}


# ── Common ICD-10 Code Lookup Table ───────────────────────────────
_ICD10_LOOKUP: dict[str, dict] = {
    "knee pain": {"icd10": "M25.561", "desc": "Pain in right knee"},
    "osteoarthritis knee": {"icd10": "M17.11", "desc": "Primary osteoarthritis, right knee"},
    "back pain": {"icd10": "M54.5", "desc": "Low back pain"},
    "chest pain": {"icd10": "R07.9", "desc": "Chest pain, unspecified"},
    "heart attack": {"icd10": "I21.0", "desc": "Acute ST elevation myocardial infarction"},
    "diabetes": {"icd10": "E11.9", "desc": "Type 2 diabetes mellitus without complications"},
    "hypertension": {"icd10": "I10", "desc": "Essential (primary) hypertension"},
    "high blood pressure": {"icd10": "I10", "desc": "Essential (primary) hypertension"},
    "depression": {"icd10": "F33.0", "desc": "Major depressive disorder, recurrent, mild"},
    "anxiety": {"icd10": "F41.1", "desc": "Generalized anxiety disorder"},
    "pneumonia": {"icd10": "J18.9", "desc": "Pneumonia, unspecified organism"},
    "broken arm": {"icd10": "S52.501A", "desc": "Fracture of lower end of radius, right arm"},
    "broken leg": {"icd10": "S82.001A", "desc": "Fracture of patella, right knee"},
    "pregnancy": {"icd10": "Z34.00", "desc": "Encounter for supervision of normal first pregnancy"},
    "cancer": {"icd10": "C80.1", "desc": "Malignant (primary) neoplasm, unspecified"},
    "breast cancer": {"icd10": "C50.919", "desc": "Malignant neoplasm of unspecified site of breast"},
    "appendicitis": {"icd10": "K35.80", "desc": "Unspecified acute appendicitis"},
    "gallstones": {"icd10": "K80.20", "desc": "Calculus of gallbladder without obstruction"},
    "upper respiratory infection": {"icd10": "J06.9", "desc": "Acute upper respiratory infection, unspecified"},
    "cold": {"icd10": "J06.9", "desc": "Acute upper respiratory infection, unspecified"},
    "flu": {"icd10": "J11.1", "desc": "Influenza with other respiratory manifestations"},
    "covid": {"icd10": "U07.1", "desc": "COVID-19, virus identified"},
    "headache": {"icd10": "R51.9", "desc": "Headache, unspecified"},
    "migraine": {"icd10": "G43.909", "desc": "Migraine, unspecified, not intractable"},
}


@tool
def lookup_cpt_code(procedure_description: str) -> str:
    """Look up a CPT (Current Procedural Terminology) code for a medical procedure.

    Translates colloquial medical descriptions into standardized CPT billing codes.
    Use this when a patient describes a procedure in plain English and you need
    the formal billing code.

    Args:
        procedure_description: Plain English description of the procedure
                              (e.g., "knee replacement", "MRI", "blood work")
    """
    key = procedure_description.lower().strip()

    # Exact match
    if key in _CPT_LOOKUP:
        entry = _CPT_LOOKUP[key]
        return (
            f"CPT Code: {entry['cpt']}\n"
            f"Description: {entry['desc']}\n"
            f"Typical Billed Range: {entry['range']}\n"
            f"Note: Actual billed amount varies by provider, facility, and geographic region."
        )

    # Partial match
    matches = [
        (k, v) for k, v in _CPT_LOOKUP.items()
        if key in k or k in key
    ]
    if matches:
        results = []
        for k, v in matches[:3]:
            results.append(f"  • CPT {v['cpt']}: {v['desc']} ({v['range']})")
        return f"Possible matches for '{procedure_description}':\n" + "\n".join(results)

    return (
        f"No exact CPT code found for '{procedure_description}'. "
        f"This may require manual code lookup from the AMA CPT database or CMS HCPCS. "
        f"Ask the patient or provider for the exact CPT code from their bill or EOB."
    )


@tool
def lookup_icd10_code(condition_description: str) -> str:
    """Look up an ICD-10-CM diagnosis code for a medical condition.

    Translates colloquial condition descriptions into standardized ICD-10
    diagnosis codes used in US medical billing.

    Args:
        condition_description: Plain English description of the condition
                              (e.g., "knee pain", "heart attack", "diabetes")
    """
    key = condition_description.lower().strip()

    # Exact match
    if key in _ICD10_LOOKUP:
        entry = _ICD10_LOOKUP[key]
        return (
            f"ICD-10-CM Code: {entry['icd10']}\n"
            f"Description: {entry['desc']}\n"
            f"Note: Exact laterality and specificity should be confirmed with clinical documentation."
        )

    # Partial match
    matches = [
        (k, v) for k, v in _ICD10_LOOKUP.items()
        if key in k or k in key
    ]
    if matches:
        results = []
        for k, v in matches[:3]:
            results.append(f"  • {v['icd10']}: {v['desc']}")
        return f"Possible matches for '{condition_description}':\n" + "\n".join(results)

    return (
        f"No exact ICD-10 code found for '{condition_description}'. "
        f"This may require lookup from the WHO ICD-10-CM database. "
        f"Ask the patient or provider for the diagnosis code from their EOB or medical record."
    )
