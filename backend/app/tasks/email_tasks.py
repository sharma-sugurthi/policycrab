"""
Email delivery background task — runs inside the FastAPI web dyno.

Uses asyncio (no separate worker process). Implements retry logic manually
since we don't have Celery's built-in retry mechanism.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_send_email(
    to_email: str,
    subject: str,
    html_body: str,
    from_email: str | None = None,
    max_retries: int = 3,
) -> bool:
    """
    Send a transactional email via Resend with manual retry logic.

    Runs as a FastAPI BackgroundTask — fire-and-forget from the API's
    perspective, but with guaranteed delivery attempts.
    """
    from app.config import settings

    if not settings.resend_api_key:
        logger.warning("Email task: RESEND_API_KEY not configured, skipping.")
        return False

    sender = from_email or settings.email_from

    for attempt in range(1, max_retries + 1):
        try:
            import resend
            resend.api_key = settings.resend_api_key

            response = resend.Emails.send({
                "from": sender,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            })

            msg_id = response.get("id", "unknown") if isinstance(response, dict) else str(response)
            logger.info(f"Email delivered: to={to_email}, id={msg_id}")
            return True

        except Exception as exc:
            logger.warning(f"Email attempt {attempt}/{max_retries} failed: {exc}")
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt * 3)   # 6s, 12s, 24s backoff

    logger.error(f"Email delivery permanently failed after {max_retries} attempts: to={to_email}")
    return False


async def run_send_otp_email(
    to_email: str,
    otp_code: str,
    full_name: str = "",
) -> bool:
    """Send an OTP verification email. Higher priority, shorter content."""
    subject = f"Your PolicyCrab verification code: {otp_code}"
    greeting = f"Hi {full_name}," if full_name else "Hi there,"

    html_body = f"""
    <div style="font-family: 'Inter', -apple-system, sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 24px;">
        <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="font-size: 24px; font-weight: 700; color: #0f172a; margin: 0;">🦀 PolicyCrab</h1>
            <p style="color: #64748b; font-size: 14px; margin-top: 4px;">US Healthcare Claims Advocate</p>
        </div>
        <p style="color: #334155; font-size: 16px; line-height: 1.6;">{greeting}</p>
        <p style="color: #334155; font-size: 16px; line-height: 1.6;">Your verification code is:</p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="font-family: 'SF Mono', 'Fira Code', monospace; font-size: 36px; font-weight: 700;
                         letter-spacing: 8px; color: #0f172a; background: #f1f5f9; padding: 16px 32px;
                         border-radius: 12px; display: inline-block;">{otp_code}</span>
        </div>
        <p style="color: #64748b; font-size: 14px; line-height: 1.6;">
            This code expires in 10 minutes. If you didn't request this, you can safely ignore this email.
        </p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 32px 0;">
        <p style="color: #94a3b8; font-size: 12px; text-align: center;">
            PolicyCrab — AI-powered healthcare claim advocacy
        </p>
    </div>
    """

    return await run_send_email(to_email, subject, html_body, max_retries=3)
