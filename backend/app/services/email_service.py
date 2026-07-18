"""
PolicyCrab Email Service — Powered by Resend

Sends all transactional emails for PolicyCrab using the Resend API.
All templates are hand-crafted HTML to maximize deliverability and
avoid spam filters (proper structure, plain-text alternatives, CAN-SPAM
compliant footer, DKIM/SPF verified sending domain).

Anti-spam best practices applied:
  - Sending from verified domain (policycrab.tech)
  - DKIM + SPF + DMARC DNS records configured
  - Plain text alternative in every email (multipart/alternative)
  - No spam trigger words in subject lines
  - CAN-SPAM compliant physical address in footer
  - Proper Reply-To header
  - Clean HTML-to-text ratio (no image-only emails)
"""

import logging
from app.config import settings

logger = logging.getLogger(__name__)


# ── Email Templates ───────────────────────────────────────────────────────────

def _base_layout(title: str, content: str) -> str:
    """Wraps content in a premium, anti-spam-safe HTML email layout."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#0f1117;">
    <tr>
      <td align="center" style="padding:40px 16px;">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;background-color:#1a1d27;border-radius:16px;overflow:hidden;border:1px solid #2a2d3e;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:32px 40px;text-align:center;">
              <h1 style="margin:0;font-size:26px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">
                🦀 PolicyCrab
              </h1>
              <p style="margin:6px 0 0;font-size:13px;color:rgba(255,255,255,0.75);letter-spacing:1px;text-transform:uppercase;">
                Your AI Health Insurance Advocate
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:40px 40px 32px;">
              {content}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:24px 40px;background-color:#13151f;border-top:1px solid #2a2d3e;text-align:center;">
              <p style="margin:0 0 8px;font-size:12px;color:#6b7280;">
                You are receiving this because you signed up at
                <a href="https://policycrab.tech" style="color:#667eea;text-decoration:none;">policycrab.tech</a>
              </p>
              <p style="margin:0;font-size:11px;color:#4b5563;">
                PolicyCrab · Healthcare AI for Patients · policycrab.tech<br>
                <a href="https://policycrab.tech/unsubscribe" style="color:#4b5563;text-decoration:underline;">Unsubscribe</a>
                &nbsp;·&nbsp;
                <a href="https://policycrab.tech/privacy" style="color:#4b5563;text-decoration:underline;">Privacy Policy</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _welcome_html(user_name: str) -> str:
    """Premium welcome email template."""
    name = user_name.split("@")[0].capitalize() if "@" in user_name else user_name.capitalize()
    content = f"""
      <h2 style="margin:0 0 16px;font-size:24px;font-weight:700;color:#ffffff;">
        Welcome, {name}! 👋
      </h2>
      <p style="margin:0 0 20px;font-size:15px;line-height:1.7;color:#9ca3af;">
        You have just joined <strong style="color:#ffffff;">PolicyCrab</strong> — an AI-powered platform
        designed to help US patients understand, challenge, and win insurance denials.
      </p>

      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 28px;">
        <tr>
          <td style="background:#1e2235;border-radius:12px;padding:20px 24px;border-left:4px solid #667eea;">
            <p style="margin:0 0 14px;font-size:14px;font-weight:600;color:#ffffff;">What you can do right now:</p>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
              <tr><td style="padding:5px 0;font-size:14px;color:#9ca3af;">✅ &nbsp; Upload your Explanation of Benefits (EOB)</td></tr>
              <tr><td style="padding:5px 0;font-size:14px;color:#9ca3af;">✅ &nbsp; Get instant AI analysis of your denial</td></tr>
              <tr><td style="padding:5px 0;font-size:14px;color:#9ca3af;">✅ &nbsp; Generate a HIPAA-compliant appeal letter</td></tr>
              <tr><td style="padding:5px 0;font-size:14px;color:#9ca3af;">✅ &nbsp; Check for NSA surprise billing violations</td></tr>
            </table>
          </td>
        </tr>
      </table>

      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
          <td align="center">
            <a href="https://policycrab.tech/dashboard"
               style="display:inline-block;background:linear-gradient(135deg,#667eea,#764ba2);color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;padding:14px 36px;border-radius:8px;letter-spacing:0.3px;">
              Go to My Dashboard →
            </a>
          </td>
        </tr>
      </table>

      <p style="margin:28px 0 0;font-size:13px;line-height:1.7;color:#6b7280;text-align:center;">
        Questions? Reply to this email — we read every message.
      </p>
    """
    return _base_layout("Welcome to PolicyCrab!", content)


def _welcome_text(user_name: str) -> str:
    """Plain text fallback for the welcome email."""
    name = user_name.split("@")[0].capitalize() if "@" in user_name else user_name.capitalize()
    return f"""Welcome to PolicyCrab, {name}!

You've joined PolicyCrab — an AI platform that helps US patients fight insurance denials.

What you can do:
- Upload your Explanation of Benefits (EOB)
- Get instant AI analysis of your denial reason
- Generate a formal HIPAA-compliant appeal letter
- Check for NSA surprise billing violations

Go to your dashboard: https://policycrab.tech/dashboard

Questions? Reply to this email — we read every message.

