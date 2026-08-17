"""
Tests for the Carrier Intelligence module — verifies correct carrier
matching and intelligence output formatting for all major insurers.
"""

import pytest
from app.engine.carrier_intelligence import (
    get_carrier_intelligence,
    format_carrier_intelligence_for_prompt,
    CARRIER_INTELLIGENCE,
)


class TestCarrierIntelligenceLookup:
    """Verify that carrier names (including variations) resolve correctly."""

    def test_uhc_exact(self):
        intel = get_carrier_intelligence("UnitedHealthcare")
        assert intel is not None
        assert intel.carrier_id == "unitedhealthcare"
        assert intel.algorithmic_system == "nH Predict (naviHealth)"

    def test_uhc_alias_uhc(self):
        intel = get_carrier_intelligence("UHC")
        assert intel is not None
        assert intel.carrier_id == "unitedhealthcare"

    def test_uhc_two_words(self):
        intel = get_carrier_intelligence("united healthcare")
        assert intel is not None
        assert intel.carrier_id == "unitedhealthcare"

    def test_cigna(self):
        intel = get_carrier_intelligence("Cigna")
        assert intel is not None
        assert intel.algorithmic_system == "PXDX (Procedure-Diagnosis)"

    def test_cigna_full_name(self):
        intel = get_carrier_intelligence("The Cigna Group")
        assert intel is not None
        assert intel.carrier_id == "cigna"

    def test_humana(self):
        intel = get_carrier_intelligence("Humana")
        assert intel is not None
        assert "Senate" in intel.denial_rate_context

    def test_aetna(self):
        intel = get_carrier_intelligence("Aetna")
        assert intel is not None
        assert intel.carrier_id == "aetna"

    def test_ambetter_resolves_to_centene(self):
        intel = get_carrier_intelligence("Ambetter")
        assert intel is not None
        assert intel.carrier_id == "centene"

    def test_kaiser(self):
        intel = get_carrier_intelligence("Kaiser Permanente")
        assert intel is not None
        assert "6%" in intel.denial_rate_context

    def test_molina(self):
        intel = get_carrier_intelligence("Molina Healthcare")
        assert intel is not None
        assert "22%" in intel.denial_rate_context

    def test_unknown_carrier_returns_none(self):
        intel = get_carrier_intelligence("Acme Insurance Co")
        assert intel is None

    def test_empty_string_returns_none(self):
        intel = get_carrier_intelligence("")
        assert intel is None

    def test_none_returns_none(self):
        intel = get_carrier_intelligence(None)
        assert intel is None


class TestCarrierIntelligenceContent:
    """Verify the intelligence data is substantive and actionable."""

    def test_uhc_has_litigation_context(self):
        intel = get_carrier_intelligence("UnitedHealthcare")
        assert len(intel.litigation_context) >= 1
        assert any("Lokken" in ctx for ctx in intel.litigation_context)

    def test_uhc_has_strategy_notes(self):
        intel = get_carrier_intelligence("UnitedHealthcare")
        assert len(intel.appeal_strategy_notes) >= 3
        assert any("nH Predict" in note for note in intel.appeal_strategy_notes)

    def test_uhc_has_reversal_rate(self):
        intel = get_carrier_intelligence("UnitedHealthcare")
        assert "90%" in intel.reversal_rate_on_appeal

    def test_cigna_has_pxdx_details(self):
        intel = get_carrier_intelligence("Cigna")
        assert "1.2 seconds" in intel.algorithmic_system_description
        assert "300,000" in intel.denial_rate_context

    def test_cigna_strategy_cites_erisa(self):
        intel = get_carrier_intelligence("Cigna")
        assert any("ERISA" in note for note in intel.appeal_strategy_notes)


class TestPromptFormatting:
    """Verify the formatted output is suitable for LLM injection."""

    def test_uhc_format_contains_algorithm_warning(self):
        intel = get_carrier_intelligence("UnitedHealthcare")
        formatted = format_carrier_intelligence_for_prompt(intel)
        assert "ALGORITHMIC DENIAL SYSTEM DETECTED" in formatted
        assert "nH Predict" in formatted

    def test_cigna_format_contains_pxdx(self):
        intel = get_carrier_intelligence("Cigna")
        formatted = format_carrier_intelligence_for_prompt(intel)
        assert "PXDX" in formatted
        assert "APPEAL STRATEGY GUIDANCE" in formatted

    def test_kaiser_format_no_algorithm_warning(self):
        intel = get_carrier_intelligence("Kaiser")
        formatted = format_carrier_intelligence_for_prompt(intel)
        assert "ALGORITHMIC DENIAL SYSTEM DETECTED" not in formatted
        assert "DENIAL PATTERN" in formatted

    def test_format_includes_all_sections(self):
        intel = get_carrier_intelligence("UnitedHealthcare")
        formatted = format_carrier_intelligence_for_prompt(intel)
        assert "DENIAL PATTERN" in formatted
        assert "REVERSAL RATE" in formatted
        assert "LITIGATION CONTEXT" in formatted
        assert "REGULATORY ACTIONS" in formatted
        assert "APPEAL STRATEGY GUIDANCE" in formatted
        assert "HIGH-RISK DENIAL CATEGORIES" in formatted

    def test_all_carriers_produce_nonempty_format(self):
        """Every carrier in the database must produce meaningful formatted output."""
        for carrier_id, intel in CARRIER_INTELLIGENCE.items():
            formatted = format_carrier_intelligence_for_prompt(intel)
            assert len(formatted) > 100, f"Carrier {carrier_id} has insufficient intelligence"
            assert intel.display_name in formatted
