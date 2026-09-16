"""
Usage metering: one row per billable action, attributed to a user and, when a
team workspace is active, to that organization.

Provider-agnostic on purpose — this table is the source of truth a Dodo/Stripe/
Paddle adapter turns into invoice line items later. Recording never raises and
never blocks a request: the middleware schedules it off the response path.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.config import settings
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

EVENT_TYPES = (
    "claim.evaluate",
    "appeal.draft",
    "appeal.revise",
    "dossier.compile",
    "policy.upload",
    "eob.parse",
    "bill.audit",
    "bill.dispute_letter",
    "chat.message",
    "deadline.breach_letter",
    "provider.search",
    "provider.network_status",
    "carrier.routing",
)

_META_MAX_KEYS = 20
_META_MAX_STR = 200
_SCALARS = (str, int, float, bool, type(None))


def metering_enabled() -> bool:
    return bool(settings.usage_metering_enabled)


def clean_metadata(meta: dict | None) -> dict:
    """Keep only small scalar values — never free text that could carry PHI."""
    if not isinstance(meta, dict):
        return {}
    out: dict = {}
    for key, value in meta.items():
        if len(out) >= _META_MAX_KEYS:
            break
        if not isinstance(key, str) or not isinstance(value, _SCALARS):
            continue
        if isinstance(value, str):
            value = value[:_META_MAX_STR]
        out[key[:60]] = value
    return out


def record_usage(
    user_id: str | None,
    event_type: str,
    *,
    org_id: str | None = None,
    quantity: int = 1,
    units: str = "count",
    resource_id: str | None = None,
    route: str | None = None,
    metadata: dict | None = None,
) -> dict | None:
    """Insert one usage row. Returns the row, or None when disabled or on any failure."""
    if not metering_enabled() or not user_id or not event_type:
        return None
    payload = {
        "id": str(uuid4()),
        "user_id": str(user_id),
        "event_type": event_type,
        "quantity": max(1, int(quantity or 1)),
        "units": units or "count",
        "resource_id": str(resource_id)[:120] if resource_id else None,
        "route": route[:200] if route else None,
        "metadata": clean_metadata(metadata),
    }
    if org_id:
        payload["org_id"] = str(org_id)
    try:
        result = get_supabase_client().table("usage_events").insert(payload).execute()
        return result.data[0] if result.data else payload
    except Exception as exc:  # metering must never break the product
        logger.warning(f"usage_events insert failed ({event_type}): {exc}")
        return None


# ── Aggregation (pure) ───────────────────────────────────────────────

def _day(value) -> str | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).astimezone(timezone.utc).date().isoformat()
    except ValueError:
        return None


def aggregate_usage(rows: list[dict], days: int, until: datetime | None = None) -> dict:
    """Totals by event type and by day for a window ending at `until` (now)."""
    until = until or datetime.now(timezone.utc)
    since = until - timedelta(days=max(1, int(days)))
    by_type: Counter = Counter()
    by_day: dict[str, int] = defaultdict(int)
    by_type_day: dict[str, Counter] = defaultdict(Counter)
    total = 0
    for row in rows or []:
        qty = int(row.get("quantity") or 1)
        etype = row.get("event_type") or "unknown"
        day = _day(row.get("created_at"))
        total += qty
        by_type[etype] += qty
        if day:
            by_day[day] += qty
            by_type_day[etype][day] += qty
    return {
        "days": int(days),
        "since": since.isoformat(),
        "until": until.isoformat(),
        "total": total,
        "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "by_day": [{"date": d, "count": by_day[d]} for d in sorted(by_day)],
        "event_types": sorted(by_type),
    }


# ── Queries ──────────────────────────────────────────────────────────

def _window_start(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).isoformat()


def fetch_usage(*, user_id: str | None = None, org_id: str | None = None, days: int = 30) -> list[dict]:
    if not user_id and not org_id:
        return []
    query = (
        get_supabase_client()
        .table("usage_events")
        .select("id, user_id, org_id, event_type, quantity, units, resource_id, route, created_at")
        .gte("created_at", _window_start(days))
    )
    if org_id:
        query = query.eq("org_id", org_id)
    else:
        query = query.eq("user_id", user_id)
    return query.order("created_at", desc=True).limit(5000).execute().data or []


def summarize_user_usage(user_id: str, days: int = 30) -> dict:
    out = aggregate_usage(fetch_usage(user_id=user_id, days=days), days)
    out["scope"] = {"type": "user", "id": user_id}
    return out


def summarize_org_usage(org_id: str, days: int = 30) -> dict:
    rows = fetch_usage(org_id=org_id, days=days)
    out = aggregate_usage(rows, days)
    per_user: dict[str, int] = defaultdict(int)
    for r in rows:
        per_user[str(r.get("user_id"))] += int(r.get("quantity") or 1)
    out["by_user"] = dict(sorted(per_user.items(), key=lambda kv: -kv[1]))
    out["scope"] = {"type": "org", "id": org_id}
    return out


def summarize_global_usage(days: int = 30, group: str = "org") -> dict:
    """Platform-wide rollup for admins, grouped by organization or by user."""
    rows = (
        get_supabase_client()
        .table("usage_events")
        .select("user_id, org_id, event_type, quantity, created_at")
        .gte("created_at", _window_start(days))
        .limit(20000)
        .execute()
    ).data or []
    key = "org_id" if group == "org" else "user_id"
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        grouped[str(r.get(key) or ("personal" if key == "org_id" else "unknown"))].append(r)
    out = aggregate_usage(rows, days)
    out["group_by"] = "org" if key == "org_id" else "user"
    out["groups"] = sorted(
        (
            {"key": k, "total": sum(int(r.get("quantity") or 1) for r in v),
             "by_type": dict(Counter(r.get("event_type") or "unknown" for r in v))}
            for k, v in grouped.items()
        ),
        key=lambda g: -g["total"],
    )
    return out
