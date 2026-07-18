"""
PolicyCrab Email Service — Powered by Resend

Industry-standard transactional email templates inspired by Stripe, GitHub, and Notion.
Design principles:
  - #f6f9fc light grey outer background (Stripe standard)
  - Pure white card with clean border
  - Black/dark-grey type for maximum legibility
  - Single accent colour (purple) for brand consistency
  - No dark backgrounds — renders perfectly in Gmail, Outlook, Apple Mail
  - Plain-text alternative for every email (required for deliverability)
  - CAN-SPAM compliant footer (required by US law)
"""

import logging
from app.config import settings

logger = logging.getLogger(__name__)


# ── Base Layout ───────────────────────────────────────────────────────────────

def _base_layout(title: str, content: str, preview: str = "") -> str:
    """
    Stripe-style email shell:
      - #f6f9fc outer background
      - White card with #e6ebf1 border and 8px radius
      - Clean minimal footer
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light">
  <meta name="supported-color-schemes" content="light">
  <title>{title}</title>
  {'<span style="display:none;max-height:0;overflow:hidden;">' + preview + '</span>' if preview else ''}
</head>
<body style="margin:0;padding:0;background-color:#f6f9fc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#f6f9fc">
    <tr>
      <td align="center" style="padding:40px 16px;">

        <!-- Logo area -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;">
          <tr>
            <td style="padding:0 0 20px;text-align:center;">
              <span style="font-size:22px;font-weight:700;color:#0a0a0a;letter-spacing:-0.5px;">🦀 PolicyCrab</span>
            </td>
          </tr>
        </table>

        <!-- White card -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;background-color:#ffffff;border:1px solid #e6ebf1;border-radius:8px;">
          <tr>
            <td style="padding:40px 48px 36px;">
              {content}
            </td>
          </tr>
        </table>

        <!-- Footer -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;">
          <tr>
            <td style="padding:24px 0 0;text-align:center;">
              <p style="margin:0;font-size:12px;line-height:1.7;color:#8898aa;">
                PolicyCrab · AI Health Insurance Advocate<br>
                <a href="https://policycrab.tech" style="color:#8898aa;">policycrab.tech</a>
                &nbsp;·&nbsp;
                <a href="https://policycrab.tech/unsubscribe" style="color:#8898aa;">Unsubscribe</a>
              </p>
            </td>
          </tr>
        </table>

      </td>
    </tr>
  </table>
</body>
</html>"""


# ── Welcome Email ─────────────────────────────────────────────────────────────

def _welcome_html(user_name: str) -> str:
    """Stripe/GitHub-style welcome email using the user's first name."""
    # Extract first name cleanly
    raw = user_name.split("@")[0] if "@" in user_name else user_name
    first_name = raw.split()[0].capitalize() if raw else "there"

    content = f"""
      <h1 style="margin:0 0 16px;font-size:24px;font-weight:700;color:#0a0a0a;letter-spacing:-0.3px;">
        Welcome, {first_name}!
      </h1>
      <p style="margin:0 0 20px;font-size:15px;line-height:1.7;color:#425466;">
        You're now on <strong style="color:#0a0a0a;">PolicyCrab</strong> — the AI-powered platform
        that helps US patients understand, challenge, and win insurance denials.
      </p>

      <hr style="border:none;border-top:1px solid #e6ebf1;margin:0 0 20px;">

      <p style="margin:0 0 10px;font-size:13px;font-weight:600;color:#0a0a0a;text-transform:uppercase;letter-spacing:0.5px;">
        What you can do
      </p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 24px;">
        <tr><td style="padding:6px 0;font-size:14px;color:#425466;border-bottom:1px solid #f6f9fc;">
          <span style="color:#635bff;font-weight:700;">→</span>&nbsp; Upload your Explanation of Benefits (EOB)
        </td></tr>
        <tr><td style="padding:6px 0;font-size:14px;color:#425466;border-bottom:1px solid #f6f9fc;">
          <span style="color:#635bff;font-weight:700;">→</span>&nbsp; Get instant AI analysis of your denial reason
        </td></tr>
        <tr><td style="padding:6px 0;font-size:14px;color:#425466;border-bottom:1px solid #f6f9fc;">
          <span style="color:#635bff;font-weight:700;">→</span>&nbsp; Generate a HIPAA-compliant formal appeal letter
        </td></tr>
        <tr><td style="padding:6px 0;font-size:14px;color:#425466;">
          <span style="color:#635bff;font-weight:700;">→</span>&nbsp; Detect NSA surprise billing violations automatically
        </td></tr>
      </table>

      <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 28px;">
        <tr>
          <td style="border-radius:6px;background-color:#635bff;">
            <a href="https://policycrab.tech/dashboard"
               style="display:inline-block;padding:12px 28px;font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;letter-spacing:0.1px;">
              Go to Dashboard →
            </a>
          </td>
        </tr>
      </table>

      <hr style="border:none;border-top:1px solid #e6ebf1;margin:0 0 20px;">
      <p style="margin:0;font-size:13px;color:#8898aa;">
        Questions? Reply to this email — we personally read every message.
      </p>
    """
    return _base_layout(
        "Welcome to PolicyCrab!",
        content,
        preview=f"Hi {first_name}, you're all set — let's fight your denial."
    )


