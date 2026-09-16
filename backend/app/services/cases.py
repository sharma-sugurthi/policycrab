"""
Case management: a claim's journey through the appeal lifecycle, owned by a
team workspace (or a single user), with an assignee, status, priority, due
date and an activity log.

Scope: every call carries a `scope` — {"user_id", "org_id" | None, "role"} —
built from the request's workspace context. Personal cases (org_id NULL) are
visible only to their creator; workspace cases to every member. Viewers read,
members and above write, admins (or the creator) delete.

Free text (notes, comments) is PHI-scrubbed before storage, like claim
descriptions are. Inert unless CASES_ENABLED=true.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date, datetime, timezone
from uuid import uuid4

from app.config import settings
from app.models.case import CLOSED_STATUSES, OPEN_STATUSES, PRIORITIES, STATUSES
from app.security.presidio_scrubber import PHIScrubbingError, scrub_phi
from app.services import organizations as org_service
from app.services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

OUTCOME_TO_STATUS = {
    "won": "won", "partial": "partial", "lost": "lost", "withdrawn": "withdrawn", "pending": "awaiting_decision",
}
MAX_OPEN_CASES_PER_SCOPE = 500
DUE_SOON_DAYS = 7

_CASE_SELECT = ("id, org_id, claim_id, created_by, assignee_id, title, status, priority, due_date, amount_at_stake, "
                "reference, notes, created_at, updated_at, closed_at")
_CLAIM_SELECT = "id, user_id, org_id, claim_description, cost_breakdown_json, appeal_output_json, route_decision, created_at"


class CaseError(ValueError):
    """Bad request — HTTP 400."""


class CaseNotFound(LookupError):
    """Case or claim not visible in this scope — HTTP 404."""


class CasePermissionError(PermissionError):
    """Role too low for the action — HTTP 403."""


class CaseScrubError(RuntimeError):
    """PHI scrubber unavailable — HTTP 503."""


# ── Pure helpers ─────────────────────────────────────────────────────

def cases_enabled() -> bool:
    return bool(settings.cases_enabled)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_scope(user_id: str, org_ctx: dict | None) -> dict:
    """Personal scope when no workspace context; otherwise the workspace and the caller's role."""
    if org_ctx and org_ctx.get("org_id"):
        return {"user_id": str(user_id), "org_id": str(org_ctx["org_id"]), "role": org_ctx.get("role") or "viewer"}
    return {"user_id": str(user_id), "org_id": None, "role": "owner"}


def can_write(scope: dict) -> bool:
    return org_service.role_at_least(scope.get("role"), "member")


def can_delete(scope: dict, case: dict) -> bool:
    if str(case.get("created_by")) == scope["user_id"]:
        return True
    return bool(scope.get("org_id")) and org_service.role_at_least(scope.get("role"), "admin")


def is_open(status: str | None) -> bool:
    return status in OPEN_STATUSES


