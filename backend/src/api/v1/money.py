"""Tipos de monto de la API (RF-07, RNF-P4-02).

**Money viaja por la API como entero de centavos (long)**: los últimos 2
dígitos son los centavos (310050 = $3.100,50). El dominio trabaja en
Decimal; la conversión vive en este módulo (el borde de la API):

  - entrada : centavos (int) → Decimal para el dominio (cents_to_decimal)
  - salida  : Decimal del dominio → centavos (int) (BeforeValidator + serializer)

**Qty** (cantidad: kg, g, L, ml, unidades) NO es dinero: sigue siendo
Decimal serializado a string ("500", "0.5"), sin centavos.

**Pct** (porcentaje: margen, gas, merma, urgencia) viaja como string decimal
("100"). Se separa de Money a propósito: tipear un % como Money y aplicarle
centavos dispara el valor ×100 (bug clásico). El frontend lo trata con
Number(), así que mantiene el formato string.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

_HUNDRED = Decimal("100")


def _to_cents(value) -> int:
    """Normaliza a centavos (int). Acepta int (canonical) y Decimal (del
    dominio, en unidades). str/float/bool se rechazan (-> 422)."""
    if isinstance(value, bool):
        raise ValueError("bool no es un monto valido")
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        return int((value * _HUNDRED).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    raise ValueError(f"el monto debe ser entero de centavos, no {type(value).__name__}")


def cents_to_decimal(cents: int) -> Decimal:
    """Centavos (int) de la API → Decimal de unidades para el dominio."""
    return Decimal(cents) / _HUNDRED


def decimal_to_cents(value: Decimal | int | float | str) -> int:
    """Decimal del dominio → long de centavos (solo en el borde).

    El schema ``Money`` acepta Decimal en runtime vía BeforeValidator; este
    helper hace la conversión explícita para que el typing sea estático.
    """
    return int(_to_cents(value))


def _coerce_qty(value) -> Decimal:
    """Qty: cantidad, no dinero. Decimal(str(v)) exacto, sin centavos."""
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
    """Pct: porcentaje (0..200). Decimal(str(v)) exacto, serializado a str."""
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


# Dinero: entero de centavos (long). when_used="json" → en python mode
# (model_dump) el valor sigue siendo int; la serialización JSON lo emite int.
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