def _welcome_text(user_name: str) -> str:
    raw = user_name.split("@")[0] if "@" in user_name else user_name
    first_name = raw.split()[0].capitalize() if raw else "there"
    return f"""Welcome to PolicyCrab, {first_name}!

You're now on PolicyCrab — the AI platform that helps US patients fight insurance denials.

What you can do:
→ Upload your Explanation of Benefits (EOB)
→ Get instant AI analysis of your denial reason
→ Generate a HIPAA-compliant formal appeal letter
→ Detect NSA surprise billing violations automatically

Go to your dashboard: https://policycrab.tech/dashboard

Questions? Reply to this email — we personally read every message.

---
PolicyCrab · policycrab.tech
Unsubscribe: https://policycrab.tech/unsubscribe
"""


# ── Appeal Letter Email ───────────────────────────────────────────────────────

def _appeal_html(user_name: str, claim_id: str, appeal_text: str) -> str:
    """GitHub/Notion-style appeal letter delivery."""
    raw = user_name.split("@")[0] if "@" in user_name else user_name
    first_name = raw.split()[0].capitalize() if raw else "there"
    formatted = "".join(
        f'<p style="margin:0 0 12px;font-size:14px;line-height:1.8;color:#425466;">{line}</p>'
        for line in appeal_text.split("\n") if line.strip()
    )
    content = f"""
      <h1 style="margin:0 0 8px;font-size:22px;font-weight:700;color:#0a0a0a;letter-spacing:-0.3px;">
        Your appeal letter is ready
      </h1>
      <p style="margin:0 0 24px;font-size:14px;color:#8898aa;">
        Claim <code style="background:#f6f9fc;padding:2px 6px;border-radius:4px;color:#635bff;font-size:13px;">{claim_id}</code>
      </p>

      <p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#425466;">
        Hi {first_name}, your AI-generated appeal letter is below. Copy it and submit
        directly to your insurance company's appeals department.
      </p>

      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 24px;">
        <tr>
          <td style="background:#f6f9fc;border-radius:6px;padding:20px 24px;border-left:3px solid #635bff;">
            {formatted}
          </td>
        </tr>
      </table>

      <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 28px;">
        <tr>
          <td style="border-radius:6px;background-color:#635bff;">
            <a href="https://policycrab.tech/dashboard"
               style="display:inline-block;padding:12px 28px;font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;">
              View on PolicyCrab →
            </a>
          </td>
        </tr>
      </table>

      <hr style="border:none;border-top:1px solid #e6ebf1;margin:0 0 16px;">
      <p style="margin:0;font-size:12px;color:#8898aa;line-height:1.7;">
        This letter was generated by AI based on your uploaded document. Always review
        with a licensed healthcare advocate or attorney before submitting a critical claim.
      </p>
    """
    return _base_layout(
        f"Your PolicyCrab Appeal Letter — Claim {claim_id}",
        content,
        preview="Your AI-generated insurance appeal letter is ready to submit."
    )


def _appeal_text(user_name: str, claim_id: str, appeal_text: str) -> str:
    raw = user_name.split("@")[0] if "@" in user_name else user_name
    first_name = raw.split()[0].capitalize() if raw else "there"
    return f"""Hi {first_name},

Your PolicyCrab appeal letter for Claim {claim_id} is ready.

--- APPEAL LETTER ---

{appeal_text}

--- END OF LETTER ---

View on PolicyCrab: https://policycrab.tech/dashboard

Note: This letter is AI-generated. Review with a licensed advocate before submission.

---
PolicyCrab · policycrab.tech
"""


# ── Email Service ─────────────────────────────────────────────────────────────

class EmailService:
    """Resend-backed email sender with pre-built PolicyCrab templates."""

    def __init__(self):
        self._configured = bool(settings.resend_api_key)
        if self._configured:
            import resend as _resend
            _resend.api_key = settings.resend_api_key
            self._resend = _resend
            logger.info("EmailService: Resend configured ✅")
        else:
            logger.warning("EmailService: RESEND_API_KEY not set — emails will be skipped.")

    def send_welcome_email(self, user_email: str, user_name: str = "") -> bool:
        if not self._configured:
            logger.warning(f"Email skipped (not configured): welcome → {user_email}")
            return False
        try:
            params = {
                "from": settings.email_from,
                "to": [user_email],
                "reply_to": "info@policycrab.tech",
                "subject": "Welcome to PolicyCrab",
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
