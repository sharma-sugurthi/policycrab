"""
Append-only audit trail: who did what, when, from where (hashed), with what result.

Complements the EASF stdout audit log (which Cloud Logging keeps) with a
queryable per-user / per-workspace record that compliance reviewers can pull
from the product itself. Rows never contain PHI or raw IP addresses.
Recording never raises. Inert unless AUDIT_TRAIL_ENABLED=true.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from app.config import settings
from app.services.supabase_client import get_supabase_client
from app.services.usage import clean_metadata

logger = logging.getLogger(__name__)

ACTOR_TYPES = ("user", "system", "agent")


def audit_enabled() -> bool:
    return bool(settings.audit_trail_enabled)


def _client_ip(request) -> str | None:
    if request is None:
        return None
    try:
        headers = request.headers
        for header in ("cf-connecting-ip", "x-forwarded-for"):
            value = headers.get(header, "")
            if value:
                return value.split(",")[0].strip()
        return request.client.host if request.client else None
    except Exception:
        return None


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return sha256(ip.encode("utf-8")).hexdigest()[:16]


def record_audit(
    action: str,
    *,
    user_id: str | None = None,
    org_id: str | None = None,
    actor_type: str = "user",
    resource_type: str | None = None,
    resource_id: str | None = None,
    outcome: str = "success",
    reason: str | None = None,
    metadata: dict | None = None,
    request=None,
) -> dict | None:
    """Append one audit row. Returns the row, or None when disabled or on failure."""
    if not audit_enabled() or not action:
        return None
    payload = {
        "id": str(uuid4()),
        "user_id": str(user_id) if user_id else None,
        "org_id": str(org_id) if org_id else None,
        "actor_type": actor_type if actor_type in ACTOR_TYPES else "user",
        "action": action[:120],
        "resource_type": resource_type[:60] if resource_type else None,
        "resource_id": str(resource_id)[:120] if resource_id else None,
        "outcome": (outcome or "success")[:40],
        "reason": reason[:300] if reason else None,
        "ip_hash": hash_ip(_client_ip(request)),
        "user_agent": (request.headers.get("user-agent", "")[:200] or None) if request is not None else None,
        "metadata": clean_metadata(metadata),
    }
    try:
        result = get_supabase_client().table("audit_events").insert(payload).execute()
        return result.data[0] if result.data else payload
    except Exception as exc:  # the audit trail must never break the product
        logger.warning(f"audit_events insert failed ({action}): {exc}")
        return None


def fetch_audit_events(
    *, user_id: str | None = None, org_id: str | None = None, days: int = 30, limit: int = 100
) -> list[dict]:
    if not user_id and not org_id:
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).isoformat()
    query = (
        get_supabase_client()
        .table("audit_events")
        .select("id, user_id, org_id, actor_type, action, resource_type, resource_id, outcome, reason, metadata, created_at")
        .gte("created_at", since)
    )
    query = query.eq("org_id", org_id) if org_id else query.eq("user_id", user_id)
    return query.order("created_at", desc=True).limit(max(1, min(int(limit), 500))).execute().data or []


def fetch_global_audit_events(*, days: int = 30, limit: int = 200, action_prefix: str | None = None) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).isoformat()
    query = (
        get_supabase_client()
        .table("audit_events")
        .select("id, user_id, org_id, actor_type, action, resource_type, resource_id, outcome, reason, metadata, created_at")
        .gte("created_at", since)
    )
    rows = query.order("created_at", desc=True).limit(max(1, min(int(limit), 1000))).execute().data or []
    if action_prefix:
        rows = [r for r in rows if str(r.get("action", "")).startswith(action_prefix)]
    return rows
