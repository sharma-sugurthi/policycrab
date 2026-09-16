"""One call for the frontend to learn which opt-in features this deployment enables."""

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.config import settings

router = APIRouter(prefix="/api/features", tags=["System"])


@router.get("")
async def features(user: dict = Depends(get_current_user)):
    return {
        "orgs": bool(settings.orgs_enabled),
        "api_keys": bool(settings.api_keys_enabled),
        "cases": bool(settings.cases_enabled),
        "usage_metering": bool(settings.usage_metering_enabled),
        "audit_trail": bool(settings.audit_trail_enabled),
    }
