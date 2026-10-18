"""WhatsApp outbound (Fase 8, P10).

Links wa.me (cero costo, sin Cloud API): plantilla de mensaje
(RF-P10-01), normalización a E.164 argentino (RF-P10-02) y enmascaramiento
del teléfono para logs/auditoría (RNF-P10-05). Funciones puras:
testeables sin I/O.
"""
from domain.budgets import Budget
from domain.pdf import format_money_peso

# RF-P10-06: límite de links por día.
WHATSAPP_DAILY_LIMIT = 30


def normalize_e164_ar(phone: str) -> str:
    """Teléfono argentino → dígitos E.164 para wa.me (+54 por defecto).

    Acepta: internacional (+54 / 0054), nacional (011, 0357) y local
    (11, 357; con o sin el 9 de celular). Retorna solo dígitos.
    """
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
            f"Teléfono inválido para WhatsApp (esperado +54 con 10-11 "
            f"dígitos locales), recibido: {phone}"
        )
    return digits


def mask_phone(e164: str) -> str:
    """RNF-P10-05: registro sin el teléfono completo: +54 ** ****89."""
    return f"+{e164[:2]} ** ****{e164[-2:]}"


def budget_whatsapp_message(
    budget: Budget, business_name: str, share_url: str
) -> str:
    """Plantilla outbound (RF-P10-01): saludo con nombre del cliente,
    ítems (cant × producto — precio), total y firma del negocio, con el
    link firmado al PDF. La codificación de la URL (es-AR, $, ñ) la hace
    el router con urllib.parse.quote."""
    business = business_name.strip() or "Toscana Pastry"
    totals = budget.totals
    lines = [f"Hola {budget.customer_name}:", ""]
    lines.append(f"Te enviamos el presupuesto {budget.seq} de {business}.")
    lines.append("Descargalo aqui:")
    lines.append(share_url)
    lines.append("")
    for item in budget.items:
        lines.append(
            f"- {item.qty} x {item.product_name} — {format_money_peso(item.line_selling)}"
        )
    lines.append("")
    lines.append(f"Total (IVA incluido): {format_money_peso(totals.total_venta)}")
    lines.append("")
    lines.append(f"Gracias! — {business}")
    return "\n".join(lines)
