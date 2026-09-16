"""
API keys: programmatic access with explicit route scopes.

A key runs as its owner (the user who created it) and, when bound to a
workspace, inside that workspace. The backend maps every route to the scope it
requires (ROUTE_SCOPES); anything unlisted — workspace management, key
management, admin, chat — is never callable with a key. Only the SHA-256 of a
key is stored; the raw key is returned exactly once at creation.

Inert unless API_KEYS_ENABLED=true.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from time import monotonic
from uuid import uuid4

from app.config import settings
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

KEY_PREFIXES = {"live": "pc_live_", "test": "pc_test_"}
PREFIX_DISPLAY_CHARS = 16
MAX_KEYS_PER_OWNER = 20
RESOLVE_CACHE_TTL_SECONDS = 60
LAST_USED_TOUCH_SECONDS = 300

SCOPE_DESCRIPTIONS: dict[str, str] = {
    "claims:evaluate": "Run the claim evaluation pipeline (cost calculation, triage, appeal drafting).",
    "appeals:draft": "Draft escalated appeals, revise letters in Studio and compile dossiers.",
    "policies:upload": "Upload SBC/EOB policy text or PDFs for extraction and indexing.",
    "eob:parse": "Parse an Explanation of Benefits into structured fields.",
    "bills:audit": "Audit itemised medical bills and generate dispute letters.",
    "history:read": "Read saved policies, claims, documents and bill audits.",
    "tasks:read": "Poll background task status for async evaluations and uploads.",
    "outcomes:read": "Read recorded appeal outcomes and calibration.",
    "outcomes:write": "Record appeal outcomes.",
    "usage:read": "Read usage summaries.",
    "providers:read": "Provider search and network-status lookups.",
    "carriers:read": "Carrier routing intelligence.",
    "deadlines:read": "Read appeal deadlines.",
    "deadlines:write": "Create, update and delete appeal deadlines; generate breach letters.",
}
ALL_SCOPES = tuple(SCOPE_DESCRIPTIONS)

# (method, route template or prefix ending in '*', scope). First match wins.
ROUTE_SCOPES: tuple[tuple[str, str, str], ...] = (
    ("POST", "/api/claim/evaluate", "claims:evaluate"),
    ("POST", "/api/claim/evaluate/async", "claims:evaluate"),
    ("POST", "/api/claim/draft-appeal", "appeals:draft"),
    ("POST", "/studio/revise", "appeals:draft"),
    ("POST", "/studio/dossier", "appeals:draft"),
    ("POST", "/api/policy/upload*", "policies:upload"),
    ("POST", "/api/eob/parse", "eob:parse"),
    ("POST", "/api/audit/scan", "bills:audit"),
    ("POST", "/api/audit/upload", "bills:audit"),
    ("POST", "/api/audit/dispute-letter", "bills:audit"),
    ("GET", "/api/history/*", "history:read"),
    ("GET", "/api/orgs/{org_id}/claims", "history:read"),
    ("GET", "/api/orgs/{org_id}/policies", "history:read"),
    ("GET", "/api/tasks/*", "tasks:read"),
    ("GET", "/api/outcomes*", "outcomes:read"),
    ("POST", "/api/outcomes", "outcomes:write"),
    ("GET", "/api/usage/*", "usage:read"),
    ("GET", "/api/providers/*", "providers:read"),
    ("POST", "/api/providers/*", "providers:read"),
    ("GET", "/api/carrier/*", "carriers:read"),
    ("POST", "/api/carrier/*", "carriers:read"),
    ("GET", "/api/deadlines*", "deadlines:read"),
    ("POST", "/api/deadlines*", "deadlines:write"),
    ("PATCH", "/api/deadlines*", "deadlines:write"),
    ("DELETE", "/api/deadlines*", "deadlines:write"),
)


class ApiKeyError(ValueError):
    """Bad request — maps to HTTP 400."""


# ── Pure helpers ─────────────────────────────────────────────────────

def api_keys_enabled() -> bool:
    return bool(settings.api_keys_enabled)


def looks_like_api_key(token: str | None) -> bool:
    return bool(token) and any(token.startswith(p) for p in KEY_PREFIXES.values())


def generate_api_key(environment: str = "live") -> str:
    return KEY_PREFIXES.get(environment, KEY_PREFIXES["live"]) + secrets.token_urlsafe(32)


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()


def key_prefix(raw: str) -> str:
    return raw[:PREFIX_DISPLAY_CHARS]


def required_scope(method: str, route_template: str | None) -> str | None:
    """Scope a key needs for this route, or None when the route is not key-callable."""
    if not route_template:
        return None
    method = (method or "").upper()
    for m, pattern, scope in ROUTE_SCOPES:
        if m != method:
            continue
        if pattern.endswith("*"):
            if route_template.startswith(pattern[:-1]):
                return scope
        elif route_template == pattern:
            return scope
    return None


def validate_scopes(scopes: list[str]) -> list[str]:
    unknown = sorted(set(scopes) - set(ALL_SCOPES))
    if unknown:
        raise ApiKeyError(f"Unknown scope(s): {', '.join(unknown)}")
    return sorted(set(scopes))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def key_status(row: dict, now: datetime | None = None) -> str:
    """'ok' | 'revoked' | 'expired'."""
    now = now or _now()
    if row.get("revoked_at"):
        return "revoked"
    expires = _parse_ts(row.get("expires_at"))
    if expires is not None and expires <= now:
        return "expired"
    return "ok"


def public_row(row: dict) -> dict:
    """Strip the hash; add `active`."""
    out = {k: v for k, v in row.items() if k != "key_hash"}
    out["scopes"] = list(row.get("scopes") or [])
    out["active"] = key_status(row) == "ok"
    return out


# ── Resolution cache (per process, short TTL) ────────────────────────

_cache: dict[str, tuple[float, dict | None]] = {}


def invalidate_cache(key_hash: str | None = None) -> None:
    if key_hash is None:
        _cache.clear()
    else:
        _cache.pop(key_hash, None)


def _cache_get(key_hash: str):
    entry = _cache.get(key_hash)
    if not entry:
        return None, False
    stored_at, row = entry
    if monotonic() - stored_at > RESOLVE_CACHE_TTL_SECONDS:
        _cache.pop(key_hash, None)
        return None, False
    return row, True


def _cache_put(key_hash: str, row: dict | None) -> None:
    _cache[key_hash] = (monotonic(), row)


# ── Persistence ──────────────────────────────────────────────────────

_SELECT = ("id, user_id, owner_email, org_id, name, key_prefix, scopes, environment, "
           "last_used_at, expires_at, revoked_at, created_at")


def count_active_keys(*, user_id: str | None = None, org_id: str | None = None) -> int:
    query = get_supabase_client().table("api_keys").select("id, revoked_at, expires_at")
    query = query.eq("org_id", org_id) if org_id else query.eq("user_id", user_id).is_("org_id", "null")
    rows = query.execute().data or []
    return sum(1 for r in rows if key_status(r) == "ok")


def create_api_key(
    owner_id: str,
    owner_email: str | None,
    name: str,
    scopes: list[str],
    *,
    org_id: str | None = None,
    environment: str = "live",
    expires_in_days: int | None = None,
) -> tuple[dict, str]:
    """Create a key; returns (public_row, raw_key). The raw key is never stored."""
    scopes = validate_scopes(scopes)
    if environment not in KEY_PREFIXES:
        raise ApiKeyError("environment must be 'live' or 'test'")
    if count_active_keys(user_id=owner_id, org_id=org_id) >= MAX_KEYS_PER_OWNER:
        raise ApiKeyError(f"Limit of {MAX_KEYS_PER_OWNER} active keys reached. Revoke one first.")

    raw = generate_api_key(environment)
    payload = {
        "id": str(uuid4()),
        "user_id": str(owner_id),
        "owner_email": (owner_email or "").lower() or None,
        "name": name,
        "key_prefix": key_prefix(raw),
        "key_hash": hash_api_key(raw),
        "scopes": scopes,
        "environment": environment,
        "expires_at": (_now() + timedelta(days=int(expires_in_days))).isoformat() if expires_in_days else None,
    }
    if org_id:
        payload["org_id"] = str(org_id)
    result = get_supabase_client().table("api_keys").insert(payload).execute()
    row = result.data[0] if result.data else payload
    logger.info(f"API key created: {row.get('id')} ({environment}, org={org_id or 'personal'}) by {owner_id}")
    return public_row(row), raw


def list_api_keys(*, user_id: str | None = None, org_id: str | None = None) -> list[dict]:
    query = get_supabase_client().table("api_keys").select(_SELECT)
    query = query.eq("org_id", org_id) if org_id else query.eq("user_id", user_id).is_("org_id", "null")
    rows = query.order("created_at", desc=True).execute().data or []
    return [public_row(r) for r in rows]


def revoke_api_key(key_id: str, *, user_id: str | None = None, org_id: str | None = None) -> dict | None:
    """Revoke a key scoped to its owner (personal) or workspace (org). Returns the row or None."""
    client = get_supabase_client()
    lookup = client.table("api_keys").select(_SELECT + ", key_hash").eq("id", key_id)
    lookup = lookup.eq("org_id", org_id) if org_id else lookup.eq("user_id", user_id).is_("org_id", "null")
    rows = lookup.limit(1).execute().data or []
    if not rows:
        return None
    row = rows[0]
    if not row.get("revoked_at"):
        updated = client.table("api_keys").update({"revoked_at": _now().isoformat()}).eq("id", key_id).execute()
        if updated.data:
            row = {**row, **updated.data[0]}
    invalidate_cache(row.get("key_hash"))
    logger.info(f"API key revoked: {key_id}")
    return public_row(row)


def resolve_api_key(raw: str) -> tuple[str, dict | None]:
    """
    Look a raw key up by hash. Returns (status, row) where status is
    'ok' | 'revoked' | 'expired' | 'unknown'. Cached for RESOLVE_CACHE_TTL_SECONDS.
    """
    if not looks_like_api_key(raw):
        return "unknown", None
    digest = hash_api_key(raw)
    row, hit = _cache_get(digest)
    if not hit:
        try:
            rows = (
                get_supabase_client().table("api_keys").select(_SELECT + ", key_hash")
                .eq("key_hash", digest).limit(1).execute()
            ).data or []
        except Exception as exc:
            logger.error(f"API key lookup failed: {exc}")
            return "unknown", None
        row = rows[0] if rows else None
        _cache_put(digest, row)
    if row is None:
        return "unknown", None
    return key_status(row), row


def touch_last_used(row: dict) -> None:
    """Update last_used_at at most every LAST_USED_TOUCH_SECONDS. Never raises."""
    try:
        last = _parse_ts(row.get("last_used_at"))
        now = _now()
        if last is not None and (now - last).total_seconds() < LAST_USED_TOUCH_SECONDS:
            return
        get_supabase_client().table("api_keys").update({"last_used_at": now.isoformat()}).eq("id", row["id"]).execute()
        row["last_used_at"] = now.isoformat()
        _cache_put(row["key_hash"], row) if row.get("key_hash") else None
    except Exception as exc:
        logger.debug(f"api key last_used update skipped: {exc}")


def build_auth_user(row: dict, membership: dict | None) -> dict:
    """The `user` dict routes see when a request is authenticated with a key."""
    return {
        "id": str(row["user_id"]),
        "email": row.get("owner_email"),
        "auth_method": "api_key",
        "api_key": {
            "id": str(row["id"]),
            "name": row.get("name"),
            "prefix": row.get("key_prefix"),
            "environment": row.get("environment", "live"),
            "scopes": list(row.get("scopes") or []),
            "org_id": str(row["org_id"]) if row.get("org_id") else None,
            "role": (membership or {}).get("role"),
        },
    }
