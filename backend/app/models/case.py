"""Pydantic models for case management."""

from datetime import date

from pydantic import BaseModel, Field, field_validator

OPEN_STATUSES = ("new", "in_review", "appeal_filed", "awaiting_decision")
CLOSED_STATUSES = ("won", "partial", "lost", "withdrawn")
STATUSES = OPEN_STATUSES + CLOSED_STATUSES
PRIORITIES = ("low", "normal", "high", "urgent")


def _clean_status(v):
    if v is None:
        return None
    v = str(v).strip().lower()
    if v not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    return v


def _clean_priority(v):
    if v is None:
        return None
    v = str(v).strip().lower()
    if v not in PRIORITIES:
        raise ValueError(f"priority must be one of {', '.join(PRIORITIES)}")
    return v


class CaseCreate(BaseModel):
    claim_id: str = Field(..., min_length=8, max_length=64)
    title: str | None = Field(None, max_length=140)
    assignee_id: str | None = None
    priority: str = "normal"
    due_date: date | None = None
    amount_at_stake: float | None = Field(None, ge=0)
    reference: str | None = Field(None, max_length=60)
    notes: str | None = Field(None, max_length=4000)

    _priority = field_validator("priority")(classmethod(lambda cls, v: _clean_priority(v) or "normal"))


class CaseUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=140)
    status: str | None = None
    assignee_id: str | None = None
    clear_assignee: bool = False
    priority: str | None = None
    due_date: date | None = None
    clear_due_date: bool = False
    amount_at_stake: float | None = Field(None, ge=0)
    reference: str | None = Field(None, max_length=60)
    notes: str | None = Field(None, max_length=4000)

    _status = field_validator("status")(classmethod(lambda cls, v: _clean_status(v)))
    _priority = field_validator("priority")(classmethod(lambda cls, v: _clean_priority(v)))


class CaseComment(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class CaseEventOut(BaseModel):
    id: str
    case_id: str
    event_type: str
    actor_id: str | None = None
    actor_email: str | None = None
    message: str | None = None
    data: dict = {}
    created_at: str | None = None
