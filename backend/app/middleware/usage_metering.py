"""
Usage metering middleware.

Maps successful (2xx) requests on billable routes to usage events and records
them off the response path. Identity comes from `request.state.auth_user`,
which `get_current_user` sets after validating the bearer token — the
middleware never re-validates tokens itself. Workspace attribution prefers the
membership already verified by `get_org_context` (`request.state.org_ctx`); a
bare X-Org-Id header is only honoured after its own membership check.

Inert unless USAGE_METERING_ENABLED=true.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services import usage as usage_service

logger = logging.getLogger(__name__)

# (method, route template) → event type. Templates are FastAPI path formats.
BILLABLE_ROUTES: dict[tuple[str, str], str] = {
    ("POST", "/api/claim/evaluate"): "claim.evaluate",
    ("POST", "/api/claim/evaluate/async"): "claim.evaluate",
    ("POST", "/api/claim/draft-appeal"): "appeal.draft",
    ("POST", "/api/policy/upload"): "policy.upload",
    ("POST", "/api/policy/upload-pdf"): "policy.upload",
    ("POST", "/api/policy/upload-pdf/async"): "policy.upload",
    ("POST", "/api/policy/upload/async"): "policy.upload",
    ("POST", "/studio/revise"): "appeal.revise",
    ("POST", "/studio/dossier"): "dossier.compile",
    ("POST", "/api/eob/parse"): "eob.parse",
    ("POST", "/api/audit/scan"): "bill.audit",
    ("POST", "/api/audit/upload"): "bill.audit",
    ("POST", "/api/audit/dispute-letter"): "bill.dispute_letter",
    ("POST", "/api/chat/message"): "chat.message",
    ("POST", "/api/deadlines/{deadline_id}/breach-letter"): "deadline.breach_letter",
    ("POST", "/api/providers/search"): "provider.search",
    ("POST", "/api/providers/network-status"): "provider.network_status",
    ("POST", "/api/carrier/routing"): "carrier.routing",
}

# Fallback when the matched route object is unavailable: concrete path → template.
_PARAM_ROUTES = [
    (re.compile(r"^/api/deadlines/[^/]+/breach-letter$"), "/api/deadlines/{deadline_id}/breach-letter"),
]

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def resolve_event_type(method: str, template_path: str | None, raw_path: str) -> tuple[str | None, str]:
    """Return (event_type or None, route template used)."""
    method = (method or "").upper()
    candidates = []
    if template_path:
        candidates.append(template_path)
    for pattern, template in _PARAM_ROUTES:
        if pattern.match(raw_path or ""):
            candidates.append(template)
    candidates.append(raw_path or "")
    for candidate in candidates:
        event = BILLABLE_ROUTES.get((method, candidate))
        if event:
            return event, candidate
    return None, template_path or raw_path or ""


def _attribute_org(user_id: str, org_ctx: dict | None, header_org_id: str | None) -> str | None:
    """Trust a verified org context; otherwise verify a bare header ourselves."""
    if org_ctx and org_ctx.get("org_id"):
        return str(org_ctx["org_id"])
    if not header_org_id or not _UUID_RE.match(header_org_id):
        return None
    try:
        from app.services import organizations as org_service
        if not org_service.orgs_enabled():
            return None
        membership = org_service.get_membership(header_org_id, user_id)
        return header_org_id if membership else None
    except Exception as exc:
        logger.debug(f"usage metering: org attribution skipped: {exc}")
        return None


def record_request_usage(
    *,
    user_id: str,
    event_type: str,
    route: str,
    status_code: int,
    org_ctx: dict | None,
    header_org_id: str | None,
    is_async: bool,
) -> dict | None:
    """Synchronous worker; runs in a thread via `_schedule`."""
    org_id = _attribute_org(user_id, org_ctx, header_org_id)
    return usage_service.record_usage(
        user_id,
        event_type,
        org_id=org_id,
        route=route,
        metadata={"status": int(status_code), "async": bool(is_async)},
    )


def _schedule(fn: Callable[[], object]) -> None:
    """Run `fn` off the event loop. Tests replace this with a synchronous call."""
    try:
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, fn)
        fut.add_done_callback(lambda f: f.exception() and logger.debug(f"usage metering task: {f.exception()}"))
    except RuntimeError:
        fn()


class UsageMeteringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if not usage_service.metering_enabled():
            return response
        if not 200 <= response.status_code < 300:
            return response

        route = request.scope.get("route")
        template = getattr(route, "path", None)
        event_type, matched = resolve_event_type(request.method, template, request.url.path)
        if not event_type:
            return response

        user = getattr(request.state, "auth_user", None)
        user_id = (user or {}).get("id") if isinstance(user, dict) else None
        if not user_id:
            return response

        org_ctx = getattr(request.state, "org_ctx", None)
        header_org_id = request.headers.get("x-org-id")
        status_code = response.status_code
        _schedule(lambda: record_request_usage(
            user_id=str(user_id), event_type=event_type, route=matched, status_code=status_code,
            org_ctx=org_ctx if isinstance(org_ctx, dict) else None, header_org_id=header_org_id,
            is_async=matched.endswith("/async"),
        ))
        return response
