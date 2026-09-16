"""
Case management API. The workspace comes from the X-Org-Id header via
get_org_context (or a workspace-bound API key); without it, cases are personal.
Every endpoint answers 404 while CASES_ENABLED is false.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.auth import get_current_user
from app.api.org_context import get_org_context, valid_uuid_or_404
from app.models.case import CaseComment, CaseCreate, CaseUpdate
from app.security.rate_limit import rate_limit_user
from app.services import cases as case_service
from app.services.audit_trail import record_audit
from app.services.cases import CaseError, CaseNotFound, CasePermissionError, CaseScrubError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cases", tags=["Cases"])
CASE_WRITE_RATE_LIMIT = rate_limit_user("cases:write", max_requests=120, window_seconds=3600)

_ERRORS = (CaseNotFound, CasePermissionError, CaseError, CaseScrubError)


def require_cases_enabled(user: dict = Depends(get_current_user)) -> None:
    if not case_service.cases_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case management is not enabled on this deployment.")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, CaseNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, CasePermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, CaseScrubError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def _scope(user: dict, org_ctx: dict | None) -> dict:
    return case_service.make_scope(user["id"], org_ctx)


def _actor(user: dict) -> dict:
    return {"id": user.get("id"), "email": user.get("email")}


@router.get("")
async def list_cases(
    status_filter: str | None = Query(None, alias="status"),
    assignee_id: str | None = Query(None),
    include_closed: bool = Query(True),
    limit: int = Query(200, ge=1, le=1000),
    user: dict = Depends(get_current_user),
    org_ctx: dict | None = Depends(get_org_context),
    _flag: None = Depends(require_cases_enabled),
):
    scope = _scope(user, org_ctx)
    if assignee_id == "me":
        assignee_id = user["id"]
    return {
        "scope": {"type": "org" if scope["org_id"] else "personal", "id": scope["org_id"] or user["id"],
                  "role": scope["role"]},
        "cases": case_service.list_cases(scope, status=status_filter, assignee_id=assignee_id,
                                         include_closed=include_closed, limit=limit),
    }


@router.get("/summary")
async def pipeline_summary(
    user: dict = Depends(get_current_user),
    org_ctx: dict | None = Depends(get_org_context),
    _flag: None = Depends(require_cases_enabled),
):
    return case_service.summarize(_scope(user, org_ctx))


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_case(
    body: CaseCreate,
    request: Request,
    user: dict = Depends(get_current_user),
    org_ctx: dict | None = Depends(get_org_context),
    _flag: None = Depends(require_cases_enabled),
    _rl: None = Depends(CASE_WRITE_RATE_LIMIT),
):
    scope = _scope(user, org_ctx)
    try:
        case = case_service.create_case(
            scope, _actor(user), body.claim_id, title=body.title, assignee_id=body.assignee_id, priority=body.priority,
            due_date=body.due_date, amount_at_stake=body.amount_at_stake, reference=body.reference, notes=body.notes,
        )
    except _ERRORS as exc:
        raise _http(exc) from exc
    record_audit("case.created", user_id=user["id"], org_id=scope["org_id"], resource_type="case", resource_id=case["id"],
                 metadata={"claim_id": body.claim_id, "assignee_id": body.assignee_id}, request=request)
    return case


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    user: dict = Depends(get_current_user),
    org_ctx: dict | None = Depends(get_org_context),
    _flag: None = Depends(require_cases_enabled),
):
    case_id = valid_uuid_or_404(case_id, "Case")
    try:
        return case_service.get_case_enriched(_scope(user, org_ctx), case_id)
    except _ERRORS as exc:
        raise _http(exc) from exc


@router.patch("/{case_id}")
async def update_case(
    case_id: str,
    body: CaseUpdate,
    request: Request,
    user: dict = Depends(get_current_user),
    org_ctx: dict | None = Depends(get_org_context),
    _flag: None = Depends(require_cases_enabled),
    _rl: None = Depends(CASE_WRITE_RATE_LIMIT),
):
    case_id = valid_uuid_or_404(case_id, "Case")
    scope = _scope(user, org_ctx)
    changes = body.model_dump(exclude_unset=True)
    try:
        case = case_service.update_case(scope, _actor(user), case_id, changes)
    except _ERRORS as exc:
        raise _http(exc) from exc
    record_audit("case.updated", user_id=user["id"], org_id=scope["org_id"], resource_type="case", resource_id=case_id,
                 metadata={"fields": ",".join(sorted(changes))}, request=request)
    return case


@router.post("/{case_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    case_id: str,
    body: CaseComment,
    user: dict = Depends(get_current_user),
    org_ctx: dict | None = Depends(get_org_context),
    _flag: None = Depends(require_cases_enabled),
    _rl: None = Depends(CASE_WRITE_RATE_LIMIT),
):
    case_id = valid_uuid_or_404(case_id, "Case")
    try:
        return case_service.add_comment(_scope(user, org_ctx), _actor(user), case_id, body.message)
    except _ERRORS as exc:
        raise _http(exc) from exc


@router.get("/{case_id}/events")
async def list_events(
    case_id: str,
    limit: int = Query(100, ge=1, le=500),
    user: dict = Depends(get_current_user),
    org_ctx: dict | None = Depends(get_org_context),
    _flag: None = Depends(require_cases_enabled),
):
    case_id = valid_uuid_or_404(case_id, "Case")
    try:
        return {"events": case_service.list_events(_scope(user, org_ctx), case_id, limit)}
    except _ERRORS as exc:
        raise _http(exc) from exc


@router.delete("/{case_id}")
async def delete_case(
    case_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
    org_ctx: dict | None = Depends(get_org_context),
    _flag: None = Depends(require_cases_enabled),
):
    case_id = valid_uuid_or_404(case_id, "Case")
    scope = _scope(user, org_ctx)
    try:
        deleted = case_service.delete_case(scope, case_id)
    except _ERRORS as exc:
        raise _http(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Case not found.")
    record_audit("case.deleted", user_id=user["id"], org_id=scope["org_id"], resource_type="case", resource_id=case_id,
                 request=request)
    return {"success": True, "deleted_id": case_id}
