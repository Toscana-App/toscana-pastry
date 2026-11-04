"""Presupuestos (Fase 7, P7/P8).

Reglas de negocio:

* El costo por unidad de cada producto se calcula contra el catalogo
  corriente (receta + insumos + settings) al crear/editar/recalcular:
  el presupuesto NO congela el desglose completo (a diferencia del
  pedido, RNF-P6-03). Guarda por item el costo y el precio de venta
  derivados en ese momento; las lecturas nunca vuelven al catalogo.
* Modo `cost_plus`: precio de venta = costo * (1 + margen/100),
  redondeado a centavos. El margen puede ser el del tenant (override
  nulo) o un override propio del presupuesto.
* Modo `manual`: cada item puede traer precio de venta personalizado
  (price_override); los items sin override usan cost_plus con el margen
  aplicado. El override de margen no se aplica a los items con precio
  manual.
* Totales (derivados, nunca persistidos): subtotal = suma de precios de
  venta; total_costos = suma de costos; ganancia = subtotal - total_costos
  (puede ser negativo); total_venta = subtotal + IVA 21%.
* Secuencia por tenant `#000NN` asignada en la creacion (RNF-P8-04),
  sin reuso tras borrado.
* Maquina de estados (RF-P8-05): borrador -> enviado (congelar version);
  reenviar desde enviado solo si hubo cambios, creando una version nueva.
* Convertir a pedido (RF-P8-02) crea un pedido `nuevo` con los mismos
  items; el pedido tiene su propio snapshot de precios (RNF-P6-03) y el
  descuento de stock ocurre al confirmarlo, no aqui.
"""
import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional, Tuple

_CENT = Decimal("0.01")
IVA_PCT = Decimal("21")


class CalculationMode(str, Enum):
    COST_PLUS = "cost_plus"
    MANUAL = "manual"


BUDGET_STATUSES = ("borrador", "enviado")


class InvalidBudgetTransitionError(ValueError):
    pass


class BudgetNotConvertibleError(ValueError):
    """Solo los presupuestos `enviado` se convierten en pedido (RF-P8-08)."""


class BudgetAlreadyConvertedError(ValueError):
    """El presupuesto ya tiene un pedido asociado (RF-P8-08)."""


class NoBudgetChangesError(ValueError):
    pass


@dataclass(frozen=True)
class BudgetItem:
    """Linea de presupuesto. `unit_cost` y `unit_selling` se calculan en
    el borde (router) contra el catalogo y se guardan: la lectura es pura.
    Money como Decimal; la API lo serializa a centavos (RF-P8-03)."""

    product_id: str
    product_name: str
    qty: int
    unit_cost: Decimal
    unit_selling: Decimal
    price_overridden: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if self.qty < 1:
            raise ValueError(f"qty de item debe ser >= 1: {self.qty}")
        if self.unit_cost < 0:
            raise ValueError("unit_cost no puede ser negativo")
        if self.unit_selling < 0:
            raise ValueError("unit_selling no puede ser negativo")

    @property
    def line_cost(self) -> Decimal:
        return (self.unit_cost * self.qty).quantize(_CENT, rounding=ROUND_HALF_UP)

    @property
    def line_selling(self) -> Decimal:
        return (self.unit_selling * self.qty).quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class BudgetTotals:
    subtotal: Decimal
    total_costos: Decimal
    ganancia: Decimal
    total_venta: Decimal


def compute_totals(items: Tuple[BudgetItem, ...]) -> BudgetTotals:
    """Totales derivados de los items. Puro: sin I/O, sin settings.
    total_venta incluye IVA 21% sobre el subtotal (RF-P7)."""
    subtotal = sum((item.line_selling for item in items), Decimal("0"))
    total_costos = sum((item.line_cost for item in items), Decimal("0"))
    ganancia = subtotal - total_costos
    total_venta = (subtotal * (Decimal("100") + IVA_PCT) / Decimal("100")).quantize(
        _CENT, rounding=ROUND_HALF_UP
    )
    return BudgetTotals(
        subtotal=subtotal,
        total_costos=total_costos,
        ganancia=ganancia,
        total_venta=total_venta,
    )


