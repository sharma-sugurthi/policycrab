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
  - CAN-SPAM compliant footer with unsubscribe link
  - Proper Reply-To header
  - Light background / white card — renders correctly in all email clients
"""

import logging
from app.config import settings

logger = logging.getLogger(__name__)


# ── Email Templates ───────────────────────────────────────────────────────────

def _base_layout(title: str, content: str) -> str:
    """
    Wraps content in a professional light-mode email layout.
    Light grey background + white card = renders correctly in Gmail, Outlook, Apple Mail.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f0f2f5;">
    <tr>
      <td align="center" style="padding:40px 16px;">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;">

          <!-- Gradient Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:28px 40px;text-align:center;border-radius:16px 16px 0 0;">
              <h1 style="margin:0;font-size:24px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">
                🦀 PolicyCrab
              </h1>
              <p style="margin:5px 0 0;font-size:12px;color:rgba(255,255,255,0.82);letter-spacing:1.5px;text-transform:uppercase;">
                AI Health Insurance Advocate
              </p>
            </td>
          </tr>

          <!-- White Card Body -->
          <tr>
            <td style="background:#ffffff;padding:40px 40px 32px;border-left:1px solid #e5e7eb;border-right:1px solid #e5e7eb;">
              {content}
            </td>
          </tr>

          <!-- Light Footer -->
          <tr>
            <td style="padding:20px 40px 28px;background-color:#f9fafb;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 16px 16px;text-align:center;">
              <p style="margin:0 0 6px;font-size:12px;color:#6b7280;">
                You are receiving this because you signed up at
                <a href="https://policycrab.tech" style="color:#667eea;text-decoration:none;">policycrab.tech</a>
              </p>
              <p style="margin:0;font-size:11px;color:#9ca3af;">
                PolicyCrab · Healthcare AI for Patients &nbsp;·&nbsp;
                <a href="https://policycrab.tech/unsubscribe" style="color:#9ca3af;">Unsubscribe</a>
                &nbsp;·&nbsp;
                <a href="https://policycrab.tech/privacy" style="color:#9ca3af;">Privacy Policy</a>
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
    """Premium welcome email — light card on grey background."""
    name = user_name.split("@")[0].capitalize() if "@" in user_name else user_name.capitalize()
    content = f"""
      <h2 style="margin:0 0 10px;font-size:22px;font-weight:700;color:#111827;">
        Welcome to PolicyCrab, {name}! 👋
      </h2>
      <p style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#4b5563;">
        You've joined an AI-powered platform designed to help US patients
        understand, challenge, and <strong style="color:#111827;">win insurance denials</strong>.
        Here is what you can do right now:
      </p>

      <!-- Feature list card -->
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 28px;">
        <tr>
          <td style="background:#f5f3ff;border-radius:12px;padding:20px 24px;border-left:4px solid #7c3aed;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
              <tr><td style="padding:6px 0;font-size:14px;color:#374151;">✅ &nbsp; Upload your Explanation of Benefits (EOB)</td></tr>
              <tr><td style="padding:6px 0;font-size:14px;color:#374151;">✅ &nbsp; Get instant AI analysis of your denial reason</td></tr>
              <tr><td style="padding:6px 0;font-size:14px;color:#374151;">✅ &nbsp; Generate a HIPAA-compliant formal appeal letter</td></tr>
              <tr><td style="padding:6px 0;font-size:14px;color:#374151;">✅ &nbsp; Detect NSA surprise billing violations automatically</td></tr>
            </table>
          </td>
        </tr>
      </table>

      <!-- CTA Button -->
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 28px;">
        <tr>
          <td align="center">
            <a href="https://policycrab.tech/dashboard"
               style="display:inline-block;background:linear-gradient(135deg,#667eea,#764ba2);color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;padding:14px 40px;border-radius:8px;">
              Go to My Dashboard →
            </a>
          </td>
        </tr>
      </table>

      <hr style="border:none;border-top:1px solid #f3f4f6;margin:0 0 20px;">
      <p style="margin:0;font-size:13px;color:#9ca3af;text-align:center;">
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
    """Appeal letter email template — clean light card layout."""
    name = user_name.split("@")[0].capitalize() if "@" in user_name else user_name.capitalize()
    formatted = "".join(
        f'<p style="margin:0 0 12px;font-size:14px;line-height:1.8;color:#374151;">{line}</p>'
        for line in appeal_text.split("\n") if line.strip()
    )
    content = f"""
      <h2 style="margin:0 0 6px;font-size:22px;font-weight:700;color:#111827;">
        Your Appeal Letter is Ready
      </h2>
      <p style="margin:0 0 24px;font-size:14px;color:#6b7280;">
        Claim Reference:
        <span style="color:#7c3aed;font-family:monospace;font-weight:600;background:#f5f3ff;padding:2px 8px;border-radius:4px;">{claim_id}</span>
      </p>

      <p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#4b5563;">
        Hi {name}, your AI-generated appeal letter is ready below. Copy and submit it
        directly to your insurance company's appeals department.
      </p>

      <!-- Appeal Letter Box -->
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 24px;">
        <tr>
          <td style="background:#fafafa;border-radius:10px;padding:24px;border:1px solid #e5e7eb;border-left:4px solid #7c3aed;">
            {formatted}
          </td>
        </tr>
      </table>

      <!-- CTA -->
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 24px;">
        <tr>
          <td align="center">
            <a href="https://policycrab.tech/dashboard"
               style="display:inline-block;background:linear-gradient(135deg,#667eea,#764ba2);color:#ffffff;font-size:14px;font-weight:600;text-decoration:none;padding:12px 32px;border-radius:8px;">
              View Full Appeal on PolicyCrab →
            </a>
          </td>
        </tr>
      </table>

      <hr style="border:none;border-top:1px solid #f3f4f6;margin:0 0 16px;">
      <p style="margin:0;font-size:12px;line-height:1.7;color:#9ca3af;">
        <strong style="color:#6b7280;">⚠️ Important:</strong> This letter is AI-generated. Always review
        with a licensed healthcare advocate or attorney before submission for critical claims.
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
