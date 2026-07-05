---
concept_id: erisa_preemption
domain: Regulatory
jurisdiction: Federal
audience: Consumer, Broker, Provider
tags: [ERISA, preemption, deemer_clause, self_funded, fully_insured]
---

### ERISA Preemption: Federal Law Governing Employer-Sponsored Health Plans

**Semantic Summary:**
The Employee Retirement Income Security Act of 1974 (ERISA) is a federal law that establishes minimum standards for most private-sector employer-sponsored health benefit plans and contains a powerful preemption clause that generally supersedes state insurance laws for self-funded (self-insured) employee benefit plans. ERISA's preemption framework creates a critical legal distinction between fully-insured and self-funded plans that determines whether state or federal law governs claims disputes, appeals, and available legal remedies.

**Detailed Mechanics:**
*   ERISA Section 514(a) (the "Preemption Clause") states that ERISA "shall supersede any and all State laws insofar as they may now or hereafter relate to any employee benefit plan."
*   ERISA Section 514(b)(2)(A) (the "Savings Clause") exempts state laws that regulate the "business of insurance" from preemption, meaning state insurance mandates still apply to the insurance products purchased by fully-insured plans.
*   ERISA Section 514(b)(2)(B) (the "Deemer Clause") states that no employee benefit plan shall be "deemed to be an insurance company" for the purpose of state insurance regulation. This effectively shields self-funded plans from state insurance mandates, state external review processes, and state-level consumer protection lawsuits.
*   Approximately 65% of covered workers in the United States are enrolled in self-funded plans, making ERISA preemption the dominant legal framework for employer-sponsored health coverage.

**Critical Exclusions & Edge Cases:**
*   ERISA does NOT apply to government employee plans (federal, state, or local), church plans, or individual market plans purchased on the ACA marketplace.
*   ERISA preemption severely limits available legal remedies. Under ERISA Section 502(a), a claimant who sues in federal court can generally only recover the value of the denied benefit, not compensatory damages, punitive damages, or damages for emotional distress.
*   Some states have enacted "surprise billing" or "external review" laws that apply to fully-insured plans but are preempted for self-funded plans under the Deemer Clause.
*   The No Surprises Act (NSA) is a federal law and therefore applies to BOTH fully-insured and self-funded ERISA plans.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** The patient must be enrolled in an employer-sponsored health benefit plan governed by ERISA (not a government, church, or individual market plan).
*   **Downstream Impacts:** Determines whether state or federal appeal timelines apply, whether external review rights exist, whether state-mandated benefits are enforceable, and the scope of legal remedies available in litigation. Directly impacts the routing of ERISA Claim Appeal Timelines.

---
concept_id: erisa_claim_appeal_timelines
domain: Regulatory
jurisdiction: Federal
audience: Consumer, Provider
tags: [ERISA, appeal_timelines, full_fair_review, claim_denial, exhaustion_of_remedies]
---

### ERISA Claim and Appeal Timelines: Federal Deadlines for Claim Determination and Review

**Semantic Summary:**
Under 29 CFR § 2560.503-1, the Employee Retirement Income Security Act (ERISA) mandates strict federal timelines for health plan administrators to issue initial claim determinations and for claimants to file and receive decisions on appeals, categorized by the urgency of the claim type (Urgent Care, Pre-Service, and Post-Service). These timelines govern the "full and fair review" process that must be exhausted before a claimant may pursue federal court litigation under ERISA Section 502(a).

**Detailed Mechanics:**
*   Urgent Care Claims: The plan administrator must issue an initial determination within 72 hours with no extensions permitted. The claimant has a minimum of 180 days to file an appeal. The plan must issue an appeal decision within 72 hours.
*   Pre-Service Claims (non-urgent): The plan administrator must issue an initial determination within 15 calendar days, with one 15-day extension permitted if the plan provides written notice of the need for the extension. The claimant has a minimum of 180 days to file an appeal. The plan must issue an appeal decision within 30 calendar days (or 15 days per level if two levels of appeal exist).
*   Post-Service Claims (retrospective): The plan administrator must issue an initial determination within 30 calendar days, with one 15-day extension permitted. The claimant has a minimum of 180 days to file an appeal. The plan must issue an appeal decision within 60 calendar days (or 30 days per level if two levels exist).
*   If an appeal deadline falls on a weekend or holiday, federal courts (e.g., the 9th Circuit in LeGras v. Aetna) have ruled that the deadline extends to the next business day.
*   The written denial notice must include: the specific reasons for the denial, the plan provisions upon which the denial is based, a description of any additional information needed, and an explanation of the plan's appeal procedures.

