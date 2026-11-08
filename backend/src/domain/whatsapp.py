from decimal import Decimal

from domain.budgets import Budget, IVA_PCT
from domain.pdf import format_money_peso

WHATSAPP_DAILY_LIMIT = 30


def normalize_e164_ar(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        raise ValueError("El teléfono no contiene dígitos")
    if digits.startswith("0054"):
        digits = digits[2:]
    elif digits.startswith("054"):
        digits = digits[1:]
    if not digits.startswith("54"):
        if digits.startswith("0"):
            digits = digits[1:]
        if not digits.startswith("54"):
            digits = "54" + digits
    if not (12 <= len(digits) <= 13):
        raise ValueError(
            "Teléfono inválido para WhatsApp (esperado +54 con 10-11 "
            "dígitos locales)"
        )
    return digits


def mask_phone(e164: str) -> str:
    return f"+{e164[:2]} ** ****{e164[-2:]}"


def budget_whatsapp_message(
    budget: Budget, business_name: str, share_url: str
) -> str:
    business = business_name.strip() or "Toscana Pastry"
    totals = budget.totals
    lines = [f"Hola {budget.customer_name}:", ""]
    lines.append(f"Te enviamos el presupuesto {budget.seq} de {business}.")
    if budget.delivery_address:
        lines.append(f"Entrega: {budget.delivery_address}")
    lines.append("Descargalo aqui:")
    lines.append(share_url)
    lines.append("")
    for item in budget.items:
        lines.append(
            f"- {item.qty} x {item.product_name} — {format_money_peso(item.line_selling)}"
        )
    lines.append("")
    lines.append(f"Total: {format_money_peso(totals.total_venta)}")
    lines.append(
        f"IVA ({IVA_PCT.quantize(Decimal('1'))}%): {format_money_peso(totals.iva)} — "
        "costo aparte del total"
    )
    lines.append("")
    lines.append(f"Gracias! — {business}")
    return "\n".join(lines)
