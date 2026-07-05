---
concept_id: medicare_advantage_appeals_five_levels
domain: Regulatory
jurisdiction: Federal
audience: Consumer, Provider
tags: [Medicare_Advantage, appeals, redetermination, IRE, ALJ]
---

### Medicare Advantage Appeals: The Five-Level Federal Appeal Process

**Semantic Summary:**
Appealing a denied claim under a Medicare Advantage (MA, Part C) plan requires navigating a highly structured, five-level appeal process mandated by the Centers for Medicare & Medicaid Services (CMS) under 42 CFR Part 422. Each level escalates from internal plan review to independent federal adjudication, with progressively higher evidentiary standards and dollar-amount thresholds.

**Detailed Mechanics:**
*   Level 1 — Redetermination: Internal review by the Medicare Advantage plan itself. Standard timeline: 30 calendar days for pre-service requests, 60 calendar days for post-service payment disputes. Expedited reviews (for situations posing immediate health risk) must be completed within 72 hours.
*   Level 2 — Reconsideration by an Independent Review Entity (IRE): If the MA plan upholds the denial at Level 1, the case is automatically forwarded to an external IRE (e.g., Maximus Federal Services). The IRE conducts an independent clinical review, generally within 60 calendar days for payment disputes and 30 days for pre-service requests.
*   Level 3 — Administrative Law Judge (ALJ) Hearing: If the IRE upholds the denial and the Amount in Controversy (AIC) meets the annual CMS threshold ($180 for 2025), the appellant may request a formal hearing before an ALJ within the Office of Medicare Hearings and Appeals (OMHA). This is the first opportunity for oral testimony. The ALJ hearing must be requested within 60 calendar days of the IRE decision.
*   Level 4 — Medicare Appeals Council Review: If the ALJ decision is unfavorable, the appellant may request a paper-based review by the Medicare Appeals Council within the Departmental Appeals Board (DAB) within 60 calendar days.
*   Level 5 — Federal District Court: The final tier requires judicial review in federal court. The AIC must meet a significantly higher threshold ($1,840 for 2025). The lawsuit must be filed within 60 calendar days of the Appeals Council decision.

**Critical Exclusions & Edge Cases:**
*   The MA plan must issue an "Integrated Denial Notice" (IDN) or "Notice of Denial of Medical Coverage" that includes specific denial reasons, appeal rights, and applicable deadlines.
*   If the MA plan fails to issue a timely decision at Level 1, the case is automatically escalated to Level 2 (IRE).
*   Expedited appeals at Level 1 may be requested by the enrollee, their representative, or the treating physician when standard timeframes could seriously jeopardize the enrollee's life, health, or ability to regain maximum function.
*   The Amount in Controversy thresholds are adjusted annually by CMS.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** A claim denial or adverse coverage determination by a Medicare Advantage plan. The enrollee must be currently enrolled in the MA plan or have been enrolled at the time the service was rendered.
*   **Downstream Impacts:** Exhaustion of all five levels is required before further legal remedies are available. Level 2 (IRE) decisions are independent of the MA plan and frequently overturn Level 1 denials, particularly for algorithmic denials from plans like Humana and UnitedHealthcare.

---
concept_id: prior_authorization
domain: Health
jurisdiction: US-General
audience: Consumer, Provider
tags: [prior_authorization, precertification, utilization_management, medical_necessity, EDI_278]
---

### Prior Authorization: Pre-Service Approval Requirement for Covered Healthcare Services

**Semantic Summary:**
Prior authorization (also called precertification, preauthorization, or prior approval) is a utilization management process by which a health insurance plan requires the treating provider to obtain advance approval from the plan before rendering specific healthcare services, procedures, medications, or medical equipment, to confirm that the requested service meets the plan's criteria for medical necessity and is a covered benefit. Failure to obtain required prior authorization typically results in claim denial, with the financial liability shifting to the provider (if coded as a Contractual Obligation denial) or the patient (if coded as Patient Responsibility).

