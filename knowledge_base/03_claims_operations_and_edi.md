---
concept_id: federal_idr_process
domain: Regulatory
jurisdiction: Federal
audience: Provider, Consumer
tags: [IDR, independent_dispute_resolution, baseball_arbitration, NSA, payment_dispute]
---

### Federal Independent Dispute Resolution (IDR): The Arbitration Process Under the No Surprises Act

**Semantic Summary:**
The Federal Independent Dispute Resolution (IDR) process is a mandatory arbitration mechanism established under the No Surprises Act (NSA) that resolves payment disputes between out-of-network providers and health plans for NSA-protected services (emergency care, air ambulance, and non-emergency services at in-network facilities) when the parties fail to reach agreement during the initial open negotiation period. The IDR process uses "baseball-style" arbitration, where a certified IDR entity selects one of the two parties' final offers as the binding payment amount.

**Detailed Mechanics:**
*   Step 1 — Initial Payment or Denial: The payer issues an initial payment or denial to the out-of-network provider along with the QPA data and applicable CARC/RARC codes within 30 calendar days of the claim submission.
*   Step 2 — Open Negotiation Period: Either party submits a notice via the Federal IDR portal (https://www.nsa-idr.cms.gov), commencing a mandatory 30-business-day open negotiation period. By the 15th business day, the responding party must furnish a standardized open negotiation response notice.
*   Step 3 — IDR Initiation: If negotiations fail to produce agreement, the initiating party has exactly 4 business days after the close of the negotiation period to formally initiate the IDR process.
*   Step 4 — Arbitrator Selection and Eligibility: The parties mutually select a certified IDR entity from a CMS-approved list within 3 business days. The selected IDR entity must confirm the dispute's eligibility for arbitration within 5 business days.
*   Step 5 — Offer Submission: Both parties have 10 business days to submit their final "best and final" offers along with supporting documentation and pay the non-refundable administrative fee ($15 per party per dispute as of the 2026 CMS final rule, reduced from $115).
*   Step 6 — Binding Determination: The IDR entity selects one of the two offers in its entirety (no compromise or split-the-difference) within 30 business days. The losing party pays the IDR entity's fee (in addition to the administrative fee already paid).
*   Batching Logic: To optimize efficiency and minimize administrative fees, up to 50 qualified line items may be grouped ("batched") into a single IDR dispute, provided they involve the same provider or facility, the same health plan, the same or similar service codes, and services rendered within the same 30-business-day window.

**Critical Exclusions & Edge Cases:**
*   The IDR entity is statutorily prohibited from considering: the provider's billed charges (chargemaster rate), Medicare reimbursement rates, Medicaid reimbursement rates, or TRICARE rates.
*   The IDR entity must consider: the QPA, the provider's level of training and experience, the patient's acuity, the complexity of the service, teaching status of the facility, case mix, good-faith contracting efforts, and prior contract history.
*   The IDR process does NOT apply to Medicare, Medicaid, TRICARE, or VA beneficiaries.
*   Ground ambulance services are excluded from the NSA's IDR process.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** A payment dispute for an NSA-protected service where the open negotiation period has concluded without agreement. The QPA must have been calculated and communicated by the payer.
*   **Downstream Impacts:** The IDR entity's determination is binding. The losing party pays the arbitration fee. The outcome does not set precedent for future disputes but may influence future contract negotiations between the parties. Introduces RARC N872 (final payment based on QPA) on the EDI 835.

---
concept_id: hipaa_edi_transactions
domain: Regulatory
jurisdiction: Federal
audience: Provider, Underwriter
tags: [HIPAA, EDI, X12, electronic_data_interchange, revenue_cycle_management]
---

### HIPAA EDI Transactions: The Electronic Data Interchange Standards for Healthcare Claims

**Semantic Summary:**
The Health Insurance Portability and Accountability Act (HIPAA) mandates that all covered entities (health plans, healthcare clearinghouses, and healthcare providers who conduct electronic transactions) use standardized ASC X12 Electronic Data Interchange (EDI) transaction sets for the electronic transmission of healthcare administrative data, including eligibility verification, prior authorization, claim submission, claim status inquiries, remittance advice, and enrollment. These EDI standards form the operational backbone of the U.S. healthcare Revenue Cycle Management (RCM) pipeline.

**Detailed Mechanics:**
*   EDI 270 / 271 — Eligibility Inquiry and Response: The provider transmits an EDI 270 to verify patient coverage status, active eligibility, deductible amounts, copay/coinsurance levels, and out-of-pocket accumulations. The payer responds with an EDI 271 confirming or denying eligibility.
*   EDI 278 — Prior Authorization Request and Response: The provider submits an EDI 278 to request pre-service medical necessity review. The payer responds with approval, denial, or a request for additional clinical information.
*   EDI 837 — Healthcare Claim Submission: The provider transmits the claim electronically. Variants include EDI 837P (Professional, equivalent to the CMS-1500 paper form), EDI 837I (Institutional, equivalent to the UB-04 paper form), and EDI 837D (Dental).
*   EDI 276 / 277 — Claim Status Request and Response: The provider queries the payer for real-time adjudication status. The EDI 277CA (Claim Acknowledgement) summarizes front-end scrubbing edits.
*   EDI 835 — Electronic Remittance Advice (ERA): The payer transmits payment details, adjustments, and denial information to the provider for automated revenue posting. Contains CARC and RARC codes within the Claim Adjustment Segment (CAS).
*   EDI 834 — Benefit Enrollment and Maintenance: Employers transmit enrollment data (new hires, terminations, demographic changes) to the health plan to synchronize eligibility with payroll systems.
*   EDI 820 — Premium Payment: Employers transmit premium payment orders and remittance details to the health plan.

**Critical Exclusions & Edge Cases:**
*   Non-HIPAA-covered entities (e.g., workers' compensation insurers in some states, some auto insurers) may not be required to use standard EDI transaction sets.
*   Claims that fail initial EDI syntax validation (e.g., invalid NPI, missing subscriber ID, truncated diagnosis codes) are "rejected" at the clearinghouse level and never enter the payer's adjudication system. Rejections are distinct from denials.
*   HIPAA mandates the use of specific code sets within EDI transactions: ICD-10-CM for diagnoses, CPT/HCPCS for procedures, and NDC (National Drug Code) for pharmacy claims.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** The provider must be a HIPAA-covered entity with an active National Provider Identifier (NPI). The provider must have a trading partner agreement with the payer or route transactions through a HIPAA-compliant clearinghouse.
*   **Downstream Impacts:** EDI 270/271 results determine eligibility and cost-sharing parameters. EDI 278 outcomes determine prior authorization status. EDI 837 submission triggers the claim adjudication workflow. EDI 835 output triggers revenue posting, denial management, and patient billing.

---
concept_id: carc_rarc_denial_codes
domain: Health
jurisdiction: US-General
audience: Provider
tags: [CARC, RARC, denial_codes, claim_adjustment, remittance_advice]
---

### CARC and RARC Codes: The Standardized Language of Claim Adjustments and Denials

**Semantic Summary:**
Claim Adjustment Reason Codes (CARC) and Remittance Advice Remark Codes (RARC) are standardized alphanumeric codes embedded within the Claim Adjustment Segment (CAS) of the EDI 835 Electronic Remittance Advice (ERA) transaction that communicate the precise reason a health plan reduced, adjusted, or denied payment on a specific claim line item. CARC codes are maintained by the ASC X12 Standards Committee, and RARC codes are maintained by CMS. Together, they form the machine-readable language that drives automated denial management workflows.

**Detailed Mechanics:**
*   CARC Group Codes define the financial category of the adjustment:
    *   CO (Contractual Obligation): The adjustment is a contractual write-off between the provider and the payer. The provider is bound by contract and CANNOT balance bill the patient for the CO adjustment amount.
    *   PR (Patient Responsibility): The adjustment amount is the patient's financial obligation, representing deductibles, copayments, or coinsurance. The provider MAY bill the patient for PR amounts.
    *   OA (Other Adjustment): Adjustments not tied to the contract or patient responsibility, such as coordination of benefits corrections or system-level adjustments.
    *   PI (Payer Initiated Reduction): Reductions initiated by the payer based on medical necessity edits, utilization review, or payer-specific coding policies.
    *   CR (Correction and Reversal): Corrects a prior adjudication error. The original payment entry must be reversed and the updated data reposted.
*   High-frequency CARC/RARC denial combinations and their resolution workflows:
    *   CO-18 / N522: Exact duplicate claim. Verify the prior claim was processed via EDI 276 status inquiry before resubmitting.
    *   CO-22 / MA92: Coordination of benefits failure. Another payer is primary. Query the patient's eligibility matrix and resubmit with the primary insurer's 9-digit payer ID.
    *   CO-29 / N211: Timely filing limit expired. Medicare claims must be filed within 12 months (1 calendar year) from the date of service.
    *   CO-45: Charge exceeds the payer's fee schedule or maximum allowable amount. The provider must write off the difference.
    *   CO-50 / N115: Non-covered service. Medical necessity not established. Cross-reference Local Coverage Determinations (LCDs) or National Coverage Determinations (NCDs) and verify ICD-10 justification.
    *   CO-97 / M80: Benefit included in another procedure (unbundling detected). Assess whether a modifier (e.g., Modifier -25 for significant, separately identifiable E/M service) is applicable.
    *   PR-243 / CO-197: Services not authorized. If PR code, patient can be billed. If CO code, the provider absorbs the loss. Initiate retro-authorization workflow if allowable by contract.

**Critical Exclusions & Edge Cases:**
*   CARC/RARC codes are NOT patient-facing. Patients receive an Explanation of Benefits (EOB) with plain-language descriptions of adjustments. The CARC/RARC codes appear only on the provider-facing EDI 835 ERA.
*   A single claim line item can have multiple CARC/RARC pairs applied simultaneously.
*   RARC codes are subdivided into "Alerts" (informational, no action required) and "Supplemental" (provides additional detail to support the CARC).

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** An EDI 837 claim must have been submitted and adjudicated. The payer issues an EDI 835 ERA containing the CAS segments with CARC/RARC codes.
*   **Downstream Impacts:** CARC group codes determine financial posting logic (write-off to contractual adjustment, transfer to patient balance, or route to denial management/appeals). Specific CARC/RARC pairs trigger automated resolution workflows: resubmission, COB correction, medical necessity appeal, or coding correction.

---
concept_id: medical_coding_icd10_cpt_hcpcs
domain: Health
jurisdiction: Federal
audience: Provider
tags: [ICD_10_CM, CPT, HCPCS, medical_coding, diagnosis_procedure_codes]
---

### Medical Coding Systems: ICD-10-CM, CPT, and HCPCS Level II

**Semantic Summary:**
U.S. healthcare claims are constructed using three primary coding taxonomies mandated by HIPAA for electronic transactions: ICD-10-CM (International Classification of Diseases, 10th Revision, Clinical Modification) for diagnosis codes that establish medical necessity, CPT (Current Procedural Terminology) for physician services and procedures, and HCPCS (Healthcare Common Procedure Coding System) Level II for ambulance services, durable medical equipment (DME), prosthetics, orthotics, and specialized pharmacology. These codes are the foundation of every EDI 837 claim submission.

**Detailed Mechanics:**
*   ICD-10-CM codes are alphanumeric codes (up to 7 characters) that describe the patient's diagnosis, symptom, condition, or reason for the encounter. The primary diagnosis code establishes "medical necessity" — the clinical justification for the services rendered. Payers use ICD-10 codes to validate whether the billed procedure is appropriate for the documented condition.
*   CPT codes are five-digit numeric codes maintained by the American Medical Association (AMA) that describe physician services, procedures, and office visits. CPT codes are organized into three categories: Category I (standard procedures), Category II (performance measurement), and Category III (emerging technology). Evaluation and Management (E/M) codes (99201–99499) describe office visits by complexity level (Levels 1–5).
*   HCPCS Level II codes are alphanumeric codes (one letter followed by four digits, e.g., E0601) maintained by CMS that describe services not covered by CPT, including ambulance services (A0000–A0999), DME (E0100–E9999), and injectable drugs administered in physician offices (J0000–J9999).
*   The CMS-1500 claim form (EDI 837P) is used for professional (physician) billing and carries CPT/HCPCS codes. The UB-04 claim form (EDI 837I) is used for institutional (hospital/facility) billing and carries both ICD-10-PCS (Procedure Coding System) and revenue codes.

**Critical Exclusions & Edge Cases:**
*   "Upcoding" — the practice of assigning a higher-level CPT code than the clinical documentation supports (e.g., billing a Level 5 E/M visit for a routine checkup) — is a form of fraud that triggers False Claims Act (FCA) liability.
*   "Unbundling" — billing component parts of a comprehensive procedure separately to maximize reimbursement — is detected by the National Correct Coding Initiative (NCCI) edits maintained by CMS.
*   If the ICD-10 diagnosis code does not support the medical necessity of the billed CPT/HCPCS procedure, the claim will be denied with CARC CO-50 (non-covered service) or referred for clinical review.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** Clinical documentation by the treating physician or provider.
*   **Downstream Impacts:** ICD-10/CPT/HCPCS code combinations drive the claim adjudication engine's medical necessity determination, NCCI unbundling edits, Local Coverage Determination (LCD) and National Coverage Determination (NCD) lookups, and ultimately the CARC/RARC outcome on the EDI 835 ERA.

---
concept_id: claim_adjudication_workflow
domain: Health
jurisdiction: US-General
audience: Provider, Underwriter
tags: [adjudication, claim_processing, scrubbing, medical_necessity, payment_determination]
---

### Claim Adjudication Workflow: The Five-Stage Engine for Processing Healthcare Claims

**Semantic Summary:**
Healthcare claim adjudication is the deterministic, rules-based process by which a health insurance payer evaluates an incoming EDI 837 claim submission and determines the payment amount, patient responsibility, and any denials or adjustments. The standard payer adjudication engine processes claims through five sequential stages: Initial Processing and Scrubbing, Automated Review (Mass Adjudication), Manual/Clinical Review, Payment Determination, and Payment Delivery.

**Detailed Mechanics:**
*   Stage 1 — Initial Processing and Scrubbing: The claim enters the payer's gateway or clearinghouse for syntax validation. The system checks for invalid National Provider Identifiers (NPIs), missing patient subscriber IDs, truncated or invalid diagnosis codes, and EDI formatting errors. Claims failing this stage are "rejected" (bounced back to the provider) before entering the adjudication system. Rejections are NOT denials and do not trigger appeal rights.
*   Stage 2 — Automated Review (Mass Adjudication): The system verifies active eligibility on the exact date of service, checks for timely filing compliance (90–365 days depending on payer contract), cross-references procedure codes against active prior authorization numbers, checks for duplicate claims (CARC CO-18), and executes National Correct Coding Initiative (NCCI) edits to detect unbundling violations.
*   Stage 3 — Manual/Clinical Review: Claims flagged during automated review (e.g., high-dollar surgeries, unlisted procedure codes, suspected medical necessity issues) are routed to a medical director or registered nurse for clinical evaluation against proprietary criteria such as Milliman Care Guidelines (MCG) or InterQual.
*   Stage 4 — Payment Determination: The engine calculates the allowable amount based on the provider's contracted fee schedule, applies patient responsibility logic (deductible status, copay, coinsurance), subtracts any prior payments, and determines the final payout.
*   Stage 5 — Payment Delivery: The payer generates an EDI 835 (ERA) to the provider and an Explanation of Benefits (EOB) to the patient, finalizing the transaction loop.

**Critical Exclusions & Edge Cases:**
*   "Clean claims" (claims passing all automated edits with no flags) may be auto-adjudicated in seconds. State prompt-pay laws require payers to adjudicate clean claims within specific timeframes (e.g., 30 days for electronic claims in Texas, 15 days in New York after determination that payment is due).
*   Claims denied at Stage 3 for medical necessity are subject to ERISA appeal timelines (for employer-sponsored plans) or state external review processes (for fully-insured plans).
*   Payers utilizing AI-based adjudication tools (e.g., UnitedHealthcare's nH Predict, Cigna's PXDX) may process claims through automated denial algorithms that bypass individualized clinical review, a practice facing increasing regulatory and legal scrutiny.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** An EDI 837 claim must be submitted by the provider to the payer or clearinghouse.
*   **Downstream Impacts:** Stage 5 output (EDI 835 ERA) triggers revenue posting, CARC/RARC-based denial routing, patient billing (EOB), and initiates the ERISA or state-level appeal timeline if the claim is denied.

---
concept_id: network_models_hmo_ppo_epo_pos
domain: Health
jurisdiction: US-General
audience: Consumer, Broker
tags: [HMO, PPO, EPO, POS, provider_network, managed_care]
---

### Health Insurance Network Models: HMO, PPO, EPO, and POS Plan Types

**Semantic Summary:**
U.S. health insurance plans are structured around four primary managed care network models — Health Maintenance Organization (HMO), Preferred Provider Organization (PPO), Exclusive Provider Organization (EPO), and Point of Service (POS) — that define how policyholders access healthcare providers, whether a Primary Care Physician (PCP) referral is required to see specialists, and whether any coverage exists for services rendered by out-of-network providers. The network model directly determines the patient's financial exposure for out-of-network care.

**Detailed Mechanics:**
*   HMO (Health Maintenance Organization): Requires the policyholder to select a Primary Care Physician (PCP) who acts as a "gatekeeper." The PCP must provide a referral before the policyholder can access any specialist. Out-of-network care is strictly NOT covered except in documented medical emergencies. HMOs typically have the lowest premiums and cost-sharing but the most restrictive provider access.
*   PPO (Preferred Provider Organization): Does NOT require a PCP or referrals for specialist access. Policyholders may see any in-network or out-of-network provider. In-network services have lower cost-sharing; out-of-network services are covered but at significantly higher cost-sharing (higher deductible, higher coinsurance, separate out-of-pocket maximum). PPOs typically have higher premiums but offer the greatest provider flexibility.
*   EPO (Exclusive Provider Organization): Functions like a PPO in that no PCP referral is required for specialist access, but functions like an HMO in that out-of-network care is completely excluded from coverage (except in emergencies). EPOs offer moderate premiums with the trade-off of a restricted network.
*   POS (Point of Service): A hybrid model requiring the policyholder to select a PCP and obtain referrals for in-network specialist visits (like an HMO), but allowing out-of-network provider access at a higher cost-sharing level (like a PPO). POS plans are less common than HMO, PPO, or EPO plans.

**Critical Exclusions & Edge Cases:**
*   Under the No Surprises Act (NSA), all network model types must limit patient cost-sharing to in-network rates for emergency services, air ambulance services from out-of-network providers, and non-emergency services from out-of-network providers at in-network facilities.
*   In rural areas, network adequacy requirements may force insurers to provide out-of-network coverage exceptions or "single case agreements" when no in-network provider is available within the required time and distance standards.
*   Kaiser Permanente operates a unique Integrated Delivery Network (IDN) model where the insurer and the provider system are the same entity, resulting in an exceptionally low denial rate (approximately 6%) compared to non-integrated payers.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** Enrollment in a health insurance plan.
*   **Downstream Impacts:** The network model determines whether out-of-network claims are eligible for coverage, whether PCP referrals are required for specialist visits, and the applicable cost-sharing structure (in-network vs. out-of-network deductibles, coinsurance, and MOOP).