**Critical Exclusions & Edge Cases:**
*   If a plan administrator fails to strictly adhere to these procedural timeframes or fails to provide the required denial information, the claimant is generally "deemed to have exhausted" their administrative remedies and may proceed directly to federal court under ERISA Section 502(a).
*   If a plan offers a voluntary additional level of appeal beyond the mandatory levels, the statute of limitations for filing a federal lawsuit is tolled (paused) during the period of that voluntary review.
*   ERISA's "closed administrative record" rule means that in many circuits, a federal court reviewing the denial will only consider evidence that was part of the administrative record during the appeal. Claimants must submit all supporting medical evidence during the internal appeal phase.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** A claim denial issued by an ERISA-governed health plan. The plan type (self-funded vs. fully-insured) must have been identified via the ERISA Preemption analysis.
*   **Downstream Impacts:** Exhaustion of ERISA administrative appeals is a prerequisite for filing a federal lawsuit under ERISA Section 502(a). The standard of judicial review (de novo vs. arbitrary and capricious) depends on whether the plan grants the administrator discretionary authority.

---
concept_id: fully_insured_vs_self_funded_plans
domain: Health
jurisdiction: Federal
audience: Consumer, Broker, Underwriter
tags: [fully_insured, self_funded, self_insured, stop_loss, TPA]
---

### Fully-Insured vs. Self-Funded Health Plans: Risk Allocation and Regulatory Implications

**Semantic Summary:**
The fundamental distinction in U.S. employer-sponsored health coverage is between fully-insured plans, where the employer purchases a commercial insurance policy and transfers all claims risk to the insurance carrier, and self-funded (self-insured) plans, where the employer retains the financial risk of paying medical claims out of its own assets and typically contracts with a Third-Party Administrator (TPA) to process claims. This distinction determines whether state or federal law governs the plan under ERISA preemption.

**Detailed Mechanics:**
*   In a fully-insured plan, the employer pays a fixed premium to a health insurance carrier (e.g., Aetna, UnitedHealthcare, Cigna). The carrier assumes all financial risk for covered claims. Fully-insured plans are subject to state insurance regulations, state-mandated benefits, state premium taxes, and state external review processes.
*   In a self-funded plan, the employer pays claims directly from its own funds or a trust. The employer contracts with a Third-Party Administrator (TPA) to handle claims processing, provider network access, and member services. Self-funded plans are governed exclusively by federal ERISA law and are exempt from state insurance regulations under the Deemer Clause.
*   To mitigate catastrophic financial risk, self-funded employers typically purchase stop-loss insurance (also called excess loss insurance). Aggregate stop-loss covers total plan claims exceeding a predetermined annual ceiling. Individual (specific) stop-loss covers claims for a single participant exceeding a threshold (e.g., $150,000–$500,000 per member per year).
*   Approximately 65% of covered workers in the United States are enrolled in self-funded plans, with the percentage increasing significantly among large employers (200+ employees).

**Critical Exclusions & Edge Cases:**
*   Stop-loss insurance is NOT health insurance; it insures the employer's financial risk, not the individual employee's medical claims. The presence of stop-loss insurance does not convert a self-funded plan into a fully-insured plan for ERISA preemption purposes.
*   "Level-funded" plans are a hybrid model where small employers make fixed monthly payments to a carrier that includes claims funding, stop-loss premiums, and administrative costs. Level-funded plans are generally classified as self-funded for ERISA preemption purposes, though some states have attempted to regulate them as fully-insured.
*   The plan's Summary Plan Description (SPD) and Form 5500 annual filing indicate whether a plan is fully-insured or self-funded.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** Employer decision to sponsor a group health plan.
*   **Downstream Impacts:** Determines the applicable regulatory framework (ERISA Preemption), the availability of state-mandated benefits, the applicable appeal and grievance procedures, and whether state external review processes or state prompt-pay laws apply.

---
concept_id: aca_premium_rating_rules
domain: Regulatory
jurisdiction: Federal
audience: Broker, Underwriter
tags: [ACA, premium_rating, age_ratio, geographic_rating_area, community_rating]
---

### ACA Premium Rating Rules: The Four Permissible Factors for Premium Variation

**Semantic Summary:**
Under the Affordable Care Act's Public Health Service Act (PHSA) Section 2701, health insurance premiums in the individual and small group markets may only vary based on four explicitly permitted factors: age (maximum 3:1 ratio), tobacco use (maximum 1.5:1 ratio), family structure (individual vs. family), and geographic rating area (state-defined boundaries). This "modified community rating" system prohibits premium variation based on health status, gender, claims history, industry, or any other factor.

