---
concept_id: state_prompt_pay_laws
domain: Regulatory
jurisdiction: State-Specific
audience: Provider
tags: [prompt_pay, clean_claim, state_regulation, timely_adjudication, fully_insured]
---

### State Prompt Pay Laws: Mandatory Claim Adjudication Timelines for Fully-Insured Plans

**Semantic Summary:**
State prompt pay laws are state-level regulations that mandate maximum timeframes within which health insurance carriers must adjudicate and pay "clean claims" (claims that pass all front-end edits and require no additional information) submitted by healthcare providers. These laws apply ONLY to fully-insured health plans regulated by the state Department of Insurance; self-funded ERISA plans are exempt from state prompt pay requirements under ERISA preemption. Penalties for violation include interest on delayed payments, administrative fines, and potential regulatory action.

**Detailed Mechanics:**
*   Prompt pay timelines vary significantly by state. Common examples: Texas requires action on electronic clean claims within 30 calendar days and paper claims within 45 days. New York requires payment within 30 days of receipt for electronic claims, with interest penalties accruing after 45 days. California mandits payment within 30 working days for non-contested claims and 45 working days for contested claims.
*   A "clean claim" is defined as a claim that is submitted with all required data elements, is not a duplicate, has valid provider and patient identifiers, and does not require additional documentation or clarification.
*   If a payer fails to pay within the prompt pay window, the provider is entitled to interest (typically 1%–1.5% per month or 12%–18% per annum) on the unpaid balance, and the provider may file a complaint with the state Department of Insurance.
*   Some states impose additional penalties beyond interest, including per-claim fines ($50–$100 per late claim) and aggregate fines for patterns of prompt pay violations.

**Critical Exclusions & Edge Cases:**
*   Self-funded ERISA plans are NOT subject to state prompt pay laws under the Deemer Clause. Providers billing self-funded plans must rely on the terms of their provider contract for payment timelines.
*   Prompt pay clocks typically do not begin running until the payer receives a "clean" claim. Claims that are rejected for missing data elements or formatting errors do not trigger the prompt pay timeline.
*   Coordination of Benefits (COB) claims where the payer is secondary may have extended prompt pay timelines in some states, as the secondary payer must first receive the primary payer's remittance data.
*   Some states exempt government-sponsored plans (Medicaid managed care) from standard prompt pay timelines and apply separate regulatory timeframes.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** The plan must be a fully-insured health plan regulated by the state. The claim must qualify as a "clean claim" under the state's definition.
*   **Downstream Impacts:** Prompt pay violations generate interest payable to the provider. Patterns of violations may trigger state Department of Insurance investigations. Providers may cite prompt pay law violations in contract renegotiations.

---
concept_id: knox_keene_california
domain: Regulatory
jurisdiction: State-Specific
audience: Consumer, Provider
tags: [Knox_Keene, California, DMHC, HMO_regulation, grievance_response]
---

### Knox-Keene Health Care Service Plan Act: California's HMO and Managed Care Regulatory Framework

**Semantic Summary:**
The Knox-Keene Health Care Service Plan Act of 1975 (California Health and Safety Code §§ 1340–1399.874) is a California state law that grants the Department of Managed Health Care (DMHC) comprehensive regulatory authority over health care service plans (HMOs and certain PPOs) operating in California. Knox-Keene mandates the provision of "basic health care services," sets strict parameters for grievance and appeal responses, requires network adequacy standards, and establishes an Independent Medical Review (IMR) process as a final administrative remedy for denied claims.

**Detailed Mechanics:**
*   Knox-Keene requires health plans to respond to standard grievances within 30 calendar days and urgent grievances within 72 hours.
*   If a health plan denies, modifies, or delays a service based on medical necessity, the enrollee may request an Independent Medical Review (IMR) through the DMHC. The IMR is conducted by independent medical professionals who review the clinical documentation and the plan's denial rationale.
*   Knox-Keene mandates that health plans provide "basic health care services" including physician services, hospital services, diagnostic laboratory services, home health services, preventive care, and emergency services.
*   The DMHC has authority to impose fines and corrective action plans on health plans that violate Knox-Keene requirements, including penalties for delayed grievance responses, network adequacy failures, and improper claim denials.
*   California's Timely Access standards under Knox-Keene require health plans to ensure appointments within specific timeframes: urgent care within 48 hours, non-urgent primary care within 10 business days, non-urgent specialist care within 15 business days.