**Detailed Mechanics:**
*   Prior authorization is transmitted electronically using the HIPAA-standard EDI 278 transaction set. The provider submits clinical justification (diagnosis codes, clinical notes, test results) to the payer, which responds with approval, denial, or a request for additional information.
*   Services commonly requiring prior authorization include: elective surgeries, advanced imaging (MRI, CT, PET scans), specialty medications (especially Tier 4 and Tier 5 formulary drugs), durable medical equipment (DME), inpatient hospital admissions, post-acute care (skilled nursing facility, home health, inpatient rehabilitation), and genetic testing.
*   Authorization decisions are typically made by clinical staff (registered nurses, medical directors) using proprietary medical necessity criteria such as Milliman Care Guidelines (MCG) or InterQual.
*   If authorization is denied, the provider may request a peer-to-peer review — a telephone call between the treating physician and the payer's medical director to discuss the clinical justification. Peer-to-peer reviews frequently result in authorization approval.
*   Authorizations are time-limited and service-specific. An authorization number is assigned upon approval, which must be included on the subsequent EDI 837 claim submission.

**Critical Exclusions & Edge Cases:**
*   Emergency services do NOT require prior authorization under federal law. The No Surprises Act and EMTALA ensure that emergency treatment is provided regardless of authorization status. Plans typically allow retrospective (retro) authorization for emergency admissions within 24–72 hours of the service.
*   If a plan denies prior authorization, the denial triggers ERISA appeal timelines (for employer-sponsored plans) or state external review processes (for fully-insured plans in states with external review laws).
*   CARC PR-243 (services not authorized) indicates the patient may be billed. CARC CO-197 (precertification/authorization absent) indicates the provider absorbs the financial loss per their contract.
*   CMS has proposed rules to streamline prior authorization for Medicare Advantage and Medicaid managed care plans, including requirements for electronic prior authorization APIs and mandatory 72-hour decision timelines for urgent requests.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** The provider must verify via the EDI 270/271 eligibility response whether the requested service requires prior authorization under the patient's specific plan.
*   **Downstream Impacts:** Authorization approval generates an authorization number that must accompany the EDI 837 claim. Authorization denial triggers appeal rights. Absence of required authorization on a submitted claim triggers CARC PR-243 or CO-197 denials on the EDI 835 ERA.

---
concept_id: emtala_emergency_treatment
domain: Regulatory
jurisdiction: Federal
audience: Consumer, Provider
tags: [EMTALA, emergency_medical_treatment, stabilization, screening, hospital_obligation]
---

### EMTALA: The Federal Mandate for Emergency Medical Treatment Regardless of Ability to Pay

**Semantic Summary:**
The Emergency Medical Treatment and Labor Act (EMTALA), codified at 42 U.S.C. § 1395dd, is a federal statute that requires any hospital with a dedicated emergency department that participates in Medicare to provide a medical screening examination (MSE) to any individual who presents to the emergency department requesting care, and to provide stabilizing treatment if an emergency medical condition (EMC) is identified, regardless of the individual's ability to pay, insurance status, citizenship, or any other factor. EMTALA creates an unfunded federal mandate that overrides financial considerations in the emergency care setting.

**Detailed Mechanics:**
*   The Medical Screening Examination (MSE) must be provided to determine whether an emergency medical condition exists. The MSE must be performed by a qualified medical person (QMP) as defined by the hospital's bylaws.
*   If an emergency medical condition is identified, the hospital must provide stabilizing treatment within its capability before the patient can be discharged or transferred.
*   An "emergency medical condition" is defined as a condition manifesting acute symptoms of sufficient severity (including severe pain, psychiatric disturbances, or symptoms of substance abuse) such that the absence of immediate medical attention could reasonably result in placing the individual's health in serious jeopardy, serious impairment of bodily functions, or serious dysfunction of any body organ or part.
*   EMTALA's "anti-dumping" provision prohibits hospitals from transferring patients with unstabilized emergency conditions to another facility unless the patient requests the transfer, or a physician certifies that the medical benefits of transfer outweigh the risks AND the receiving facility has agreed to accept the transfer and has the capability to treat the condition.
*   Hospitals cannot delay the MSE or stabilizing treatment to inquire about the patient's insurance status or ability to pay.

