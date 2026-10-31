"""Order domain entity (RF-P6-12, C1.1 / RF-P11-06/08, C6).

Fields added by Phase 5:
    payment_method      – {mercadopago, cash}
    payment_reference   – provider payment ID
    paid_at             – server-managed timestamp
    payment_status      – {pending, approved, rejected, failed} | None
    code                – TP + 6 alphanumeric chars ("mis pedidos")
    delivery_mode       – {delivery, pickup}
    delivery_address    – required if delivery; normalised to None for pickup
    coupon_code         – snapshot at confirmation
    discount_amount     – snapshot at confirmation
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class PaymentMethod(StrEnum):
    MERCADOPAGO = "mercadopago"
    CASH = "cash"


class DeliveryMode(StrEnum):
    DELIVERY = "delivery"
    PICKUP = "pickup"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


# Provider status priority: approved > rejected = failed > pending.
# A notification only applies when it outranks the order's current status.
_PAYMENT_STATUS_RANK: dict[PaymentStatus, int] = {
    PaymentStatus.PENDING: 0,
    PaymentStatus.REJECTED: 1,
    PaymentStatus.FAILED: 1,
    PaymentStatus.APPROVED: 2,
}


def overridable_payment_statuses(new: PaymentStatus) -> frozenset[PaymentStatus]:
    """Current payment statuses that a provider ``new`` status may replace.

    ``None`` (never initiated) is always replaceable and is not listed.
    """
    return frozenset(
        current
        for current, rank in _PAYMENT_STATUS_RANK.items()
        if rank < _PAYMENT_STATUS_RANK[new]
    )


class OrderValidationError(ValueError):
    """A portal order violates a business rule; ``code`` is the API detail."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class OrderStatus(StrEnum):
    NUEVO = "nuevo"
    CONFIRMADO = "confirmado"
    ENTREGADO = "entregado"
    CANCELADO = "cancelado"


@dataclass(frozen=True)
class OrderItem:
    """Line item snapshot inside an order."""

    product_id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    portion_note: str = ""

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity


_CODE_PREFIX = "TP"
_CODE_LENGTH = 6


def _generate_code() -> str:
    """Generate a unique order code (RF-P11-08: TP + 6 alphanumeric)."""
    return f"{_CODE_PREFIX}{uuid.uuid4().hex[:_CODE_LENGTH].upper()}"


@dataclass
class Order:
    """Order entity with payment tracking and portal fields.

    Invariants:
        - payment_method is immutable once status != "nuevo".
        - paid (derived: paid_at is not None) is monotonic false → true.
        - For cash orders, payment_status is always None.
        - delivery_mode=pickup normalises delivery_address to None.
        - delivery_mode=delivery with empty address → validated at portal
          creation endpoint (C6); domain default is "" for backward compat.
    """

    customer_id: str
    date: datetime.datetime
    items: list[OrderItem]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    code: str = field(default_factory=_generate_code)
    status: OrderStatus = OrderStatus.NUEVO
    payment_method: PaymentMethod = PaymentMethod.CASH
    delivery_mode: DeliveryMode = DeliveryMode.DELIVERY
    delivery_address: str = ""
    coupon_code: str | None = None
    discount_amount: Decimal | None = None
    payment_reference: str | None = None
    paid_at: datetime.datetime | None = None
    payment_status: PaymentStatus | None = None
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    def __post_init__(self) -> None:
        # Pickup normalises address to None (admin orders may omit it).
        if self.delivery_mode == DeliveryMode.PICKUP:
            object.__setattr__(self, "delivery_address", None)

    @property
    def paid(self) -> bool:
        return self.paid_at is not None

    @property
    def total(self) -> Decimal:
        return sum((item.total for item in self.items), start=Decimal("0"))

    @classmethod
    def place_portal(
        cls,
        *,
        customer_id: str,
        date: datetime.datetime,
        items: list[OrderItem],
        payment_method: PaymentMethod,
        delivery_mode: DeliveryMode,
        delivery_address: str | None,
        coupon_code: str | None = None,
        now: datetime.datetime | None = None,
    ) -> Order:
        """Build a new portal order after validating its business rules."""
        now = now or datetime.datetime.now(datetime.UTC)
        if not items:
            raise OrderValidationError("order_requires_items")
        if delivery_mode == DeliveryMode.DELIVERY and not (
            delivery_address and delivery_address.strip()
        ):
            raise OrderValidationError("delivery_requires_address")
        order_date = date.replace(tzinfo=None) if date.tzinfo else date
        today = now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        if order_date < today:
            raise OrderValidationError("date_must_be_today_or_later")
        return cls(
            customer_id=customer_id,
            date=order_date,
            items=items,
            payment_method=payment_method,
            delivery_mode=delivery_mode,
            delivery_address=delivery_address or "",
            coupon_code=coupon_code,
            created_at=now,
        )

    def confirm_payment(self, reference: str, status: PaymentStatus) -> None:
        """Mark the order as paid (server-managed, monotonic).

        Only transitions paid from False → True. Cannot revert.
        """
        if self.paid:
            raise ValueError("Order is already paid; paid is monotonic")
        if self.payment_method == PaymentMethod.CASH:
            raise ValueError("Cash orders cannot be auto-paid")
        self.paid_at = datetime.datetime.now(datetime.UTC)
        self.payment_reference = reference
        self.payment_status = status

    def mark_cash_payment(self) -> None:
        """Manual paid marking for cash orders (RF-P6-14)."""
        if self.paid:
            raise ValueError("Order is already paid")
        if self.payment_method != PaymentMethod.CASH:
            raise ValueError("mark_cash_payment is only for cash orders")
        self.paid_at = datetime.datetime.now(datetime.UTC)

    def init_mercadopago(self) -> None:
        """Switch payment method to mercadopago (portal creation)."""
        if self.status != OrderStatus.NUEVO:
            raise ValueError("payment_method is immutable after order confirmation")
        self.payment_method = PaymentMethod.MERCADOPAGO