**Detailed Mechanics:**
*   Age Rating: Insurers may charge older adults no more than three times (3:1) the premium charged to younger adults for the same plan. The age curve is standardized using federal age rating factors published by CMS.
*   Tobacco Use: Insurers may impose a surcharge of up to 50% (1.5:1 ratio) on the premium for tobacco users. However, Premium Tax Credits cannot be applied to offset the tobacco surcharge, making this surcharge particularly burdensome for lower-income enrollees. Several states (e.g., California, New York, Massachusetts) prohibit tobacco rating entirely.
*   Family Structure: Premiums scale based on the number and ages of covered family members. Children under age 21 are rated at the lowest age band. Only the three oldest children under 21 are rated; additional children do not increase the premium.
*   Geographic Rating Areas (GRAs): Each state defines GRAs using Metropolitan Statistical Areas (MSAs) or county groupings. The default CMS methodology assigns each MSA as a separate rating area, with all non-MSA counties grouped as an additional area ("MSAs+1"). States may request alternative GRA configurations with actuarial justification.

**Critical Exclusions & Edge Cases:**
*   These rating rules apply ONLY to individual and small group markets. Large group markets (typically 51+ employees, or 101+ in some states) may use additional rating factors, such as industry and claims experience.
*   Grandfathered plans are not subject to ACA community rating requirements.
*   Rural GRAs typically have higher premiums due to lower provider competition, provider consolidation, and network adequacy requirements that force insurers to accept higher-cost contracts.
*   The ACA prohibits premium variation based on gender, pre-existing conditions, health status, and claims history in the individual and small group markets.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** The plan must be sold in the individual or small group market and be ACA-compliant (not grandfathered or STLDI).
*   **Downstream Impacts:** Geographic Rating Areas affect local premium levels, plan availability (number of competing plans), and network adequacy standards. Premium levels interact with Premium Tax Credit calculations for marketplace enrollees.

---
concept_id: aca_essential_health_benefits
domain: Regulatory
jurisdiction: Federal
audience: Consumer, Broker
tags: [EHB, essential_health_benefits, ACA_mandate, covered_services, minimum_coverage]
---

### ACA Essential Health Benefits (EHBs): The 10 Mandated Categories of Coverage

**Semantic Summary:**
Under the Affordable Care Act (ACA), all non-grandfathered health insurance plans sold in the individual and small group markets must cover a set of 10 categories of Essential Health Benefits (EHBs), as defined in ACA Section 1302(b). EHBs establish a federal floor of minimum coverage, ensuring that all ACA-compliant plans cover a standardized set of services regardless of the insurer or state.

**Detailed Mechanics:**
*   The 10 EHB categories are: (1) Ambulatory patient services (outpatient care), (2) Emergency services, (3) Hospitalization, (4) Maternity and newborn care, (5) Mental health and substance use disorder services (including behavioral health treatment and parity requirements under the Mental Health Parity and Addiction Equity Act), (6) Prescription drugs, (7) Rehabilitative and habilitative services and devices, (8) Laboratory services, (9) Preventive and wellness services and chronic disease management, (10) Pediatric services (including oral and vision care for children).
*   Each state selects a "benchmark plan" that defines the specific services within each EHB category for that state. The benchmark is typically the largest small group plan in the state.
*   ACA-compliant plans cannot impose annual or lifetime dollar limits on Essential Health Benefits.
*   Preventive care services recommended by the U.S. Preventive Services Task Force (USPSTF) with an "A" or "B" rating must be covered with zero cost-sharing (no deductible, copay, or coinsurance).

**Critical Exclusions & Edge Cases:**
*   EHB requirements do NOT apply to large group plans (51+ employees) or self-funded ERISA plans, though these plans must still comply with the prohibition on annual and lifetime dollar limits for EHBs.
*   Grandfathered plans are exempt from the EHB mandate.
*   Services NOT included in EHBs (and therefore not required to be covered) typically include: cosmetic surgery, adult dental and vision care, long-term care (custodial), and weight loss programs (varies by state benchmark).
*   Short-term limited-duration insurance (STLDI) plans are NOT required to cover EHBs.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** The plan must be an ACA-compliant plan sold in the individual or small group market.
*   **Downstream Impacts:** The EHB benchmark determines what services are subject to the prohibition on annual/lifetime limits, what services count toward the Out-of-Pocket Maximum, and what services are eligible for Cost-Sharing Reductions on Silver-tier marketplace plans.

---
concept_id: no_surprises_act_overview
domain: Regulatory
jurisdiction: Federal
audience: Consumer, Provider
tags: [NSA, no_surprises_act, balance_billing, QPA, patient_protections]
---

### No Surprises Act (NSA): Federal Protections Against Surprise Out-of-Network Billing