**Critical Exclusions & Edge Cases:**
*   EMTALA applies ONLY to hospitals that have dedicated emergency departments AND participate in Medicare. Freestanding urgent care clinics, physician offices, and non-Medicare-participating facilities are NOT subject to EMTALA.
*   EMTALA does NOT mandate that hospitals provide free care. After the patient is stabilized, the hospital may bill the patient for services rendered. EMTALA only requires that care be provided regardless of payment ability; it does not waive the patient's financial obligation.
*   EMTALA violations can result in civil monetary penalties of up to $50,000 per violation for hospitals with 100+ beds ($25,000 for smaller hospitals), termination from the Medicare program, and private lawsuits by individuals who suffered personal harm due to an EMTALA violation.
*   The No Surprises Act interacts with EMTALA by limiting patient cost-sharing for emergency services to in-network rates, regardless of the provider's network status.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** An individual must present to a Medicare-participating hospital's emergency department requesting examination or treatment.
*   **Downstream Impacts:** EMTALA-mandated emergency services are exempt from prior authorization requirements. After stabilization, the claim enters the standard adjudication workflow. The No Surprises Act limits patient cost-sharing for EMTALA-triggered emergency services. Consumer defense tactics (e.g., consent addendums limiting financial liability) leverage EMTALA's treatment mandate.

---
concept_id: medical_necessity_determination
domain: Health
jurisdiction: US-General
audience: Provider, Consumer
tags: [medical_necessity, clinical_criteria, MCG, InterQual, coverage_determination]
---

### Medical Necessity: The Clinical Standard for Health Insurance Coverage Determinations

**Semantic Summary:**
Medical necessity is the foundational clinical and legal standard that health insurance plans use to determine whether a specific healthcare service, procedure, medication, or supply is eligible for coverage and reimbursement. A service is generally deemed "medically necessary" if it is clinically appropriate and effective for the diagnosis or treatment of the patient's condition, consistent with accepted standards of medical practice, not primarily for the convenience of the patient or provider, and the most cost-effective option among clinically equivalent alternatives. Medical necessity determinations are the single most common basis for clinical claim denials.

**Detailed Mechanics:**
*   Health insurance plans define medical necessity criteria in their plan documents (Summary Plan Description for ERISA plans, Certificate of Coverage for fully-insured plans). These definitions vary by plan and by payer.
*   Payers operationalize medical necessity determinations using proprietary clinical criteria sets, most commonly Milliman Care Guidelines (MCG) and InterQual (owned by Change Healthcare/Optum). These criteria provide evidence-based benchmarks for the appropriate level of care, length of stay, and clinical thresholds for specific diagnoses and procedures.
*   During prior authorization review or retrospective claim review, the payer's clinical staff (registered nurses, medical directors) compare the patient's clinical documentation against MCG or InterQual criteria to determine if the service meets the threshold for medical necessity.
*   If a service is denied for lack of medical necessity, the denial must include the specific clinical rationale and the criteria used. Under ERISA regulations, the plan must provide the claimant with the specific internal rule, guideline, or protocol relied upon in making the adverse determination, or a statement that such a rule was relied upon and that a copy will be provided free of charge upon request.
*   The ICD-10-CM diagnosis code submitted on the EDI 837 claim must clinically justify the CPT/HCPCS procedure code billed. If the diagnosis does not support the procedure, the claim is denied for lack of medical necessity (CARC CO-50 / RARC N115).

