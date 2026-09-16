"""
Request-scoped organization context.

`get_org_context` reads the optional X-Org-Id header and resolves it to the
caller's membership. It is attached to the claim/policy save endpoints as an
optional dependency: with no header (or ORGS_ENABLED=false) it returns None and
those endpoints behave exactly as they always have.
"""

from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status

from app.api.auth import get_current_user
from app.services import organizations as org_service
from app.services.organizations import OrgError, OrgNotFound, OrgPermissionError


def is_uuid(value: str | None) -> bool:
    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def valid_uuid_or_404(value: str, what: str = "Organization") -> str:
    if not is_uuid(value):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found.")
    return str(value)


def require_orgs_enabled() -> None:
    if not org_service.orgs_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizations are not enabled on this deployment.",
        )


def translate_org_error(exc: Exception) -> HTTPException:
    if isinstance(exc, OrgNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, OrgPermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, OrgError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Organization request failed.")


def get_org_context(
    user: dict = Depends(get_current_user),
    x_org_id: str | None = Header(default=None, alias="X-Org-Id"),
    request: Request = None,
) -> dict | None:
    """{"org_id", "role"} for the active workspace, or None for personal context."""
    key = user.get("api_key") if isinstance(user, dict) else None
    if key and key.get("org_id"):
        # A workspace-bound key always acts inside its workspace (membership verified at auth time).
        if x_org_id and x_org_id != key["org_id"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="X-Org-Id does not match the workspace this API key belongs to.")
        ctx = {"org_id": key["org_id"], "role": key.get("role")}
        if request is not None:
            request.state.org_ctx = ctx
        return ctx
    if not org_service.orgs_enabled() or not x_org_id:
        return None
    if not is_uuid(x_org_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-Org-Id header.")
    try:
        ctx = org_service.resolve_org_context(user["id"], x_org_id)
    except (OrgNotFound, OrgPermissionError, OrgError) as exc:
        raise translate_org_error(exc) from exc
    if request is not None:
        request.state.org_ctx = ctx
    return ctx


def get_org_write_context(org_ctx: dict | None = Depends(get_org_context)) -> dict | None:
    """Same as get_org_context, but viewers may not save claims or policies into the workspace."""
    if org_ctx and not org_service.role_at_least(org_ctx.get("role"), "member"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Viewers cannot create claims or policies in this workspace.")
    return org_ctx