**Semantic Summary:**
The No Surprises Act (NSA), enacted as part of the Consolidated Appropriations Act of 2021 and effective January 1, 2022, is a federal law that prohibits out-of-network healthcare providers from "balance billing" (billing patients for the difference between their billed charges and the insurer's payment) for emergency services, air ambulance services provided by out-of-network air ambulance providers, and non-emergency services provided by out-of-network providers at in-network facilities without the patient's prior written informed consent. Under the NSA, patient cost-sharing for these protected services is limited to in-network rates, calculated using the Qualifying Payment Amount (QPA).

**Detailed Mechanics:**
*   For emergency services, the NSA applies regardless of whether the emergency facility is in-network or out-of-network. The patient's cost-sharing (deductible, copay, coinsurance) is calculated as if the provider were in-network.
*   For non-emergency services at in-network facilities, the NSA protects patients from surprise bills from out-of-network providers (e.g., anesthesiologists, radiologists, pathologists) who the patient did not choose and could not have reasonably anticipated would be out-of-network. The out-of-network provider may only balance bill the patient if they provide written notice at least 72 hours before the service (or at least 3 hours for same-day services) AND the patient provides written informed consent.
*   The NSA applies to commercial health plans (both fully-insured and self-funded ERISA plans), Federal Employees Health Benefits (FEHB) plans, and state and local government plans. The NSA does NOT apply to Medicare, Medicaid, TRICARE, Indian Health Service, or Veterans Affairs health coverage.
*   The NSA introduced the Good Faith Estimate (GFE) requirement: providers must give uninsured or self-pay patients a GFE at least 3 business days before a scheduled service. If the final bill exceeds the GFE by $400 or more, the patient may initiate the Patient-Provider Dispute Resolution (PPDR) process.

**Critical Exclusions & Edge Cases:**
*   The NSA does NOT apply to ground ambulance services; only air ambulance services are covered.
*   The NSA does NOT protect patients who voluntarily choose an out-of-network provider and sign a valid informed consent waiver.
*   Emergency department providers cannot require patients to sign a consent waiver for balance billing as a condition of receiving emergency care.
*   State surprise billing laws may offer additional protections beyond the NSA for fully-insured plans but are preempted by ERISA for self-funded plans.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** The patient must have a commercial health plan (not Medicare/Medicaid). The service must qualify as emergency care, air ambulance, or non-emergency care at an in-network facility by an out-of-network provider.
*   **Downstream Impacts:** Triggers the Qualifying Payment Amount (QPA) calculation to determine patient cost-sharing. If the provider disputes the payment, triggers the Federal Independent Dispute Resolution (IDR) process. Introduces specific RARC codes (N864, N872) on the EDI 835 remittance.

---
concept_id: qualifying_payment_amount_qpa
domain: Regulatory
jurisdiction: Federal
audience: Provider, Underwriter
tags: [QPA, qualifying_payment_amount, median_contracted_rate, NSA, cost_sharing_benchmark]
---

### Qualifying Payment Amount (QPA): The Benchmark Rate Under the No Surprises Act

**Semantic Summary:**
The Qualifying Payment Amount (QPA) is a statutorily defined benchmark used under the No Surprises Act (NSA) to determine patient cost-sharing for protected out-of-network services and to serve as a key reference point in the Federal Independent Dispute Resolution (IDR) process. The QPA is defined as the health plan's median contracted rate for the same or similar service, provided by a similar specialty provider, in the same geographic region, as of January 31, 2019, adjusted annually for inflation using the Consumer Price Index for All Urban Consumers (CPI-U).

**Detailed Mechanics:**
*   The QPA is calculated by each health plan or issuer individually, using its own contracted rates from January 31, 2019 as the base, indexed forward by CPI-U inflation.
*   The geographic region for QPA calculation is typically defined by the plan as a Metropolitan Statistical Area (MSA), a state, or a Census division, depending on available data.
*   The QPA is used to set the patient's cost-sharing (deductible, copay, coinsurance) for NSA-protected services. The patient pays no more than what they would have paid had the service been provided by an in-network provider.
*   In the IDR process, the certified IDR entity must consider the QPA alongside other permissible factors: the level of training and experience of the provider, the complexity of the service, the patient's acuity, previous good-faith contracting efforts, and market share. The IDR entity is prohibited from considering the provider's billed charges (chargemaster rates) or Medicare/Medicaid rates.

**Critical Exclusions & Edge Cases:**
*   The medical community has criticized the QPA methodology, alleging that some insurers artificially suppress the QPA by including "ghost rates" — contracted rates for services a specialized physician rarely or never performs — to drag down the median calculation.
*   If a plan did not have a median contracted rate for a specific service as of January 31, 2019 (e.g., for a new procedure code), alternative QPA calculation methods apply, such as using rates from similar services or independent databases.
*   Courts have ruled that the QPA should not be treated as the sole presumptive factor in IDR decisions; IDR entities must meaningfully consider all permissible factors.

**Relational Context (For Multi-Hop RAG):**
*   **Prerequisites:** A claim for a service protected under the No Surprises Act (emergency, air ambulance, or non-emergency at an in-network facility).
*   **Downstream Impacts:** Sets the patient's cost-sharing amount. Serves as a mandatory consideration in the Federal IDR process. Influences the insurer's initial payment offer to the out-of-network provider.
