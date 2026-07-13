"""
Tests for the Deadline Calculator — verifies correct deadline
computation and urgency classification for each framework.
"""

from datetime import date, timedelta
from app.engine.deadline_calculator import calculate_appeal_deadline
from app.models.enums import AppealFramework


class TestDeadlineCalculation:
    """Verify correct deadline dates for each framework."""

    def test_erisa_180_days(self):
        denial = date(2025, 1, 1)
        result = calculate_appeal_deadline(AppealFramework.ERISA_FEDERAL, denial)
        assert result["deadline_date"] == "2025-06-30"
        assert result["calendar_days_allowed"] == 180

    def test_medicare_60_days(self):
        denial = date(2025, 3, 1)
        result = calculate_appeal_deadline(AppealFramework.MEDICARE_ADVANTAGE_5LEVEL, denial)
        assert result["deadline_date"] == "2025-04-30"
        assert result["calendar_days_allowed"] == 60

    def test_nsa_30_business_days(self):
        denial = date(2025, 6, 1)
        result = calculate_appeal_deadline(AppealFramework.NSA_IDR, denial)
        assert result["deadline_date"] == "2025-07-11"
        assert result["business_days_allowed"] == 30
        assert result["calendar_days_allowed"] == 40

    def test_state_review_120_days(self):
        denial = date(2025, 1, 1)
        result = calculate_appeal_deadline(AppealFramework.STATE_EXTERNAL_REVIEW, denial)
        assert result["deadline_date"] == "2025-05-01"
        assert result["calendar_days_allowed"] == 120


class TestUrgencyClassification:
    """Verify urgency levels based on remaining days."""

    def test_expired_deadline(self):
        old_denial = date.today() - timedelta(days=200)
        result = calculate_appeal_deadline(AppealFramework.ERISA_FEDERAL, old_denial)
        assert result["urgency"] == "EXPIRED"
        assert result["days_remaining"] < 0

    def test_critical_urgency(self):
        # Denial 175 days ago → 5 days remaining for ERISA (180 day window)
        denial = date.today() - timedelta(days=175)
        result = calculate_appeal_deadline(AppealFramework.ERISA_FEDERAL, denial)
        assert result["urgency"] == "CRITICAL"
        assert result["days_remaining"] <= 7

    def test_urgent(self):
        # Denial 160 days ago → 20 days remaining for ERISA
        denial = date.today() - timedelta(days=160)
        result = calculate_appeal_deadline(AppealFramework.ERISA_FEDERAL, denial)
        assert result["urgency"] == "URGENT"

    def test_moderate(self):
        # Denial 120 days ago → 60 days remaining for ERISA
        denial = date.today() - timedelta(days=120)
        result = calculate_appeal_deadline(AppealFramework.ERISA_FEDERAL, denial)
        assert result["urgency"] == "MODERATE"

    def test_standard(self):
        # Recent denial → plenty of time
        denial = date.today() - timedelta(days=5)
        result = calculate_appeal_deadline(AppealFramework.ERISA_FEDERAL, denial)
        assert result["urgency"] == "STANDARD"
        assert result["days_remaining"] > 90


class TestEdgeCases:
    """Edge cases for deadline calculation."""

    def test_denial_today(self):
        result = calculate_appeal_deadline(AppealFramework.ERISA_FEDERAL, date.today())
        assert result["days_remaining"] == 180
        assert result["urgency"] == "STANDARD"

    def test_state_doi_365_days(self):
        denial = date(2025, 1, 1)
        result = calculate_appeal_deadline(AppealFramework.STATE_DOI_COMPLAINT, denial)
        assert result["calendar_days_allowed"] == 365
        assert result["deadline_date"] == "2026-01-01"

    def test_result_contains_framework_info(self):
        result = calculate_appeal_deadline(AppealFramework.ERISA_FEDERAL, date.today())
        assert "ERISA" in result["framework_description"]
        assert result["framework"] == "ERISA_FEDERAL"