def unit_selling_price(
    unit_cost: Decimal,
    margin_pct: Decimal,
    price_override: Optional[Decimal] = None,
) -> Tuple[Decimal, bool]:
    """Precio de venta por unidad de un item.

    `price_override` no nulo = modo manual con precio personalizado.
    Si no, cost_plus: costo * (1 + margen/100), redondeo a centavos.
    """
    if price_override is not None:
        if price_override < 0:
            raise ValueError("price_override no puede ser negativo")
        return price_override, True
    price = (unit_cost * (Decimal("100") + margin_pct) / Decimal("100")).quantize(
        _CENT, rounding=ROUND_HALF_UP
    )
    return price, False


def derive_budget_items(
    inputs: Tuple[Tuple[str, str, int, Decimal, Optional[Decimal]], ...],
    margin_pct: Decimal,
) -> Tuple[Tuple[BudgetItem, ...], BudgetTotals]:
    """Deriva los items y los totales de un presupuesto.

    `inputs`: (product_id, product_name, qty, unit_cost, price_override).
    `margin_pct` es el margen YA RESUELTO (override o tenant); el router
    lo resuelve antes de llamar. Puro.
    """
    if not Decimal("0") <= margin_pct <= Decimal("200"):
        raise ValueError("El margen del presupuesto debe estar entre 0% y 200%")
    items: list = []
    for product_id, product_name, qty, unit_cost, price_override in inputs:
        selling, overridden = unit_selling_price(unit_cost, margin_pct, price_override)
        items.append(
            BudgetItem(
                product_id=product_id,
                product_name=product_name,
                qty=qty,
                unit_cost=unit_cost,
                unit_selling=selling,
                price_overridden=overridden,
            )
        )
    return tuple(items), compute_totals(tuple(items))


@dataclass
class Budget:
    customer_id: str
    customer_name: str
    customer_phone: str
    delivery_address: Optional[str] = None  # snapshot (RF-P7-06/07)
    items: Tuple[BudgetItem, ...] = ()
    margin_pct: Optional[Decimal] = None  # None = margen del tenant
    calculation_mode: CalculationMode = CalculationMode.COST_PLUS
    status: str = "borrador"
    version: int = 0
    seq: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    sent_at: Optional[datetime.datetime] = None
    order_id: Optional[str] = None  # pedido creado al convertir (RF-P8-08)

    def __post_init__(self):
        if self.status not in BUDGET_STATUSES:
            raise ValueError(f"estado invalido: {self.status!r}")
        if len(self.items) == 0:
            raise ValueError("el presupuesto requiere al menos un item")
        if self.margin_pct is not None and not Decimal("0") <= self.margin_pct <= Decimal(
            "200"
        ):
            raise ValueError("margin_pct fuera de rango 0-200")
        if self.version < 0:
            raise ValueError("version no puede ser negativa")

    @property
    def totals(self) -> BudgetTotals:
        return compute_totals(self.items)

    def has_changes_since_last_send(self) -> bool:
        """Hay cambios pendientes de reenviar si se edito despues del
        ultimo envio (RF-P8-05). Borrador: siempre 'cambiado'."""
        if self.status == "borrador":
            return True
        if self.sent_at is None:
            return True
        return self.updated_at > self.sent_at


def transition_to_sent(budget: Budget) -> Budget:
    """enviar (RF-P8-05): borrador -> enviado (version 1) o reenviar
    desde enviado con cambios (version +1). Sin cambios: 409 en la API."""
    import dataclasses

    if not budget.has_changes_since_last_send():
        raise NoBudgetChangesError("Sin cambios desde el ultimo envio")
    sent_at = datetime.datetime.now(datetime.timezone.utc)
    if budget.status == "borrador":
        new_version = 1
    else:
        new_version = budget.version + 1
    return dataclasses.replace(
        budget,
        status="enviado",
        version=new_version,
        sent_at=sent_at,
        updated_at=sent_at,
    )


def format_sequence(n: int) -> str:
    """Secuencia por tenant: #00001, #00002, ... (RNF-P8-04)."""
    if n < 1:
        raise ValueError(f"la secuencia debe ser >= 1: {n}")
    return f"#{n:05d}"
