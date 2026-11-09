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
    pass


class BudgetAlreadyConvertedError(ValueError):
    pass


class NoBudgetChangesError(ValueError):
    pass


@dataclass(frozen=True)
class BudgetItem:

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
    iva: Decimal
    total_venta: Decimal


def compute_totals(items: Tuple[BudgetItem, ...]) -> BudgetTotals:
    subtotal = sum((item.line_selling for item in items), Decimal("0"))
    total_costos = sum((item.line_cost for item in items), Decimal("0"))
    ganancia = subtotal - total_costos
    iva = (subtotal * IVA_PCT / Decimal("100")).quantize(
        _CENT, rounding=ROUND_HALF_UP
    )
    return BudgetTotals(
        subtotal=subtotal,
        total_costos=total_costos,
        ganancia=ganancia,
        iva=iva,
        total_venta=subtotal,
    )


def unit_selling_price(
    unit_cost: Decimal,
    margin_pct: Decimal,
    price_override: Optional[Decimal] = None,
) -> Tuple[Decimal, bool]:
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
    delivery_address: Optional[str] = None
    items: Tuple[BudgetItem, ...] = ()
    margin_pct: Optional[Decimal] = None
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
    order_id: Optional[str] = None

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
        if self.status == "borrador":
            return True
        if self.sent_at is None:
            return True
        return self.updated_at > self.sent_at


def transition_to_sent(budget: Budget) -> Budget:
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
    if n < 1:
        raise ValueError(f"la secuencia debe ser >= 1: {n}")
    return f"#{n:05d}"
