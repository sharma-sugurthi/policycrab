"""
US-specific enums for the health insurance claims engine.
These enums drive the entire system's routing, cost calculation,
and regulatory compliance logic.
"""

from enum import Enum


class PlanType(str, Enum):
    """Health insurance plan network model."""
    HMO = "HMO"    # Health Maintenance Organization — in-network only, requires PCP referral
    PPO = "PPO"    # Preferred Provider Organization — in/out-of-network, no referral needed
    EPO = "EPO"    # Exclusive Provider Organization — in-network only, no referral needed
    POS = "POS"    # Point of Service — in/out-of-network, requires PCP referral


class PlanLegalClassification(str, Enum):
    """Legal classification determines the appeal framework and applicable law."""
    FULLY_INSURED = "FULLY_INSURED"              # State Department of Insurance regulated
    SELF_FUNDED_ERISA = "SELF_FUNDED_ERISA"      # Federal ERISA, state law preempted
    MEDICARE_ADVANTAGE = "MEDICARE_ADVANTAGE"     # CMS 5-level appeal process
    MEDICARE_ORIGINAL = "MEDICARE_ORIGINAL"       # Medicare Parts A & B
    MEDICAID_MANAGED = "MEDICAID_MANAGED"         # State Medicaid managed care
    INDIVIDUAL_ACA = "INDIVIDUAL_ACA"             # ACA Marketplace plan


class NetworkStatus(str, Enum):
    """Provider network status relative to the patient's plan."""
    IN_NETWORK = "IN_NETWORK"
    OUT_OF_NETWORK = "OUT_OF_NETWORK"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # Emergencies under NSA — network irrelevant


class DenialReason(str, Enum):
    """Standardized claim denial categories mapped to CARC codes."""
    MEDICAL_NECESSITY = "MEDICAL_NECESSITY"               # CARC CO-50
    PRIOR_AUTH_MISSING = "PRIOR_AUTH_MISSING"             # CARC PR-243 / CO-197
    TIMELY_FILING = "TIMELY_FILING"                       # CARC CO-29
    NOT_COVERED = "NOT_COVERED"                           # Plan exclusion
    DUPLICATE_CLAIM = "DUPLICATE_CLAIM"                   # CARC CO-18
    COB_FAILURE = "COB_FAILURE"                           # CARC CO-22
    UNBUNDLING = "UNBUNDLING"                             # CARC CO-97 (NCCI edit)
    NSA_BALANCE_BILLING = "NSA_BALANCE_BILLING"           # No Surprises Act violation
    PRE_EXISTING_CONDITION = "PRE_EXISTING_CONDITION"     # ACA Section 2704 violation
    REFERRAL_MISSING = "REFERRAL_MISSING"                 # HMO/POS without PCP referral
    OUT_OF_NETWORK_DENIAL = "OUT_OF_NETWORK_DENIAL"       # HMO/EPO out-of-network
    OTHER = "OTHER"


class AppealFramework(str, Enum):
    """Legal appeal pathway, determined by plan legal classification."""
    ERISA_FEDERAL = "ERISA_FEDERAL"                          # 180-day deadline, federal law
    STATE_EXTERNAL_REVIEW = "STATE_EXTERNAL_REVIEW"          # State DOI external review
    MEDICARE_ADVANTAGE_5LEVEL = "MEDICARE_ADVANTAGE_5LEVEL"  # CMS 5-level process
    NSA_IDR = "NSA_IDR"                                      # No Surprises Act IDR
    STATE_DOI_COMPLAINT = "STATE_DOI_COMPLAINT"              # State DOI complaint filing


class MetalTier(str, Enum):
    """ACA marketplace plan metal tier by actuarial value."""
    CATASTROPHIC = "CATASTROPHIC"  # ~57% AV, under-30 or hardship exemption only
    BRONZE = "BRONZE"              # ~60% AV
    SILVER = "SILVER"              # ~70% AV (eligible for CSR)
    GOLD = "GOLD"                  # ~80% AV
    PLATINUM = "PLATINUM"          # ~90% AV


class ClaimStatus(str, Enum):
    """Status of a claim through the evaluation pipeline."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    DENIED = "DENIED"
    APPEAL_IN_PROGRESS = "APPEAL_IN_PROGRESS"
    APPEAL_RESOLVED = "APPEAL_RESOLVED"