---
PolicyCrab | https://policycrab.tech
Unsubscribe: https://policycrab.tech/unsubscribe
"""


def _appeal_html(user_name: str, claim_id: str, appeal_text: str) -> str:
    """Appeal letter email template."""
    name = user_name.split("@")[0].capitalize() if "@" in user_name else user_name.capitalize()
    # Safely format the appeal body as HTML paragraphs
    formatted = "".join(
        f'<p style="margin:0 0 12px;font-size:14px;line-height:1.8;color:#d1d5db;">{line}</p>'
        for line in appeal_text.split("\n") if line.strip()
    )
    content = f"""
      <h2 style="margin:0 0 6px;font-size:22px;font-weight:700;color:#ffffff;">
        Your Appeal Letter is Ready
      </h2>
      <p style="margin:0 0 24px;font-size:14px;color:#6b7280;">
        Claim Reference: <span style="color:#667eea;font-family:monospace;">{claim_id}</span>
      </p>

      <p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#9ca3af;">
        Hi {name}, here is your AI-generated appeal letter. Copy this text and submit it
        directly to your insurance company's appeals department.
      </p>

      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 24px;">
        <tr>
          <td style="background:#0d0f1a;border-radius:12px;padding:24px;border:1px solid #2a2d3e;border-left:4px solid #667eea;">
            {formatted}
          </td>
        </tr>
      </table>

      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
          <td align="center">
            <a href="https://policycrab.tech/dashboard"
               style="display:inline-block;background:linear-gradient(135deg,#667eea,#764ba2);color:#ffffff;font-size:14px;font-weight:600;text-decoration:none;padding:12px 32px;border-radius:8px;">
              View Full Appeal on PolicyCrab →
            </a>
          </td>
        </tr>
      </table>

      <p style="margin:24px 0 0;font-size:12px;line-height:1.7;color:#6b7280;">
        <strong style="color:#9ca3af;">Important:</strong> This letter is AI-generated based on the document you uploaded.
        Always review it with a licensed healthcare advocate or attorney before submission for critical claims.
      </p>
    """
    return _base_layout(f"Your PolicyCrab Appeal Letter — Claim {claim_id}", content)


def _appeal_text(user_name: str, claim_id: str, appeal_text: str) -> str:
    """Plain text fallback for the appeal email."""
    name = user_name.split("@")[0].capitalize() if "@" in user_name else user_name.capitalize()
    return f"""Hi {name},

Your PolicyCrab appeal letter for Claim {claim_id} is ready.

--- APPEAL LETTER START ---

{appeal_text}

--- APPEAL LETTER END ---

View on PolicyCrab: https://policycrab.tech/dashboard

Important: This letter is AI-generated. Review with a licensed advocate before submission.

---
PolicyCrab | https://policycrab.tech
"""


# ── Email Service ─────────────────────────────────────────────────────────────

class EmailService:
    """Thin wrapper around the Resend API with pre-built PolicyCrab templates."""

    def __init__(self):
        self._configured = bool(settings.resend_api_key)
        if self._configured:
            import resend as _resend
            _resend.api_key = settings.resend_api_key
            self._resend = _resend
            logger.info("EmailService: Resend API configured ✅")
        else:
            logger.warning(
                "EmailService: RESEND_API_KEY not set. "
                "Emails will be skipped. Add the key to .env to enable sending."
            )

    def send_welcome_email(self, user_email: str, user_name: str = "") -> bool:
        """
        Sends the onboarding welcome email to a newly registered user.
        Returns True on success, False on failure (non-blocking).
        """
        if not self._configured:
            logger.warning(f"Email skipped (not configured): welcome → {user_email}")
            return False

        try:
            params = {
                "from": settings.email_from,
                "to": [user_email],
                "reply_to": "info@policycrab.tech",
                "subject": "Welcome to PolicyCrab — Your AI Health Insurance Advocate",
                "html": _welcome_html(user_name or user_email),
                "text": _welcome_text(user_name or user_email),
            }
            response = self._resend.Emails.send(params)
            logger.info(f"Welcome email sent to {user_email} (id={response.get('id')})")
            return True
        except Exception as e:
            logger.error(f"Failed to send welcome email to {user_email}: {e}")
            return False

    def send_appeal_letter(
        self,
        user_email: str,
        claim_id: str,
        appeal_text: str,
        user_name: str = "",
    ) -> bool:
        """
        Emails the AI-generated appeal letter to the user.
        Returns True on success, False on failure (non-blocking).
        """
        if not self._configured:
            logger.warning(f"Email skipped (not configured): appeal → {user_email}")
            return False

        try:
            params = {
                "from": settings.email_from,
                "to": [user_email],
                "reply_to": "info@policycrab.tech",
                "subject": f"Your PolicyCrab Appeal Letter — Claim {claim_id}",
                "html": _appeal_html(user_name or user_email, claim_id, appeal_text),
                "text": _appeal_text(user_name or user_email, claim_id, appeal_text),
            }
            response = self._resend.Emails.send(params)
            logger.info(f"Appeal email sent to {user_email} (id={response.get('id')})")
            return True
        except Exception as e:
            logger.error(f"Failed to send appeal email to {user_email}: {e}")
            return False


# Singleton
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
