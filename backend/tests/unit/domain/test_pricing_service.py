from decimal import Decimal

import pytest

from domain.pricing_service import AudienceForbiddenError, derive_audience_price


class TestDeriveAudiencePrice:

    def test_revendedores_returns_base_unchanged(self):
        assert derive_audience_price(Decimal("2800"), Decimal("40"), "revendedores") == Decimal("2800")

    def test_consumidor_final_applies_markup(self):
        result = derive_audience_price(Decimal("10.00"), Decimal("40"), "consumidor_final")
        assert result == Decimal("14.00")

    def test_consumidor_final_half_up_rounding(self):
        result = derive_audience_price(Decimal("1.005"), Decimal("40"), "consumidor_final")
        assert result == Decimal("1.41")

    def test_zero_markup(self):
        assert derive_audience_price(Decimal("100"), Decimal("0"), "revendedores") == Decimal("100")
        assert derive_audience_price(Decimal("100"), Decimal("0"), "consumidor_final") == Decimal("100")

    def test_large_markup(self):
        result = derive_audience_price(Decimal("50.00"), Decimal("100"), "consumidor_final")
        assert result == Decimal("100.00")


class TestResolveAudienceError:

    def test_forbidden_message_is_clean_spanish(self):
        from domain.pricing_service import resolve_audience

        with pytest.raises(AudienceForbiddenError) as excinfo:
            resolve_audience("customer", "revendedores")
        message = str(excinfo.value)
        assert message == "Tu rol no tiene acceso a la lista de revendedores"
        assert "UserRole" not in message
