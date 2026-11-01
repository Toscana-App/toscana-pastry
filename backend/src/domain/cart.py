"""Dominio del carrito (RF-P11-03/14, C4).

Modulo puro: Decimal adentro, Decimal afuera. Sin I/O, sin frameworks.

Reglas:
- Max 50 lineas, qty 1-999 (RF-P11-03).
- El precio NO se persiste como fuente: el carrito guarda product_id + qty
  y el unit_price se deriva en cada lectura segun la audiencia
  (RNF-P11-03).
- El descuento se calcula sobre el subtotal de la audiencia, ANTES del
  redondeo del motor; el redondeo (round_step) se aplica sobre el total
  post-descuento (RF-P11-14).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from domain.coupon import Coupon
from domain.pricing import round_to_step

MAX_CART_LINES = 50
MIN_QTY = 1
MAX_QTY = 999

_CENT = Decimal("0.01")
_HUNDRED = Decimal(100)


@dataclass(frozen=True)
class CartLine:
    """Linea del carrito con el precio derivado para la audiencia."""

    product_id: str
    product_name: str
    unit_price: Decimal
    qty: int

    @property
    def total(self) -> Decimal:
        return (self.unit_price * self.qty).quantize(
            _CENT, rounding=ROUND_HALF_UP
        )


@dataclass(frozen=True)
class CartTotals:
    """Subtotal, descuento y total final (post-descuento, redondeado)."""

    subtotal: Decimal
    discount_amount: Decimal
    final: Decimal


def compute_discount(
    total: Decimal, coupon: Coupon | None
) -> Decimal:
    """Descuento del cupon sobre el total (nunca mayor al total)."""
    if coupon is None:
        return Decimal("0.00")
    if coupon.type == "percent":
        return (total * coupon.value / _HUNDRED).quantize(
            _CENT, rounding=ROUND_HALF_UP
        )
    return min(coupon.value, total).quantize(_CENT, rounding=ROUND_HALF_UP)


def cart_totals(
    lines: list[CartLine],
    coupon: Coupon | None,
    round_step: Decimal,
) -> CartTotals:
    """Subtotal + descuento + total final redondeado al paso del motor."""
    subtotal = sum((line.total for line in lines), Decimal("0.00"))
    discount = compute_discount(subtotal, coupon)
    final = round_to_step(subtotal - discount, round_step)
    return CartTotals(
        subtotal=subtotal,
        discount_amount=discount,
        final=final,
    )


def _naive_utc(
    dt: datetime.datetime | None,
) -> datetime.datetime | None:
    """Normaliza a naive UTC (mismo patron que domain.coupon): SQLite
    devuelve naive en el round-trip y mezclar naive/aware rompe la
    comparacion de la ventana."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(datetime.UTC).replace(tzinfo=None)
    return dt


def validate_coupon_for_cart(
    coupon: Coupon, now: datetime.datetime
) -> str | None:
    """Valida un cupon para aplicarlo al carrito.

    Devuelve None si es aplicable, o el codigo de error 422:
      - ``coupon_inactive``      → status=paused o antes de valid_from
      - ``coupon_expired``       → despues de valid_until
      - ``coupon_limit_reached`` → uses >= max_uses

    El orden de validacion (inactivo > vencido > max_uses) define la
    prioridad de los codigos cuando fallan varios a la vez.
    """
    if coupon.status != "active":
        return "coupon_inactive"
    valid_from = _naive_utc(coupon.valid_from)
    valid_until = _naive_utc(coupon.valid_until)
    now_naive = _naive_utc(now)
    assert now_naive is not None  # `now` es un parametro obligatorio
    if valid_from is not None and now_naive < valid_from:
        return "coupon_inactive"
    if valid_until is not None and now_naive > valid_until:
        return "coupon_expired"
    if coupon.max_uses is not None and coupon.uses >= coupon.max_uses:
        return "coupon_limit_reached"
    return None
