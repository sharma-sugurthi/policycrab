"""
Deadline Calculator — computes appeal filing deadlines.

All deadlines are deterministic, calculated from the denial date
using the applicable legal framework's timeline requirements.
"""

from datetime import date, timedelta
from app.models.enums import AppealFramework
from app.engine.state_profiles import get_state_external_review_deadline


# ── Deadline Rules by Framework ───────────────────────────────────
# These are the MAXIMUM allowed filing windows.
# Using the most conservative (shortest) deadline where ranges exist.

_DEADLINE_RULES: dict[AppealFramework, dict] = {
    AppealFramework.ERISA_FEDERAL: {
        "calendar_days": 180,
        "description": "ERISA 29 CFR §2560.503-1: 180 calendar days from denial notice",
        "urgency_note": "Submit ALL evidence with the appeal — the administrative record closes after internal review",
    },
    AppealFramework.STATE_EXTERNAL_REVIEW: {
        "calendar_days": 120,
        "description": "State external review: typically 120 calendar days (varies by state, using conservative estimate)",
        "urgency_note": "Check your state's DOI website for exact deadline — some states allow only 60 days",
    },
    AppealFramework.MEDICARE_ADVANTAGE_5LEVEL: {
        "calendar_days": 60,
        "description": "Medicare Advantage Level 1 Redetermination: 60 calendar days from denial notice",
        "urgency_note": "Expedited review available in 72 hours if standard timeline could jeopardize health",
    },
    AppealFramework.NSA_IDR: {
        "business_days": 30,
        "description": "No Surprises Act: 30 business days open negotiation period from initial payment/denial",
        "urgency_note": "This is the provider's deadline to initiate IDR; patient cost-sharing is already capped",
    },
    AppealFramework.STATE_DOI_COMPLAINT: {
        "calendar_days": 365,
        "description": "State DOI complaint: typically up to 1 year (varies by state)",
        "urgency_note": "File as early as possible — regulatory investigations can take months",
    },
}


def _add_business_days(start_date: date, business_days: int) -> date:
    current = start_date
    remaining = business_days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def calculate_appeal_deadline(
    framework: AppealFramework,
    denial_date: date,
    state_code: str | None = None,
) -> dict:
    """
    Calculate the appeal filing deadline based on the applicable framework.

    For STATE_EXTERNAL_REVIEW, uses the state-specific deadline from the
    state registry when state_code is provided, instead of the generic 120-day default.

    Returns:
        dict with deadline date, days remaining, framework details,
        and urgency classification.
    """
    rule = _DEADLINE_RULES.get(framework)
    if not rule:
        raise ValueError(f"Unknown appeal framework: {framework}")

    # Override calendar_days with state-specific deadline for state-regulated plans
    if framework == AppealFramework.STATE_EXTERNAL_REVIEW and state_code:
        state_deadline = get_state_external_review_deadline(state_code)
        rule = {
            **rule,
            "calendar_days": state_deadline,
            "description": (
                f"{rule['description'].split('(')[0].strip()} "
                f"({state_code} state-specific: {state_deadline} calendar days)"
            ),
        }

    if "business_days" in rule:
        deadline_date = _add_business_days(denial_date, rule["business_days"])
        days_allowed = rule["business_days"]
        days_label = "business_days_allowed"
    else:
        deadline_date = denial_date + timedelta(days=rule["calendar_days"])
        days_allowed = rule["calendar_days"]
        days_label = "calendar_days_allowed"

    today = date.today()
    days_remaining = (deadline_date - today).days

    # Classify urgency
    if days_remaining <= 0:
        urgency = "EXPIRED"
        urgency_message = (
            f"⚠️ CRITICAL: The appeal deadline has EXPIRED. "
            f"The deadline was {deadline_date.isoformat()} ({abs(days_remaining)} days ago). "
            f"The patient may have permanently forfeited their right to appeal under {framework.value}."
        )
    elif days_remaining <= 7:
        urgency = "CRITICAL"
        urgency_message = (
            f"🔴 CRITICAL: Only {days_remaining} day(s) remaining. "
            f"File the appeal IMMEDIATELY."
        )
    elif days_remaining <= 30:
        urgency = "URGENT"
        urgency_message = (
            f"🟠 URGENT: {days_remaining} days remaining. "
            f"Begin preparing the appeal now."
        )
    elif days_remaining <= 90:
        urgency = "MODERATE"
        urgency_message = (
            f"🟡 MODERATE: {days_remaining} days remaining. "
            f"Adequate time to prepare a thorough appeal."
        )
    else:
        urgency = "STANDARD"
        urgency_message = (
            f"🟢 STANDARD: {days_remaining} days remaining. "
            f"Sufficient time for preparation and evidence gathering."
        )

    return {
        "framework": framework.value,
        "denial_date": denial_date.isoformat(),
        "deadline_date": deadline_date.isoformat(),
        days_label: days_allowed,
        "calendar_days_allowed": (deadline_date - denial_date).days,
        "days_remaining": days_remaining,
        "urgency": urgency,
        "urgency_message": urgency_message,
        "framework_description": rule["description"],
        "urgency_note": rule["urgency_note"],
    }
