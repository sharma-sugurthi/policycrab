"""
Organizations API — team workspaces, members and email invitations.

Every endpoint except /status answers 404 while ORGS_ENABLED is false, so the
feature is invisible on deployments that have not opted in. Authorization is
enforced in app/services/organizations.py; this module only maps its
exceptions onto HTTP status codes.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.auth import get_current_user
from app.api.org_context import require_orgs_enabled, translate_org_error, valid_uuid_or_404
from app.config import settings
from app.models.organization import (
    InvitationAccept,
    InvitationCreate,
    InvitationOut,
    InvitationPreview,
    MemberOut,
    MemberRoleUpdate,
    OrganizationCreate,
    OrganizationOut,
    OrganizationRename,
    OrgStatus,
)
from app.security.rate_limit import rate_limit_user
from app.services import organizations as org_service
from app.services.email_service import get_email_service
from app.services.organizations import OrgError, OrgNotFound, OrgPermissionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orgs", tags=["Organizations"])

ORG_CREATE_RATE_LIMIT = rate_limit_user("orgs:create", max_requests=5, window_seconds=3600)
ORG_INVITE_RATE_LIMIT = rate_limit_user("orgs:invite", max_requests=20, window_seconds=3600)
ORG_ACCEPT_RATE_LIMIT = rate_limit_user("orgs:accept", max_requests=10, window_seconds=600)

_ORG_ERRORS = (OrgNotFound, OrgPermissionError, OrgError)


def _org_out(org: dict, role: str | None = None, member_count: int | None = None) -> OrganizationOut:
    return OrganizationOut(
        id=str(org.get("id")),
        name=org.get("name") or "",
        slug=org.get("slug") or "",
        owner_id=str(org.get("owner_id") or ""),
        plan=org.get("plan") or "team",
        created_at=org.get("created_at"),
        role=role if role is not None else org.get("role"),
        member_count=member_count,
    )


def _member_out(row: dict, current_user_id: str) -> MemberOut:
    return MemberOut(
        user_id=str(row.get("user_id")),
        email=row.get("email"),
        role=row.get("role") or "viewer",
        created_at=row.get("created_at"),
        is_you=str(row.get("user_id")) == str(current_user_id),
    )


def _invitation_out(row: dict, **extra) -> InvitationOut:
    return InvitationOut(
        id=str(row.get("id")),
        org_id=str(row.get("org_id")),
        email=row.get("email") or "",
        role=row.get("role") or "member",
        invited_by=str(row["invited_by"]) if row.get("invited_by") else None,
        expires_at=row.get("expires_at"),
        created_at=row.get("created_at"),
        **extra,
    )


def _membership_or_http(org_id: str, user: dict, minimum: str = "viewer") -> dict:
    org_id = valid_uuid_or_404(org_id)
    try:
        return org_service.require_membership(org_id, user["id"], minimum)
    except _ORG_ERRORS as exc:
        raise translate_org_error(exc) from exc


# ── Feature status ────────────────────────────────────────────────────

@router.get("/status", response_model=OrgStatus)
async def org_status(user: dict = Depends(get_current_user)):
    """Whether team workspaces are enabled on this deployment."""
    return OrgStatus(enabled=org_service.orgs_enabled())


# ── Invitations addressed to the signed-in user (declared before /{org_id}) ──

@router.get("/invitations/preview", response_model=InvitationPreview)
async def preview_invitation(
    token: str = Query(..., min_length=16, max_length=256),
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    """Describe an invitation so the accept page can show what is being joined."""
    return InvitationPreview(**org_service.preview_invitation(token))


@router.post("/invitations/accept", response_model=OrganizationOut)
async def accept_invitation(
    body: InvitationAccept,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
    _rl: None = Depends(ORG_ACCEPT_RATE_LIMIT),
):
    """Redeem an invitation token for the signed-in user (email must match)."""
    try:
        membership = org_service.accept_invitation(user["id"], user.get("email"), body.token)
    except _ORG_ERRORS as exc:
        raise translate_org_error(exc) from exc
    org = org_service.get_organization(membership["org_id"]) or {"id": membership["org_id"]}
    return _org_out(org, role=membership.get("role"))


# ── Organizations ────────────────────────────────────────────────────

@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
    _rl: None = Depends(ORG_CREATE_RATE_LIMIT),
):
    """Create a team workspace; the creator becomes its owner."""
    try:
        org = org_service.create_organization(user["id"], user.get("email"), body.name)
    except _ORG_ERRORS as exc:
        raise translate_org_error(exc) from exc
    return _org_out(org, role="owner", member_count=1)


@router.get("", response_model=list[OrganizationOut])
async def list_my_organizations(
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    return [_org_out(o) for o in org_service.list_user_organizations(user["id"])]


@router.get("/{org_id}", response_model=OrganizationOut)
async def get_organization(
    org_id: str,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    membership = _membership_or_http(org_id, user)
    org = org_service.get_organization(org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return _org_out(org, role=membership.get("role"), member_count=org_service.count_members(org_id))


@router.patch("/{org_id}", response_model=OrganizationOut)
async def rename_organization(
    org_id: str,
    body: OrganizationRename,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    membership = _membership_or_http(org_id, user, "admin")
    try:
        org = org_service.rename_organization(org_id, membership, body.name)
    except _ORG_ERRORS as exc:
        raise translate_org_error(exc) from exc
    return _org_out(org, role=membership.get("role"))


@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    """Owner only. Members and invitations are removed; saved claims keep their author."""
    membership = _membership_or_http(org_id, user, "owner")
    try:
        deleted = org_service.delete_organization(org_id, membership)
    except _ORG_ERRORS as exc:
        raise translate_org_error(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return {"success": True, "deleted_id": org_id}


# ── Members ──────────────────────────────────────────────────────────

@router.get("/{org_id}/members", response_model=list[MemberOut])
async def list_members(
    org_id: str,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    _membership_or_http(org_id, user)
    return [_member_out(r, user["id"]) for r in org_service.list_members(org_id)]


@router.patch("/{org_id}/members/{member_user_id}", response_model=MemberOut)
async def update_member_role(
    org_id: str,
    member_user_id: str,
    body: MemberRoleUpdate,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    membership = _membership_or_http(org_id, user, "admin")
    member_user_id = valid_uuid_or_404(member_user_id, "Member")
    try:
        row = org_service.update_member_role(org_id, membership, member_user_id, body.role)
    except _ORG_ERRORS as exc:
        raise translate_org_error(exc) from exc
    return _member_out(row, user["id"])


@router.delete("/{org_id}/members/{member_user_id}")
async def remove_member(
    org_id: str,
    member_user_id: str,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    """Admins remove members/viewers; any non-owner may remove themselves (leave)."""
    membership = _membership_or_http(org_id, user)
    member_user_id = valid_uuid_or_404(member_user_id, "Member")
    try:
        removed = org_service.remove_member(org_id, membership, member_user_id)
    except _ORG_ERRORS as exc:
        raise translate_org_error(exc) from exc
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found.")
    return {"success": True, "removed_user_id": member_user_id}


# ── Invitations managed by admins ────────────────────────────────────

@router.get("/{org_id}/invitations", response_model=list[InvitationOut])
async def list_invitations(
    org_id: str,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    _membership_or_http(org_id, user, "admin")
    return [_invitation_out(r) for r in org_service.list_pending_invitations(org_id)]


@router.post("/{org_id}/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    org_id: str,
    body: InvitationCreate,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
    _rl: None = Depends(ORG_INVITE_RATE_LIMIT),
):
    """
    Invite someone by email. The one-time link is emailed via Resend; when email is
    not configured the link is returned once to the inviting admin instead.
    """
    membership = _membership_or_http(org_id, user, "admin")
    try:
        row, raw_token = org_service.create_invitation(org_id, membership, body.email, body.role)
    except _ORG_ERRORS as exc:
        raise translate_org_error(exc) from exc

    org = org_service.get_organization(org_id) or {}
    accept_url = org_service.build_accept_url(raw_token)
    sent = get_email_service().send_org_invitation(
        to_email=body.email,
        org_name=org.get("name") or "your team",
        inviter_email=membership.get("email") or user.get("email") or "",
        role=body.role,
        accept_url=accept_url,
        expires_days=max(1, int(settings.org_invitation_ttl_days or 7)),
    )
    return _invitation_out(row, email_sent=sent, accept_url=None if sent else accept_url)


@router.delete("/{org_id}/invitations/{invitation_id}")
async def revoke_invitation(
    org_id: str,
    invitation_id: str,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    membership = _membership_or_http(org_id, user, "admin")
    invitation_id = valid_uuid_or_404(invitation_id, "Invitation")
    try:
        revoked = org_service.revoke_invitation(org_id, membership, invitation_id)
    except _ORG_ERRORS as exc:
        raise translate_org_error(exc) from exc
    if not revoked:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    return {"success": True, "revoked_id": invitation_id}


# ── Workspace data ───────────────────────────────────────────────────

@router.get("/{org_id}/claims")
async def list_org_claims(
    org_id: str,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    """Claims saved into this workspace by any member (same shape as /api/history/claims)."""
    _membership_or_http(org_id, user)
    return org_service.list_org_claims(org_id)


@router.get("/{org_id}/policies")
async def list_org_policies(
    org_id: str,
    user: dict = Depends(get_current_user),
    _flag: None = Depends(require_orgs_enabled),
):
    _membership_or_http(org_id, user)
    return org_service.list_org_policies(org_id)
