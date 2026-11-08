"""dominio.whatsapp (Fase 8, P10): normalización E.164, enmascaramiento
y plantilla de mensaje. Puro, sin I/O."""
from decimal import Decimal
import pytest

from domain.budgets import Budget, derive_budget_items
from domain.whatsapp import (
    WHATSAPP_DAILY_LIMIT,
    budget_whatsapp_message,
    mask_phone,
    normalize_e164_ar,
)


def _budget() -> Budget:
    items, _totals = derive_budget_items(
        (
            ("p1", "Torta de Limón", 2, Decimal("775"), None),
            ("p2", "Brownie de Chispas", 1, Decimal("450"), None),
        ),
        Decimal("100"),
    )
    return Budget(
        customer_id="c1",
        customer_name="María Fernanda",
        customer_phone="5493571234567",
        items=items,
        margin_pct=Decimal("100"),
        seq="#00001",
        version=1,
        status="enviado",
    )


class TestNormalizeE164Ar:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # Internacional.
            ("+54 9 11 5555-6789", "5491155556789"),
            ("5491155556789", "5491155556789"),
            ("0054 9 357 422-3456", "5493574223456"),
            # Nacional (0 + área).
            ("011 5555-6789", "541155556789"),
            ("0357 422-3456", "543574223456"),
            # Local sin 0.
            ("11 5555-6789", "541155556789"),
            ("357 422-3456", "543574223456"),
            ("9 11 5555-6789", "5491155556789"),
            # Guardado en la BD ya como dígitos (normalize_phone del cliente).
            ("5493571234567", "5493571234567"),
        ],
    )
    def test_acepta_formatos_argentinos(self, raw, expected):
        assert normalize_e164_ar(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "hola",           # sin digitos
            "123",            # corto
            "447911123456",   # otro pais: se rechazaria si quedara 12-13 digitos con +54
            "",
        ],
    )
    def test_rechaiza_formatos_invalidos(self, raw):
        with pytest.raises(ValueError):
            normalize_e164_ar(raw)


class TestMaskPhone:
    def test_mascara_el_numero(self):
        masked = mask_phone("5491155556789")
        assert masked == "+54 ** ****89"
        # El numero completo nunca aparece en el registro.
        assert "5555" not in masked
        assert "5491155556789" not in masked


class TestBudgetWhatsAppMessage:
    def test_contiene_saldo_items_total_y_firma(self):
        budget = _budget()
        msg = budget_whatsapp_message(
            budget, "Toscana Pastry", "http://localhost:8000/api/v1/pdf/tok.abc"
        )
        assert "Hola María Fernanda:" in msg
        assert "presupuesto #00001" in msg
        # Items: cant x producto - precio.
        assert "2 x Torta de Limón — $3.100,00" in msg
        assert "1 x Brownie de Chispas — $900,00" in msg
        # Total = subtotal (sin IVA); IVA 21% aparte: 4000 * 0.21 = 840.
        assert "Total: $4.000,00" in msg
        assert "IVA (21%): $840,00 — costo aparte del total" in msg
        # Link al PDF y firma del negocio.
        assert "http://localhost:8000/api/v1/pdf/tok.abc" in msg
        assert "Toscana Pastry" in msg

    def test_solo_campo_negocio_vacio(self):
        budget = _budget()
        msg = budget_whatsapp_message(budget, "", "http://x/api/v1/pdf/t")
        assert "Toscana Pastry" in msg  # fallback de nombre

    def test_limites(self):
        assert WHATSAPP_DAILY_LIMIT == 30
