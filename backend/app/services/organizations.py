"""
Organizations (team workspaces): membership, roles and email invitations.

All authorization for organizations is enforced HERE, in Python, because the
backend reaches Supabase with the service role (RLS does not apply to it).
Every function that mutates state takes the acting user's membership row and
checks it against the role rules below before touching the database.

Role ladder (highest first): owner > admin > member > viewer
  - owner   : everything, including deleting the organization. Exactly one per org
              (the creator); ownership transfer is intentionally out of scope.
  - admin   : invite/remove members and viewers, change their roles, rename the org.
  - member  : run evaluations inside the workspace, see workspace claims.
  - viewer  : read-only access to workspace claims.

Invitations use a one-time random token. Only its SHA-256 is stored; the raw
token exists in the invitation email (and, when email is not configured, in the
API response to the inviting admin). Accepting requires the signed-in user's
email to match the invited address.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.config import settings
from app.models.organization import INVITABLE_ROLES
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

ROLE_RANK = {"owner": 4, "admin": 3, "member": 2, "viewer": 1}
MAX_ORGS_OWNED_PER_USER = 5
MAX_MEMBERS_PER_ORG = 50
MAX_PENDING_INVITATIONS_PER_ORG = 50


class OrgError(ValueError):
    """Bad request (validation / state) — maps to HTTP 400."""


class OrgPermissionError(PermissionError):
    """Acting user lacks the role required — maps to HTTP 403."""


class OrgNotFound(LookupError):
    """Organization does not exist or the user is not a member — maps to HTTP 404."""


# ── Pure helpers (no I/O) ─────────────────────────────────────────────

def orgs_enabled() -> bool:
    return bool(settings.orgs_enabled)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "org"
    return f"{base}-{secrets.token_hex(3)}"


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)


def hash_invitation_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def role_at_least(role: str | None, minimum: str) -> bool:
    return ROLE_RANK.get(role or "", 0) >= ROLE_RANK[minimum]


def can_grant_role(actor_role: str | None, target_role: str) -> bool:
    """Which roles an actor may hand out (on invite or role change)."""
    if target_role not in INVITABLE_ROLES:
        return False
    if actor_role == "owner":
        return True
    if actor_role == "admin":
        return target_role in ("member", "viewer")
    return False


def can_manage_member(actor_role: str | None, target_role: str | None) -> bool:
    """Whether actor may change or remove a member holding target_role."""
    if target_role == "owner":
        return False
    if actor_role == "owner":
        return True
    if actor_role == "admin":
        return target_role in ("member", "viewer")
    return False


def invitation_status(row: dict, now: datetime | None = None) -> str:
    now = now or _now()
    if row.get("accepted_at"):
        return "accepted"
    if row.get("revoked_at"):
        return "revoked"
    expires = _parse_ts(row.get("expires_at"))
    if expires is None or expires <= now:
        return "expired"
    return "valid"


def build_accept_url(raw_token: str) -> str:
    base = (settings.app_base_url or "").rstrip("/")
    return f"{base}/invite?token={raw_token}"


# ── Lookups ───────────────────────────────────────────────────────────

def get_organization(org_id: str) -> dict | None:
    client = get_supabase_client()
    result = (
        client.table("organizations")
        .select("id, name, slug, owner_id, plan, created_at")
        .eq("id", org_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_membership(org_id: str, user_id: str) -> dict | None:
    client = get_supabase_client()
    result = (
        client.table("org_members")
        .select("id, org_id, user_id, email, role, created_at")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def require_membership(org_id: str, user_id: str, minimum: str = "viewer") -> dict:
    """
    Return the acting user's membership row or raise.

    Non-members get OrgNotFound (404) rather than 403 so organization ids cannot be
    enumerated; members below `minimum` get OrgPermissionError (403).
    """
    membership = get_membership(org_id, user_id)
    if membership is None:
        raise OrgNotFound("Organization not found.")
    if not role_at_least(membership.get("role"), minimum):
        raise OrgPermissionError(f"This action requires the {minimum} role or higher.")
    return membership


def list_user_organizations(user_id: str) -> list[dict]:
    client = get_supabase_client()
    memberships = (
        client.table("org_members")
        .select("org_id, role")
        .eq("user_id", user_id)
        .execute()
    ).data or []
    if not memberships:
        return []
    role_by_org = {m["org_id"]: m["role"] for m in memberships}
    orgs = (
        client.table("organizations")
        .select("id, name, slug, owner_id, plan, created_at")
        .in_("id", list(role_by_org))
        .order("created_at", desc=True)
        .execute()
    ).data or []
    out = []
    for org in orgs:
        item = dict(org)
        item["role"] = role_by_org.get(org["id"])
        out.append(item)
    return out


def list_members(org_id: str) -> list[dict]:
    client = get_supabase_client()
    result = (
        client.table("org_members")
        .select("user_id, email, role, created_at")
        .eq("org_id", org_id)
        .order("created_at", desc=False)
        .execute()
    )
    rows = result.data or []
    rows.sort(key=lambda r: -ROLE_RANK.get(r.get("role"), 0))
    return rows


def count_members(org_id: str) -> int:
    client = get_supabase_client()
    result = (
        client.table("org_members")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .execute()
    )
    return result.count if result.count is not None else len(result.data or [])


# ── Organizations ────────────────────────────────────────────────────

def create_organization(owner_id: str, owner_email: str | None, name: str) -> dict:
    client = get_supabase_client()

    owned = (
        client.table("organizations")
        .select("id", count="exact")
        .eq("owner_id", owner_id)
        .execute()
    )
    owned_count = owned.count if owned.count is not None else len(owned.data or [])
    if owned_count >= MAX_ORGS_OWNED_PER_USER:
        raise OrgError(f"You already own the maximum of {MAX_ORGS_OWNED_PER_USER} organizations.")

    org_id = str(uuid4())
    org_payload = {
        "id": org_id,
        "name": name,
        "slug": slugify(name),
        "owner_id": owner_id,
        "plan": "team",
    }
    org_result = client.table("organizations").insert(org_payload).execute()
    org = org_result.data[0] if org_result.data else org_payload

    member_payload = {
        "id": str(uuid4()),
        "org_id": org_id,
        "user_id": owner_id,
        "email": (owner_email or "").lower() or None,
        "role": "owner",
        "invited_by": None,
    }
    client.table("org_members").insert(member_payload).execute()

    logger.info(f"Organization created: {org_id} by user {owner_id}")
    out = dict(org)
    out["role"] = "owner"
    return out


def rename_organization(org_id: str, actor: dict, name: str) -> dict:
    if not role_at_least(actor.get("role"), "admin"):
        raise OrgPermissionError("Only owners and admins can rename an organization.")
    client = get_supabase_client()
    result = (
        client.table("organizations")
        .update({"name": name, "updated_at": _iso(_now())})
        .eq("id", org_id)
        .execute()
    )
    if not result.data:
        raise OrgNotFound("Organization not found.")
    return result.data[0]


def delete_organization(org_id: str, actor: dict) -> bool:
    if actor.get("role") != "owner":
        raise OrgPermissionError("Only the owner can delete an organization.")
    client = get_supabase_client()
    # Members, invitations cascade; user_claims/user_policies.org_id become NULL.
    result = client.table("organizations").delete().eq("id", org_id).execute()
    deleted = bool(result.data)
    if deleted:
        logger.info(f"Organization deleted: {org_id} by owner {actor.get('user_id')}")
    return deleted


# ── Members ──────────────────────────────────────────────────────────

def update_member_role(org_id: str, actor: dict, target_user_id: str, new_role: str) -> dict:
    if new_role not in INVITABLE_ROLES:
        raise OrgError(f"role must be one of {', '.join(INVITABLE_ROLES)}.")
    if target_user_id == actor.get("user_id"):
        raise OrgError("You cannot change your own role.")
    target = get_membership(org_id, target_user_id)
    if target is None:
        raise OrgNotFound("Member not found.")
    if not can_manage_member(actor.get("role"), target.get("role")):
        raise OrgPermissionError("You cannot change this member's role.")
    if not can_grant_role(actor.get("role"), new_role):
        raise OrgPermissionError(f"You cannot grant the {new_role} role.")

    client = get_supabase_client()
    result = (
        client.table("org_members")
        .update({"role": new_role})
        .eq("org_id", org_id)
        .eq("user_id", target_user_id)
        .execute()
    )
    if not result.data:
        raise OrgNotFound("Member not found.")
    return result.data[0]


def remove_member(org_id: str, actor: dict, target_user_id: str) -> bool:
    target = get_membership(org_id, target_user_id)
    if target is None:
        raise OrgNotFound("Member not found.")
    if target.get("role") == "owner":
        raise OrgError("The owner cannot be removed. Delete the organization instead.")
    is_self = target_user_id == actor.get("user_id")
    if not is_self and not can_manage_member(actor.get("role"), target.get("role")):
        raise OrgPermissionError("You cannot remove this member.")

    client = get_supabase_client()
    result = (
        client.table("org_members")
        .delete()
        .eq("org_id", org_id)
        .eq("user_id", target_user_id)
        .execute()
    )
    removed = bool(result.data)
    if removed:
        logger.info(f"Member {target_user_id} removed from org {org_id} by {actor.get('user_id')}")
    return removed


# ── Invitations ──────────────────────────────────────────────────────

def _pending_invitations_query(client, org_id: str):
    return (
        client.table("org_invitations")
        .select("id, org_id, email, role, invited_by, expires_at, accepted_at, revoked_at, created_at")
        .eq("org_id", org_id)
        .is_("accepted_at", "null")
        .is_("revoked_at", "null")
    )


def list_pending_invitations(org_id: str) -> list[dict]:
    client = get_supabase_client()
    rows = _pending_invitations_query(client, org_id).order("created_at", desc=True).execute().data or []
    now = _now()
    return [r for r in rows if invitation_status(r, now) == "valid"]


def create_invitation(org_id: str, actor: dict, email: str, role: str) -> tuple[dict, str]:
    """
    Create a pending invitation and return (row, raw_token).

    The raw token is returned exactly once so the caller can email it; only its
    hash is persisted. Any earlier pending invitation for the same address in
    this organization is revoked first.
    """
    email = email.strip().lower()
    if not role_at_least(actor.get("role"), "admin"):
        raise OrgPermissionError("Only owners and admins can invite people.")
    if not can_grant_role(actor.get("role"), role):
        raise OrgPermissionError(f"You cannot invite someone as {role}.")
    if (actor.get("email") or "").lower() == email:
        raise OrgError("You are already a member of this organization.")

    client = get_supabase_client()

    existing_member = (
        client.table("org_members")
        .select("user_id")
        .eq("org_id", org_id)
        .eq("email", email)
        .limit(1)
        .execute()
    ).data
    if existing_member:
        raise OrgError(f"{email} is already a member of this organization.")

    if count_members(org_id) >= MAX_MEMBERS_PER_ORG:
        raise OrgError(f"This organization has reached the maximum of {MAX_MEMBERS_PER_ORG} members.")

    pending = _pending_invitations_query(client, org_id).execute().data or []
    now = _now()
    live_pending = [p for p in pending if invitation_status(p, now) == "valid"]
    same_email = [p for p in live_pending if (p.get("email") or "").lower() == email]
    if len(live_pending) - len(same_email) >= MAX_PENDING_INVITATIONS_PER_ORG:
        raise OrgError("Too many pending invitations. Revoke some before inviting more.")
    for stale in same_email:
        client.table("org_invitations").update({"revoked_at": _iso(now)}).eq("id", stale["id"]).execute()

    raw_token = generate_invitation_token()
    ttl_days = max(1, int(settings.org_invitation_ttl_days or 7))
    payload = {
        "id": str(uuid4()),
        "org_id": org_id,
        "email": email,
        "role": role,
        "token_hash": hash_invitation_token(raw_token),
        "invited_by": actor.get("user_id"),
        "expires_at": _iso(now + timedelta(days=ttl_days)),
    }
    result = client.table("org_invitations").insert(payload).execute()
    row = result.data[0] if result.data else payload
    logger.info(f"Invitation created for org {org_id} (role={role}) by {actor.get('user_id')}")
    return row, raw_token


def revoke_invitation(org_id: str, actor: dict, invitation_id: str) -> bool:
    if not role_at_least(actor.get("role"), "admin"):
        raise OrgPermissionError("Only owners and admins can revoke invitations.")
    client = get_supabase_client()
    result = (
        client.table("org_invitations")
        .update({"revoked_at": _iso(_now())})
        .eq("id", invitation_id)
        .eq("org_id", org_id)
        .execute()
    )
    return bool(result.data)


def _find_invitation_by_token(client, raw_token: str) -> dict | None:
    result = (
        client.table("org_invitations")
        .select("id, org_id, email, role, invited_by, expires_at, accepted_at, revoked_at, created_at")
        .eq("token_hash", hash_invitation_token(raw_token))
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def preview_invitation(raw_token: str) -> dict:
    """Non-mutating look at an invitation so the accept page can describe it."""
    client = get_supabase_client()
    row = _find_invitation_by_token(client, raw_token)
    if row is None:
        return {"status": "invalid"}
    org = get_organization(row["org_id"])
    inviter = None
    if row.get("invited_by"):
        inviter_row = get_membership(row["org_id"], row["invited_by"])
        inviter = (inviter_row or {}).get("email")
    return {
        "status": invitation_status(row),
        "org_name": (org or {}).get("name"),
        "role": row.get("role"),
        "email": row.get("email"),
        "invited_by_email": inviter,
        "expires_at": row.get("expires_at"),
    }


def accept_invitation(user_id: str, user_email: str | None, raw_token: str) -> dict:
    """
    Redeem an invitation for the signed-in user. Idempotent for an existing member.

    The invited address must match the signed-in user's email (case-insensitive)
    so a forwarded link cannot be redeemed by someone else.
    """
    client = get_supabase_client()
    row = _find_invitation_by_token(client, raw_token)
    if row is None:
        raise OrgNotFound("This invitation link is not valid.")

    status = invitation_status(row)
    if status == "accepted":
        existing = get_membership(row["org_id"], user_id)
        if existing:
            return existing
        raise OrgError("This invitation has already been used.")
    if status == "revoked":
        raise OrgError("This invitation was revoked.")
    if status == "expired":
        raise OrgError("This invitation has expired. Ask your administrator for a new one.")

    signed_in_email = (user_email or "").strip().lower()
    if not signed_in_email or signed_in_email != (row.get("email") or "").lower():
        raise OrgPermissionError(
            "This invitation was sent to a different email address. "
            "Sign in with the invited address to accept it."
        )

    existing = get_membership(row["org_id"], user_id)
    if existing is None:
        if count_members(row["org_id"]) >= MAX_MEMBERS_PER_ORG:
            raise OrgError("This organization is full. Ask your administrator to free a seat.")
        member_payload = {
            "id": str(uuid4()),
            "org_id": row["org_id"],
            "user_id": user_id,
            "email": signed_in_email,
            "role": row["role"],
            "invited_by": row.get("invited_by"),
        }
        inserted = client.table("org_members").insert(member_payload).execute()
        existing = inserted.data[0] if inserted.data else member_payload

    client.table("org_invitations").update({"accepted_at": _iso(_now())}).eq("id", row["id"]).execute()
    logger.info(f"Invitation {row['id']} accepted by user {user_id} for org {row['org_id']}")
    return existing


# ── Workspace data ───────────────────────────────────────────────────

def list_org_claims(org_id: str) -> list[dict]:
    """Claims saved into this workspace, same shape as /api/history/claims plus author."""
    client = get_supabase_client()
    rows = (
        client.table("user_claims")
        .select("id, user_id, claim_description, cost_breakdown_json, appeal_output_json, route_decision, created_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .execute()
    ).data or []
    email_by_user = {m["user_id"]: m.get("email") for m in list_members(org_id)}
    return [
        {
            "id": r["id"],
            "user_id": r.get("user_id"),
            "created_by_email": email_by_user.get(r.get("user_id")),
            "claim_description": r.get("claim_description"),
            "cost_breakdown": r.get("cost_breakdown_json"),
            "appeal_output": r.get("appeal_output_json"),
            "route_decision": r.get("route_decision"),
            "created_at": r.get("created_at"),
        }
        for r in rows
    ]


def list_org_policies(org_id: str) -> list[dict]:
    client = get_supabase_client()
    rows = (
        client.table("user_policies")
        .select("id, user_id, session_id, policy_profile_json, created_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .execute()
    ).data or []
    return [
        {
            "id": r["id"],
            "user_id": r.get("user_id"),
            "session_id": r.get("session_id"),
            "policy_profile": r.get("policy_profile_json"),
            "created_at": r.get("created_at"),
        }
        for r in rows
    ]


# ── Request context ──────────────────────────────────────────────────

def resolve_org_context(user_id: str, org_id: str | None) -> dict | None:
    """
    Turn an optional X-Org-Id header into {"org_id", "role"} for the request.

    Returns None (personal context) when the feature is disabled or no header was
    sent, so callers behave exactly as before. A header naming an organization
    the user does not belong to raises OrgNotFound. Any member (viewers included)
    gets a context; endpoints that write into the workspace apply
    `get_org_write_context`, which requires the member role.
    """
    if not orgs_enabled() or not org_id:
        return None
    membership = require_membership(org_id, user_id, minimum="viewer")
    return {"org_id": org_id, "role": membership.get("role")}
