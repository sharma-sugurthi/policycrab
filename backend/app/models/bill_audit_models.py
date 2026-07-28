"""
Bill Audit Models — Pydantic schemas for the Bill Auditor feature.

ServiceLineInput:  Structured representation of a single line item on a medical bill.
AuditFlag:         A single audit finding (upcoding, unbundling, etc.) for a service line.
BillAuditResult:   The complete audit report returned to the frontend.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class ServiceLineInput(BaseModel):
    """A single line item on a medical bill or EOB."""
    line_number: int = Field(..., description="1-indexed position on the bill")
    cpt_code: str | None = Field(None, description="CPT/HCPCS procedure code")
    cpt_description: str | None = Field(None, description="Procedure description")
    icd_10_code: str | None = Field(None, description="ICD-10-CM diagnosis code")
    icd_10_description: str | None = Field(None, description="Diagnosis description")
    billed_amount: float | None = Field(None, description="Provider's billed charge")
    allowed_amount: float | None = Field(None, description="Insurer's allowed amount (if known)")
    date_of_service: str | None = Field(None, description="Date of service (YYYY-MM-DD)")
    provider_name: str | None = Field(None, description="Provider or facility name")
    units: int = Field(1, description="Number of units billed")
    modifier: str | None = Field(None, description="CPT modifier (e.g., -26, -TC, -59)")


class AuditFlag(BaseModel):
    """A single audit finding for a service line."""
    line_number: int = Field(..., description="Which line item this flag refers to")
    issue_type: str = Field(
        ...,
        description=(
            "One of: upcoding, unbundling, duplicate, excessive_charge, "
            "coding_mismatch, modifier_error, balance_billing"
        ),
    )
    severity: str = Field(..., description="critical | warning | info")
    description: str = Field(..., description="Detailed explanation of the issue")
    recommendation: str = Field(..., description="Actionable next step for the patient")
    estimated_savings: float | None = Field(
        None, description="Estimated dollar savings if corrected"
    )


class BillAuditResult(BaseModel):
    """Complete audit report for a medical bill."""
    overall_risk: str = Field(..., description="high | medium | low")
    total_billed: float = Field(0.0, description="Sum of all billed amounts")
    estimated_fair_total: float | None = Field(
        None, description="Estimated fair market total for the services"
    )
    potential_savings: float | None = Field(
        None, description="Total estimated savings across all flags"
    )
    flags: list[AuditFlag] = Field(default_factory=list, description="All audit findings")
    summary: str = Field("", description="Human-readable audit summary")
    line_count: int = Field(0, description="Number of service lines audited")
    dispute_letter: str | None = Field(None, description="Generated dispute letter text")
    audited_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO timestamp of audit",
    )