**Critical Exclusions & Edge Cases:**
*   Knox-Keene applies to health care service plans licensed by the DMHC. Health insurance policies regulated by the California Department of Insurance (CDI) — typically indemnity PPO plans — are subject to CDI regulations rather than Knox-Keene.
*   Self-funded ERISA plans are NOT subject to Knox-Keene under ERISA's Deemer Clause.
*   The DMHC's IMR process is one of the most robust state-level external review mechanisms in the United States. IMR decisions are binding on the health plan and have historically favored patients in a significant percentage of cases.
*   Knox-Keene's grievance requirements are more stringent than federal ERISA timelines, providing California consumers with faster resolution paths — but only for fully-insured Knox-Keene-regulated plans.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** The health plan must be a California-licensed health care service plan regulated by the DMHC under Knox-Keene. The enrollee must be a California resident covered by the plan.
*   **Downstream Impacts:** Knox-Keene grievance timelines override federal ERISA timelines for fully-insured plans in California. The DMHC IMR process provides a binding external review pathway. Knox-Keene network adequacy standards affect provider contracting and access to care in California GRAs.

---
concept_id: cobra_continuation_coverage
domain: Regulatory
jurisdiction: Federal
audience: Consumer, Broker
tags: [COBRA, continuation_coverage, job_loss, qualifying_event, premium_responsibility]
---

### COBRA Continuation Coverage: Temporary Health Insurance After Employment Loss

**Semantic Summary:**
The Consolidated Omnibus Budget Reconciliation Act of 1985 (COBRA) is a federal law that provides eligible employees and their dependents the right to temporarily continue their employer-sponsored group health plan coverage after experiencing a "qualifying event" that would otherwise result in loss of coverage, such as voluntary or involuntary job loss (except for gross misconduct), reduction in work hours, divorce or legal separation, death of the covered employee, or a dependent child aging out of eligibility. COBRA coverage requires the individual to pay the full premium cost (both the employee and employer share) plus a 2% administrative fee.

**Detailed Mechanics:**
*   COBRA applies to group health plans sponsored by private-sector employers with 20 or more employees on more than 50% of its typical business days in the prior calendar year. It also applies to state and local government plans. Federal employee plans are covered by a similar but separate law (FEHBA).
*   The maximum COBRA continuation period is 18 months for qualifying events related to termination of employment or reduction of hours. The period extends to 36 months for qualifying events related to divorce, legal separation, death of the covered employee, or a dependent child's loss of dependent status.
*   COBRA premiums can be up to 102% of the total plan cost (the employer's share plus the employee's share plus a 2% administrative surcharge). For disabled individuals who qualify for an 11-month extension (29 months total), the premium may increase to 150% for months 19–29.
*   Employers must provide COBRA election notices within 14 days of receiving notice of a qualifying event. The qualified beneficiary has 60 days from the later of the qualifying event date or the notice date to elect COBRA coverage. Coverage is retroactive to the date of the qualifying event.
*   COBRA coverage terminates upon: the end of the maximum continuation period, failure to pay premiums on time (with a 30-day grace period), the employer ceasing to maintain any group health plan, the qualified beneficiary obtaining other group health coverage (without a pre-existing condition exclusion), or the qualified beneficiary becoming entitled to Medicare.