**Critical Exclusions & Edge Cases:**
*   "Medically necessary" is NOT synonymous with "medically recommended." A treating physician may recommend a service that the plan determines does not meet its specific medical necessity criteria, creating a conflict between clinical judgment and coverage policy.
*   Medicare uses Local Coverage Determinations (LCDs) and National Coverage Determinations (NCDs) to define medical necessity for specific services. LCDs are issued by Medicare Administrative Contractors (MACs) and vary by jurisdiction. NCDs are issued by CMS and apply nationally.
*   Experimental, investigational, and unproven services are typically excluded from coverage under medical necessity criteria, even if the treating physician believes they are appropriate.
*   Cosmetic procedures are generally not medically necessary unless they are reconstructive (e.g., breast reconstruction after mastectomy, which is mandated by the Women's Health and Cancer Rights Act).

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** A healthcare service has been rendered or is being requested. The ICD-10-CM diagnosis code must be submitted to establish the clinical justification.
*   **Downstream Impacts:** Medical necessity approval is a prerequisite for claim payment. Medical necessity denial triggers CARC CO-50 or PI-group adjustments and activates appeal rights under ERISA (for employer plans) or the Medicare Advantage appeals process (for MA plans). Appeal letters should cite specific MCG or InterQual criteria to counter the payer's determination.

---
concept_id: medical_loss_ratio
domain: Regulatory
jurisdiction: Federal
audience: Broker, Underwriter
tags: [MLR, medical_loss_ratio, ACA_mandate, rebates, premium_spending]
---

### Medical Loss Ratio (MLR): The ACA Mandate on Insurer Premium Spending

**Semantic Summary:**
The Medical Loss Ratio (MLR) is a federal requirement under Affordable Care Act (ACA) Section 2718 mandating that health insurance issuers spend a minimum percentage of premium revenue on direct medical care and quality improvement activities rather than administrative costs, marketing, executive compensation, and profit. Issuers in the individual and small group markets must maintain an MLR of at least 80% (the "80/20 rule"), while issuers in the large group market must maintain an MLR of at least 85% (the "85/15 rule"). Issuers failing to meet the minimum MLR must issue rebates to enrollees.

**Detailed Mechanics:**
*   MLR is calculated as: (Clinical Services Spending + Quality Improvement Activities) ÷ (Total Premium Revenue − Federal and State Taxes and Licensing Fees).
*   "Clinical services" includes payments for hospital, physician, and pharmacy claims, as well as clinical disease management and case management programs.
*   "Quality improvement activities" includes care coordination, health information technology investments, and accreditation efforts.
*   Administrative costs that do NOT count toward the MLR include: agent and broker commissions, salaries for non-clinical staff, marketing and advertising, executive compensation, and corporate overhead.
*   If an issuer's MLR falls below the required threshold, the issuer must issue rebates to enrollees by September 30 of the following year. Rebates are calculated at the state-market level (not individual policy level) and are distributed proportionally to enrollees.
*   MLR data is reported annually to CMS by each issuer and is publicly available.

**Critical Exclusions & Edge Cases:**
*   The MLR requirement applies ONLY to health insurance issuers (carriers). Self-funded ERISA plans are NOT subject to the MLR requirement because the employer (not an insurer) is the risk-bearer.
*   Mini-med plans, expatriate plans, and certain reinsurance arrangements may be exempt or have different MLR calculation methodologies.
*   Some critics argue that the MLR requirement creates a perverse incentive for insurers to allow healthcare costs to rise, because a higher total claims cost base allows the insurer to retain a larger absolute dollar amount as the permitted 15%–20% administrative/profit margin.
*   For employer-sponsored fully-insured plans, MLR rebates may be returned to the employer rather than directly to employees, depending on the plan document and applicable DOL guidance.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** The entity must be a licensed health insurance issuer selling coverage in the individual, small group, or large group market.
*   **Downstream Impacts:** MLR compliance affects insurer profitability, premium pricing strategy, and administrative cost management. MLR rebates are issued to enrollees or employers when the threshold is not met. MLR data is used by regulators and analysts to assess insurer efficiency.
