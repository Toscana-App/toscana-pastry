"""Montos (Decimal) para los schemas de la API.

Dinero viaja siempre como Decimal y se serializa como str (RNF-P4-02):
el JSON no representa decimales exactos y el float pierde precision.
La coercion es explicita (Decimal(str(v))) para que un float de la request
no pase por su representacion binaria.
"""
from decimal import Decimal, InvalidOperation
from typing import Annotated
from pydantic import BeforeValidator, PlainSerializer


def _coerce_money(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool no es un monto valido")
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"monto invalido: {value!r}") from exc
    raise TypeError(f"tipo no aceptado para monto: {type(value).__name__}")


Money = Annotated[
    Decimal,
    BeforeValidator(_coerce_money),
    # when_used="json": en python mode (model_dump) el valor sigue siendo Decimal;
    # solo la serializacion JSON lo emite como str.
    PlainSerializer(lambda v: str(v), return_type=str, when_used="json"),
]