**Critical Exclusions & Edge Cases:**
*   COBRA does NOT apply to employers with fewer than 20 employees. However, many states have "mini-COBRA" laws that extend similar continuation rights to employees of small employers (e.g., California's Cal-COBRA covers employers with 2–19 employees for up to 36 months).
*   Loss of employment due to "gross misconduct" disqualifies the employee from COBRA eligibility. However, "gross misconduct" is narrowly defined and is distinct from ordinary termination for cause.
*   COBRA coverage is NOT "creditable coverage" for Medicare Part B Late Enrollment Penalty purposes. Individuals who rely solely on COBRA after turning 65 and do not enroll in Medicare Part B will face a permanent 10% penalty per year of delay.
*   A qualifying event that occurs during a COBRA continuation period (e.g., a divorce during an 18-month COBRA period) may trigger a second qualifying event, extending coverage to 36 months from the original qualifying event date.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** The individual must have been enrolled in a group health plan sponsored by an employer with 20+ employees and must have experienced a qualifying event.
*   **Downstream Impacts:** COBRA election preserves access to the employer's group plan benefits and provider network. COBRA is NOT creditable coverage for Medicare Part B penalty avoidance. Loss of COBRA coverage triggers a Special Enrollment Period (SEP) for ACA marketplace enrollment. Under Medicare Secondary Payer (MSP) rules, Medicare is generally primary when the beneficiary has COBRA coverage (not active employment-based coverage).

---
concept_id: timely_filing_limits
domain: Health
jurisdiction: US-General
audience: Provider
tags: [timely_filing, claim_deadline, submission_window, CARC_CO_29, payer_contract]
---

### Timely Filing Limits: Deadlines for Healthcare Claim Submission

**Semantic Summary:**
Timely filing limits are the maximum timeframes within which healthcare providers must submit claims (EDI 837 transactions) to the payer after the date of service in order for the claim to be eligible for adjudication and payment. If a claim is submitted after the timely filing deadline, the payer will deny the claim with CARC CO-29 (the time limit for filing has expired) and RARC N211, and the provider is contractually prohibited from billing the patient for the denied amount. Timely filing limits vary by payer, plan type, and contract terms.

**Detailed Mechanics:**
*   Medicare: Claims must be filed within 12 months (1 calendar year) from the date of service. Claims filed after the 12-month deadline are automatically denied, with very limited exceptions (e.g., retroactive Medicare entitlement, administrative error by CMS).
*   Medicaid: Timely filing limits are set by each state's Medicaid program and typically range from 90 days to 365 days from the date of service, with some states allowing up to 2 years.
*   Commercial Payers: Timely filing limits are defined in the provider's participation agreement (contract) with each payer. Common commercial deadlines range from 90 days to 365 days. Some payers (e.g., UnitedHealthcare, Aetna) use 90-day filing windows for in-network claims, while others allow up to 180 or 365 days.
*   The timely filing clock starts from the date of service (DOS) for original claims and from the date of the remittance advice (ERA) for corrected or adjusted claims.
*   If a claim is denied for timely filing, the provider generally cannot appeal the denial unless they can demonstrate that the late submission was due to circumstances beyond their control (e.g., the payer provided incorrect eligibility information, or a retroactive coverage change was made).

**Critical Exclusions & Edge Cases:**
*   When a claim is denied for timely filing (CARC CO-29), the denial is a Contractual Obligation (CO group code), meaning the provider CANNOT balance bill the patient for the denied amount. The provider absorbs the financial loss.
*   Coordination of Benefits (COB) claims submitted to a secondary payer typically have a separate timely filing window that begins from the date the primary payer's remittance advice is received, not from the date of service.
*   Some state laws mandate minimum timely filing periods for fully-insured plans (e.g., a state may require that fully-insured plans accept claims for at least 180 days). These laws do not apply to self-funded ERISA plans.
*   Workers' compensation and auto insurance claims may have different timely filing rules that are separate from health insurance timely filing limits.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** A healthcare service has been rendered and the provider must submit the EDI 837 claim within the applicable timely filing window.
*   **Downstream Impacts:** Timely filing denial (CARC CO-29) results in permanent revenue loss for the provider with no patient billing recourse. Triggers need for automated timely filing tracking in revenue cycle management systems. COB claims require tracking of secondary timely filing deadlines separately from primary filing deadlines.

---
concept_id: ncci_unbundling_edits
domain: Health
jurisdiction: Federal
audience: Provider
tags: [NCCI, unbundling, CCI_edits, modifier, bundled_services]
---

### National Correct Coding Initiative (NCCI): Federal Edits to Prevent Improper Unbundling

**Semantic Summary:**
The National Correct Coding Initiative (NCCI), maintained by the Centers for Medicare & Medicaid Services (CMS), is a set of automated coding edits applied during claim adjudication that identify and prevent the improper billing practice of "unbundling" — the practice of fragmenting a comprehensive procedure into its individual component parts and billing each component separately to maximize cumulative reimbursement. NCCI edits define pairs of CPT/HCPCS codes that should not be billed together because one code is a component of, or inherently included in, the other.

**Detailed Mechanics:**
*   NCCI Procedure-to-Procedure (PTP) Edits: Define pairs of codes where Column 1 is the comprehensive (parent) code and Column 2 is the component (included) code. When both codes are billed on the same claim for the same patient on the same date of service, the Column 2 code is denied or bundled into the Column 1 code.
*   NCCI Medically Unlikely Edits (MUE): Define the maximum number of units of a particular CPT/HCPCS code that a single provider can report for a single patient on a single date of service. Claims exceeding the MUE threshold are denied for the excess units.
*   Modifier Indicators: Some NCCI PTP edit pairs have a modifier indicator of "1," meaning the Column 2 code may be separately reported if an appropriate modifier is appended (e.g., Modifier -25 for a significant, separately identifiable evaluation and management service, Modifier -59 for a distinct procedural service, or Modifier -XE/XS/XP/XU for specific distinct service subcategories). A modifier indicator of "0" means no modifier override is permitted.
*   NCCI edits are updated quarterly by CMS and are publicly available on the CMS website.

**Critical Exclusions & Edge Cases:**
*   NCCI edits were originally developed for Medicare claims but are widely adopted by commercial payers as well. However, commercial payers may apply proprietary bundling edits in addition to or instead of standard NCCI edits.
*   Improper unbundling detected by NCCI edits triggers CARC CO-97 (benefit included in another procedure) and RARC M80 or M144 on the EDI 835 ERA.
*   Intentional unbundling to maximize reimbursement constitutes healthcare fraud and may trigger False Claims Act (FCA) liability, Anti-Kickback Statute (AKS) penalties, and OIG exclusion.
*   Legitimate use of NCCI modifier overrides requires that the services were truly distinct (different anatomical site, different session, different encounter, or different patient) and is supported by clinical documentation.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** An EDI 837 claim containing two or more CPT/HCPCS codes that are paired in the NCCI PTP edit table.
*   **Downstream Impacts:** NCCI edit failures result in CARC CO-97 denials on the EDI 835 ERA. Pre-submission claim scrubbing against NCCI edits prevents denials. Intentional unbundling violations trigger federal fraud statute liability (FCA, AKS).

---
concept_id: premium_tax_credits_aca
domain: Regulatory
jurisdiction: Federal
audience: Consumer, Broker
tags: [PTC, premium_tax_credit, ACA_subsidy, marketplace, income_eligibility]
---

### ACA Premium Tax Credits: Federal Subsidies for Marketplace Health Insurance

**Semantic Summary:**
Premium Tax Credits (PTCs) are refundable federal tax credits established under Affordable Care Act (ACA) Section 36B that reduce the monthly premium cost for eligible individuals and families who purchase health insurance through the Health Insurance Marketplace (HealthCare.gov or a state-based exchange). PTC eligibility is based on household income relative to the Federal Poverty Level (FPL) and the cost of the benchmark Silver plan in the enrollee's geographic rating area. PTCs may be taken in advance (Advanced Premium Tax Credit, or APTC) to lower monthly payments or claimed when filing the annual federal tax return.

**Detailed Mechanics:**
*   PTC eligibility requires: household income between 100% and 400% of the Federal Poverty Level (FPL) under standard ACA rules. However, the Inflation Reduction Act (IRA) temporarily eliminated the 400% FPL income cap through 2025, extending PTC eligibility to higher-income households who would otherwise pay more than 8.5% of household income for the benchmark Silver plan.
*   The PTC amount is calculated as the difference between the cost of the second-lowest-cost Silver plan (the "benchmark plan") in the enrollee's rating area and the enrollee's expected contribution (a percentage of household income based on a sliding scale defined by IRS).
*   PTCs can ONLY be used for plans purchased through the ACA marketplace. They cannot be applied to off-marketplace plans, employer-sponsored plans, Medicare, Medicaid, or CHIP.
*   If household income changes during the year, the enrollee must report the change to the marketplace to adjust the APTC amount. At tax filing, the actual PTC is reconciled against the APTC received. If actual income exceeds the estimate, the enrollee may owe back a portion of the excess APTC.
*   Individuals who are eligible for "affordable" employer-sponsored coverage (where the employee's share of the self-only premium is less than 8.39% of household income for 2024) or eligible for Medicare, Medicaid, or CHIP are NOT eligible for PTCs.

**Critical Exclusions & Edge Cases:**
*   PTCs cannot be used to offset the ACA tobacco use premium surcharge (up to 50%). The tobacco surcharge is applied on top of the subsidized premium.
*   Married individuals must file a joint tax return to claim PTCs, with limited exceptions for domestic abuse or spousal abandonment.
*   The "family glitch fix" (effective 2023) expanded PTC eligibility to family members of employees whose employer-sponsored coverage is affordable for the employee but unaffordable for the family (family premium exceeds the affordability threshold).
*   If the IRA's enhanced PTCs expire after 2025 without congressional extension, millions of marketplace enrollees will face significant premium increases due to the reinstatement of the 400% FPL income cap.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** The individual must not be eligible for affordable employer-sponsored coverage, Medicare, Medicaid, or CHIP. The individual must purchase coverage through the ACA marketplace during Open Enrollment or a qualifying SEP.
*   **Downstream Impacts:** PTC amount directly reduces the enrollee's monthly premium. PTC calculation is based on the benchmark Silver plan in the enrollee's geographic rating area (GRA). APTC reconciliation at tax filing may result in additional tax liability or a refund.
