"""
Audit trail API — read-only access to append-only audit events.
(/api/audit is the medical bill auditor; this lives at /api/audit-log.)
"""

from fastapi import APIRouter, Depends, Query

from app.api.admin_routes import require_admin
from app.api.auth import get_current_user
from app.api.org_context import translate_org_error, valid_uuid_or_404
from app.services import audit_trail
from app.services import organizations as org_service
from app.services.organizations import OrgError, OrgNotFound, OrgPermissionError

router = APIRouter(prefix="/api/audit-log", tags=["Audit Trail"])
admin_router = APIRouter(prefix="/api/admin", tags=["Admin Analytics"])

_DAYS = Query(30, ge=1, le=365)
_LIMIT = Query(100, ge=1, le=500)


@router.get("/me")
async def my_audit_log(days: int = _DAYS, limit: int = _LIMIT, user: dict = Depends(get_current_user)):
    """Actions performed by (or on) the signed-in user."""
    if not audit_trail.audit_enabled():
        return {"enabled": False, "events": []}
    return {"enabled": True, "events": audit_trail.fetch_audit_events(user_id=user["id"], days=days, limit=limit)}


@router.get("/org/{org_id}")
async def org_audit_log(org_id: str, days: int = _DAYS, limit: int = _LIMIT, user: dict = Depends(get_current_user)):
    """Workspace activity: invitations, role changes, removals, deletions. Owners and admins only."""
    org_id = valid_uuid_or_404(org_id)
    try:
        org_service.require_membership(org_id, user["id"], minimum="admin")
    except (OrgNotFound, OrgPermissionError, OrgError) as exc:
        raise translate_org_error(exc) from exc
    if not audit_trail.audit_enabled():
        return {"enabled": False, "events": []}
    return {"enabled": True, "events": audit_trail.fetch_audit_events(org_id=org_id, days=days, limit=limit)}


@admin_router.get("/audit-log")
async def platform_audit_log(
    days: int = _DAYS,
    limit: int = Query(200, ge=1, le=1000),
    action: str | None = Query(None, max_length=60, description="Optional action prefix filter, e.g. 'org.' or 'admin.'"),
    user: dict = Depends(require_admin),
):
    """Platform-wide audit trail (admin only)."""
    if not audit_trail.audit_enabled():
        return {"enabled": False, "events": []}
    return {"enabled": True, "events": audit_trail.fetch_global_audit_events(days=days, limit=limit, action_prefix=action)}
