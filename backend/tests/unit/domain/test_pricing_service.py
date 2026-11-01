"""Unit tests for derive_audience_price domain helper (T4 refactor).

This helper centralises the markup derivation formula so both
compute_dual_pricing (T3) and the pricelist router (T4) share one
home for the pricing rule.
"""
from decimal import Decimal

import pytest

from domain.pricing_service import AudienceForbiddenError, derive_audience_price


class TestDeriveAudiencePrice:
    """Tests for the price-derivation helper."""

    def test_revendedores_returns_base_unchanged(self):
        """T4-refactor: revendedores audience returns base_price as-is."""
        assert derive_audience_price(Decimal("2800"), Decimal("40"), "revendedores") == Decimal("2800")

    def test_consumidor_final_applies_markup(self):
        """T4-refactor: consumidor_final applies markup: base × (1 + markup/100)."""
        # 10.00 × 1.40 = 14.00
        result = derive_audience_price(Decimal("10.00"), Decimal("40"), "consumidor_final")
        assert result == Decimal("14.00")

    def test_consumidor_final_half_up_rounding(self):
        """T4-refactor: ROUND_HALF_UP quantization to 0.01.

        base 1.005 × 1.40 = 1.407 → rounds to 1.41 (half-up).
        """
        result = derive_audience_price(Decimal("1.005"), Decimal("40"), "consumidor_final")
        assert result == Decimal("1.41")

    def test_zero_markup(self):
        """T4-refactor: markup 0 → same price for both audiences."""
        assert derive_audience_price(Decimal("100"), Decimal("0"), "revendedores") == Decimal("100")
        assert derive_audience_price(Decimal("100"), Decimal("0"), "consumidor_final") == Decimal("100")

    def test_large_markup(self):
        """T4-refactor: large markup (e.g. 100% → double)."""
        result = derive_audience_price(Decimal("50.00"), Decimal("100"), "consumidor_final")
        assert result == Decimal("100.00")


class TestResolveAudienceError:
    """The 403 message is user-facing: Spanish, no role/enum leaks."""

    def test_forbidden_message_is_clean_spanish(self):
        """customer requesting revendedores gets a friendly Spanish message."""
        from domain.pricing_service import resolve_audience

        with pytest.raises(AudienceForbiddenError) as excinfo:
            resolve_audience("customer", "revendedores")
        message = str(excinfo.value)
        assert message == "Tu rol no tiene acceso a la lista de revendedores"
        assert "UserRole" not in message
