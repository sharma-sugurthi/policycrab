"""
Pydantic models for organizations (team workspaces), members and invitations.
"""

import re

from pydantic import BaseModel, Field, field_validator

ROLES = ("owner", "admin", "member", "viewer")
INVITABLE_ROLES = ("admin", "member", "viewer")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Organization name is too short.")
        return v


class OrganizationRename(OrganizationCreate):
    pass


class OrganizationOut(BaseModel):
    id: str
    name: str
    slug: str
    owner_id: str
    plan: str = "team"
    created_at: str | None = None
    role: str | None = Field(None, description="The requesting user's role in this organization.")
    member_count: int | None = None


class MemberOut(BaseModel):
    user_id: str
    email: str | None = None
    role: str
    created_at: str | None = None
    is_you: bool = False


class MemberRoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in INVITABLE_ROLES:
            raise ValueError(f"role must be one of {', '.join(INVITABLE_ROLES)}")
        return v


class InvitationCreate(BaseModel):
    email: str = Field(..., max_length=254)
    role: str = "member"

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address.")
        return v

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in INVITABLE_ROLES:
            raise ValueError(f"role must be one of {', '.join(INVITABLE_ROLES)}")
        return v


class InvitationOut(BaseModel):
    id: str
    org_id: str
    email: str
    role: str
    invited_by: str | None = None
    expires_at: str | None = None
    created_at: str | None = None
    email_sent: bool | None = None
    # Only populated when the invitation email could not be sent, so an admin can
    # hand the link over manually. Never stored.
    accept_url: str | None = None


class InvitationAccept(BaseModel):
    token: str = Field(..., min_length=16, max_length=256)


class InvitationPreview(BaseModel):
    status: str = Field(..., description="valid | expired | revoked | accepted | invalid")
    org_name: str | None = None
    role: str | None = None
    email: str | None = None
    invited_by_email: str | None = None
    expires_at: str | None = None


class OrgStatus(BaseModel):
    enabled: bool
