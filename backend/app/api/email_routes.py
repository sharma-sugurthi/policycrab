"""
Email API Routes

Provides authenticated endpoints to trigger transactional emails:
  POST /api/email/welcome      — Welcome email (call on first login)
  POST /api/email/send-appeal  — Email the appeal letter to the user
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.api.auth import get_current_user
from app.services.email_service import get_email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["Email"])


class AppealEmailRequest(BaseModel):
    claim_id: str
    appeal_text: str


@router.post("/welcome", summary="Send welcome email to current user")
async def send_welcome(user: dict = Depends(get_current_user)):
    """
    Sends the onboarding welcome email to the currently authenticated user.
    Call this from the frontend immediately after a successful sign-up confirmation.
    """
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="No email address found for this user.")

    service = get_email_service()
    success = service.send_welcome_email(
        user_email=user_email,
        user_name=user.get("user_metadata", {}).get("full_name", user_email),
    )

    if not success:
        # Non-fatal: log but don't crash the user's sign-up flow
        logger.warning(f"Welcome email delivery failed for {user_email}")
        return {"sent": False, "message": "Email service not configured or delivery failed."}

    return {"sent": True, "message": f"Welcome email sent to {user_email}"}


@router.post("/send-appeal", summary="Email the appeal letter to the current user")
async def send_appeal_email(
    body: AppealEmailRequest,
    user: dict = Depends(get_current_user),
):
    """
    Emails the AI-generated appeal letter directly to the user's inbox.
    The appeal text is formatted into a premium HTML email with a plain-text fallback.
    """
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="No email address found for this user.")

    if not body.appeal_text or len(body.appeal_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Appeal text is too short to email.")

    service = get_email_service()
    success = service.send_appeal_letter(
        user_email=user_email,
        claim_id=body.claim_id,
        appeal_text=body.appeal_text,
        user_name=user.get("user_metadata", {}).get("full_name", user_email),
    )

    if not success:
        raise HTTPException(
            status_code=503,
            detail="Email delivery failed. Please try again or copy the letter manually.",
        )

    return {
        "sent": True,
        "message": f"Appeal letter emailed to {user_email}",
        "claim_id": body.claim_id,
    }