def _parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def scrub_text(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    try:
        clean, _ = scrub_phi(text)
    except PHIScrubbingError as exc:
        raise CaseScrubError("Could not safely process the text. Please try again shortly.") from exc
    return clean


def default_title(claim: dict) -> str:
    desc = " ".join(str(claim.get("claim_description") or "").split())
    if desc:
        return (desc[:117] + "…") if len(desc) > 120 else desc
    return f"Claim {str(claim.get('id'))[:8]}"


def claim_summary(claim: dict | None) -> dict | None:
    if not claim:
        return None
    appeal = claim.get("appeal_output_json") or {}
    cost = claim.get("cost_breakdown_json") or {}
    desc = " ".join(str(claim.get("claim_description") or "").split())
    return {
        "route_decision": claim.get("route_decision"),
        "appeal_recommendation": appeal.get("appeal_recommendation"),
        "success_score_band": appeal.get("success_score_band"),
        "appeal_deadline": appeal.get("appeal_deadline"),
        "triage_path": appeal.get("triage_path"),
        "patient_responsibility": cost.get("total_patient_responsibility"),
        "description_preview": (desc[:137] + "…") if len(desc) > 140 else desc,
        "evaluated_at": claim.get("created_at"),
    }


def compute_pipeline_summary(cases: list[dict], outcomes_by_claim: dict[str, dict], today: date | None = None) -> dict:
    """Counts, money and timing for a set of cases. Pure."""
    today = today or date.today()
    by_status: Counter = Counter()
    by_priority: Counter = Counter()
    per_assignee: Counter = Counter()
    overdue = due_soon = unassigned = 0
    at_stake = 0.0
    close_days: list[int] = []
    recovered = 0.0
    for c in cases:
        status = c.get("status") or "new"
        by_status[status] += 1
        if is_open(status):
            by_priority[c.get("priority") or "normal"] += 1
            due = _parse_date(c.get("due_date"))
            if due is not None:
                if due < today:
                    overdue += 1
                elif (due - today).days <= DUE_SOON_DAYS:
                    due_soon += 1
            if c.get("assignee_id"):
                per_assignee[str(c["assignee_id"])] += 1
            else:
                unassigned += 1
            try:
                at_stake += float(c.get("amount_at_stake") or 0)
            except (TypeError, ValueError):
                pass
        else:
            created, closed = c.get("created_at"), c.get("closed_at")
            try:
                if created and closed:
                    closed_dt = datetime.fromisoformat(str(closed).replace("Z", "+00:00"))
                    created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                    delta = closed_dt - created_dt
                    close_days.append(max(0, delta.days))
            except ValueError:
                pass
        outcome = outcomes_by_claim.get(str(c.get("claim_id")))
        if outcome:
            try:
                recovered += float(outcome.get("amount_recovered") or 0)
            except (TypeError, ValueError):
                pass
    won, partial, lost = by_status["won"], by_status["partial"], by_status["lost"]
    decided = won + partial + lost
    return {
        "total": len(cases),
        "open": sum(by_status[s] for s in OPEN_STATUSES),
        "closed": sum(by_status[s] for s in CLOSED_STATUSES),
        "by_status": {s: by_status[s] for s in STATUSES},
        "open_by_priority": {p: by_priority[p] for p in PRIORITIES},
        "overdue": overdue,
        "due_soon": due_soon,
        "due_soon_days": DUE_SOON_DAYS,
        "unassigned": unassigned,
        "amount_at_stake_open": round(at_stake, 2),
        "amount_recovered": round(recovered, 2),
        "decided": decided,
        "overturn_rate": round((won + partial) / decided, 3) if decided else None,
        "avg_days_to_close": round(sum(close_days) / len(close_days), 1) if close_days else None,
        "open_by_assignee": dict(per_assignee.most_common()),
        "as_of": today.isoformat(),
    }


# ── Queries ──────────────────────────────────────────────────────────

def _scoped(query, scope: dict):
    if scope.get("org_id"):
        return query.eq("org_id", scope["org_id"])
    return query.eq("created_by", scope["user_id"]).is_("org_id", "null")


def _claim_for(scope: dict, claim_id: str) -> dict:
    rows = get_supabase_client().table("user_claims").select(_CLAIM_SELECT).eq("id", claim_id).limit(1).execute().data or []
    claim = rows[0] if rows else None
    if claim is None:
        raise CaseNotFound("Claim not found.")
    if scope.get("org_id"):
        visible = str(claim.get("org_id") or "") == scope["org_id"]
    else:
        visible = str(claim.get("user_id")) == scope["user_id"] and not claim.get("org_id")
    if not visible:
        raise CaseNotFound("Claim not found in this workspace.")
    return claim


def _validate_assignee(scope: dict, assignee_id: str | None) -> None:
    if not assignee_id:
        return
    if scope.get("org_id"):
        membership = org_service.get_membership(scope["org_id"], assignee_id)
        if membership is None or not org_service.role_at_least(membership.get("role"), "member"):
            raise CaseError("Assignee must be a member of this workspace.")
    elif str(assignee_id) != scope["user_id"]:
        raise CaseError("Personal cases can only be assigned to yourself.")


def _event(case: dict, actor: dict | None, event_type: str, message: str | None = None, data: dict | None = None) -> dict:
    payload = {
        "id": str(uuid4()),
        "case_id": case["id"],
        "org_id": case.get("org_id"),
        "actor_id": (actor or {}).get("id"),
        "actor_email": (actor or {}).get("email"),
        "event_type": event_type,
        "message": message,
        "data": data or {},
    }
    result = get_supabase_client().table("case_events").insert(payload).execute()
    return result.data[0] if result.data else payload


def _enrich(rows: list[dict], scope: dict, today: date | None = None) -> list[dict]:
    today = today or date.today()
    client = get_supabase_client()
    claim_ids = sorted({str(r["claim_id"]) for r in rows if r.get("claim_id")})
    claims: dict[str, dict] = {}
    if claim_ids:
        for c in client.table("user_claims").select(_CLAIM_SELECT).in_("id", claim_ids).execute().data or []:
            claims[str(c["id"])] = c
    emails: dict[str, str | None] = {}
    if scope.get("org_id"):
        emails = {str(m["user_id"]): m.get("email") for m in org_service.list_members(scope["org_id"])}
    out = []
    for r in rows:
        item = dict(r)
        due = _parse_date(r.get("due_date"))
        item["is_open"] = is_open(r.get("status"))
        item["days_to_due"] = (due - today).days if due else None
        item["overdue"] = bool(due and item["is_open"] and due < today)
        item["assignee_email"] = emails.get(str(r.get("assignee_id"))) if r.get("assignee_id") else None
        item["created_by_email"] = emails.get(str(r.get("created_by")))
        item["claim"] = claim_summary(claims.get(str(r.get("claim_id"))))
        out.append(item)
    return out


def _sort_key(c: dict):
    due = _parse_date(c.get("due_date"))
    return (0 if is_open(c.get("status")) else 1, due is None, due or date.max, str(c.get("created_at") or ""))


def list_cases(scope: dict, *, status: str | None = None, assignee_id: str | None = None,
               include_closed: bool = True, limit: int = 200) -> list[dict]:
    query = _scoped(get_supabase_client().table("cases").select(_CASE_SELECT), scope)
    if status:
        query = query.eq("status", status)
    if assignee_id:
        query = query.eq("assignee_id", assignee_id)
    rows = query.limit(max(1, min(int(limit), 1000))).execute().data or []
    if not include_closed:
        rows = [r for r in rows if is_open(r.get("status"))]
    rows.sort(key=_sort_key)
    return _enrich(rows, scope)


def get_case(scope: dict, case_id: str) -> dict:
    query = _scoped(get_supabase_client().table("cases").select(_CASE_SELECT), scope)
    rows = query.eq("id", case_id).limit(1).execute().data or []
    if not rows:
        raise CaseNotFound("Case not found.")
    return rows[0]


def get_case_enriched(scope: dict, case_id: str) -> dict:
    return _enrich([get_case(scope, case_id)], scope)[0]


def list_events(scope: dict, case_id: str, limit: int = 100) -> list[dict]:
    get_case(scope, case_id)                                  # visibility check
    rows = (
        get_supabase_client().table("case_events")
        .select("id, case_id, event_type, actor_id, actor_email, message, data, created_at")
        .eq("case_id", case_id).order("created_at", desc=True).limit(max(1, min(int(limit), 500))).execute()
    ).data or []
    # Newest first regardless of how the client ordered (ties keep insertion order reversed).
    rows.reverse()
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows


# ── Mutations ────────────────────────────────────────────────────────

def create_case(scope: dict, actor: dict, claim_id: str, *, title: str | None = None, assignee_id: str | None = None,
                priority: str = "normal", due_date: date | None = None, amount_at_stake: float | None = None,
                reference: str | None = None, notes: str | None = None) -> dict:
    if not can_write(scope):
        raise CasePermissionError("Viewers cannot create cases.")
    claim = _claim_for(scope, claim_id)
    client = get_supabase_client()
    existing = client.table("cases").select("id, org_id, created_by").eq("claim_id", claim_id).limit(1).execute().data or []
    if existing:
        raise CaseError("A case already exists for this claim.")
    scoped_rows = _scoped(client.table("cases").select("id, status"), scope).execute().data or []
    open_count = sum(1 for r in scoped_rows if is_open(r.get("status")))
    if open_count >= MAX_OPEN_CASES_PER_SCOPE:
        raise CaseError(f"This workspace already has {MAX_OPEN_CASES_PER_SCOPE} open cases. Close some first.")
    _validate_assignee(scope, assignee_id)
    if priority not in PRIORITIES:
        raise CaseError(f"priority must be one of {', '.join(PRIORITIES)}")

    appeal = claim.get("appeal_output_json") or {}
    cost = claim.get("cost_breakdown_json") or {}
    if due_date is None:
        due_date = _parse_date(appeal.get("appeal_deadline"))
    if amount_at_stake is None:
        try:
            responsibility = cost.get("total_patient_responsibility")
            amount_at_stake = float(responsibility) if responsibility is not None else None
        except (TypeError, ValueError):
            amount_at_stake = None

    payload = {
        "id": str(uuid4()),
        "claim_id": str(claim_id),
        "created_by": scope["user_id"],
        "assignee_id": str(assignee_id) if assignee_id else None,
        "title": scrub_text(title) or default_title(claim),
        "status": "new",
        "priority": priority,
        "due_date": due_date.isoformat() if due_date else None,
        "amount_at_stake": amount_at_stake,
        "reference": (reference or "").strip()[:60] or None,
        "notes": scrub_text(notes),
    }
    if scope.get("org_id"):
        payload["org_id"] = scope["org_id"]
    result = client.table("cases").insert(payload).execute()
    case = result.data[0] if result.data else payload
    _event(case, actor, "created", data={"status": "new", "assignee_id": payload["assignee_id"]})
    logger.info(f"Case created {case['id']} for claim {claim_id} (org={scope.get('org_id') or 'personal'})")
    return _enrich([case], scope)[0]


def update_case(scope: dict, actor: dict, case_id: str, changes: dict) -> dict:
    if not can_write(scope):
        raise CasePermissionError("Viewers cannot edit cases.")
    case = get_case(scope, case_id)
    updates: dict = {}
    events: list[tuple[str, str | None, dict]] = []

    if "status" in changes and changes["status"] and changes["status"] != case.get("status"):
        new_status = changes["status"]
        if new_status not in STATUSES:
            raise CaseError(f"status must be one of {', '.join(STATUSES)}")
        updates["status"] = new_status
        updates["closed_at"] = _now().isoformat() if new_status in CLOSED_STATUSES else None
        events.append(("status_changed", None, {"from": case.get("status"), "to": new_status}))

    if changes.get("clear_assignee"):
        if case.get("assignee_id"):
            updates["assignee_id"] = None
            events.append(("assigned", None, {"from": case.get("assignee_id"), "to": None}))
    elif changes.get("assignee_id") and str(changes["assignee_id"]) != str(case.get("assignee_id") or ""):
        _validate_assignee(scope, changes["assignee_id"])
        updates["assignee_id"] = str(changes["assignee_id"])
        events.append(("assigned", None, {"from": case.get("assignee_id"), "to": updates["assignee_id"]}))

    if changes.get("priority") and changes["priority"] != case.get("priority"):
        if changes["priority"] not in PRIORITIES:
            raise CaseError(f"priority must be one of {', '.join(PRIORITIES)}")
        updates["priority"] = changes["priority"]
        events.append(("priority_changed", None, {"from": case.get("priority"), "to": changes["priority"]}))

    if changes.get("clear_due_date"):
        if case.get("due_date"):
            updates["due_date"] = None
            events.append(("due_date_changed", None, {"from": case.get("due_date"), "to": None}))
    elif changes.get("due_date") is not None:
        new_due = changes["due_date"].isoformat() if isinstance(changes["due_date"], date) else str(changes["due_date"])[:10]
        if new_due != (case.get("due_date") or None):
            updates["due_date"] = new_due
            events.append(("due_date_changed", None, {"from": case.get("due_date"), "to": new_due}))

    if changes.get("title"):
        clean = scrub_text(changes["title"])
        if clean and clean != case.get("title"):
            updates["title"] = clean[:140]
    if "reference" in changes and changes["reference"] is not None:
        updates["reference"] = str(changes["reference"]).strip()[:60] or None
    if changes.get("amount_at_stake") is not None:
        updates["amount_at_stake"] = float(changes["amount_at_stake"])
    if "notes" in changes and changes["notes"] is not None:
        clean = scrub_text(changes["notes"])
        if clean != case.get("notes"):
            updates["notes"] = clean
            events.append(("notes_updated", None, {}))

    if not updates:
        return _enrich([case], scope)[0]
    updates["updated_at"] = _now().isoformat()
    result = get_supabase_client().table("cases").update(updates).eq("id", case_id).execute()
    updated = {**case, **(result.data[0] if result.data else updates)}
    for event_type, message, data in events:
        _event(updated, actor, event_type, message, data)
    return _enrich([updated], scope)[0]


def add_comment(scope: dict, actor: dict, case_id: str, message: str) -> dict:
    if not can_write(scope):
        raise CasePermissionError("Viewers cannot comment on cases.")
    case = get_case(scope, case_id)
    clean = scrub_text(message)
    if not clean:
        raise CaseError("Comment is empty.")
    return _event(case, actor, "comment", clean)


def delete_case(scope: dict, case_id: str) -> bool:
    case = get_case(scope, case_id)
    if not can_delete(scope, case):
        raise CasePermissionError("Only workspace admins or the case creator can delete a case.")
    result = get_supabase_client().table("cases").delete().eq("id", case_id).execute()
    return bool(result.data)


def summarize(scope: dict, today: date | None = None) -> dict:
    client = get_supabase_client()
    cases = _scoped(client.table("cases").select(_CASE_SELECT), scope).limit(2000).execute().data or []
    outcomes: dict[str, dict] = {}
    claim_ids = sorted({str(c["claim_id"]) for c in cases if c.get("claim_id")})
    if claim_ids:
        outcome_rows = (client.table("appeal_outcomes").select("claim_id, outcome, amount_recovered")
                        .in_("claim_id", claim_ids).execute().data or [])
        for o in outcome_rows:
            outcomes[str(o["claim_id"])] = o
    summary = compute_pipeline_summary(cases, outcomes, today)
    if scope.get("org_id"):
        emails = {str(m["user_id"]): m.get("email") for m in org_service.list_members(scope["org_id"])}
        summary["open_by_assignee"] = {(emails.get(uid) or uid): n for uid, n in summary["open_by_assignee"].items()}
    summary["scope"] = {"type": "org" if scope.get("org_id") else "personal", "id": scope.get("org_id") or scope["user_id"]}
    return summary


def close_case_from_outcome(claim_id: str, outcome: str, actor: dict | None) -> dict | None:
    """When an appeal outcome is recorded, move the claim's case to the matching status. Never raises."""
    if not cases_enabled():
        return None
    try:
        new_status = OUTCOME_TO_STATUS.get((outcome or "").lower())
        if not new_status:
            return None
        client = get_supabase_client()
        rows = client.table("cases").select(_CASE_SELECT).eq("claim_id", claim_id).limit(1).execute().data or []
        if not rows:
            return None
        case = rows[0]
        if case.get("status") == new_status:
            return case
        updates = {"status": new_status, "updated_at": _now().isoformat(),
                   "closed_at": _now().isoformat() if new_status in CLOSED_STATUSES else None}
        result = client.table("cases").update(updates).eq("id", case["id"]).execute()
        updated = {**case, **(result.data[0] if result.data else updates)}
        _event(updated, actor, "outcome_recorded", data={"outcome": outcome, "from": case.get("status"), "to": new_status})
        return updated
    except Exception as exc:
        logger.warning(f"close_case_from_outcome skipped for claim {claim_id}: {exc}")
        return None
