from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

_HUNDRED = Decimal("100")


def _to_cents(value) -> int:
    if isinstance(value, bool):
        raise ValueError("bool no es un monto valido")
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        return int((value * _HUNDRED).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    raise ValueError(f"el monto debe ser entero de centavos, no {type(value).__name__}")


def cents_to_decimal(cents: int) -> Decimal:
    return Decimal(cents) / _HUNDRED


def decimal_to_cents(value: Decimal | int | float | str) -> int:
    return int(_to_cents(value))


def format_money_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    c = abs(int(cents))
    pesos, centavos = divmod(c, 100)
    s = f"{pesos:,}".replace(",", ".")
    return f"{sign}${s},{centavos:02d}"


def _coerce_qty(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool no es una cantidad valida")
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"cantidad invalida: {value!r}") from exc
    raise TypeError(f"tipo no aceptado para cantidad: {type(value).__name__}")


def _coerce_pct(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool no es un porcentaje valido")
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"porcentaje invalido: {value!r}") from exc
    raise TypeError(f"tipo no aceptado para porcentaje: {type(value).__name__}")


Money = Annotated[
    int,
    BeforeValidator(_to_cents),
    PlainSerializer(lambda v: int(v), return_type=int, when_used="json"),
]

Qty = Annotated[
    Decimal,
    BeforeValidator(_coerce_qty),
    PlainSerializer(lambda v: str(v), return_type=str, when_used="json"),
]

Pct = Annotated[
    Decimal,
    BeforeValidator(_coerce_pct),
    PlainSerializer(lambda v: str(v), return_type=str, when_used="json"),
]
