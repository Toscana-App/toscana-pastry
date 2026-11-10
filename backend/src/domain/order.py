
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


_PAYMENT_STATUS_RANK: dict[PaymentStatus, int] = {
    PaymentStatus.PENDING: 0,
    PaymentStatus.REJECTED: 1,
    PaymentStatus.FAILED: 1,
    PaymentStatus.APPROVED: 2,
}


def overridable_payment_statuses(new: PaymentStatus) -> frozenset[PaymentStatus]:
    return frozenset(
        current
        for current, rank in _PAYMENT_STATUS_RANK.items()
        if rank < _PAYMENT_STATUS_RANK[new]
    )


PAYMENT_EXPIRY = datetime.timedelta(hours=24)


class OrderValidationError(ValueError):

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

    product_id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    portion_note: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    portions: int = 0

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity


_CODE_PREFIX = "TP"
_CODE_LENGTH = 6


def _generate_code() -> str:
    return f"{_CODE_PREFIX}{uuid.uuid4().hex[:_CODE_LENGTH].upper()}"


@dataclass
class Order:

    customer_id: str
    date: datetime.datetime
    items: list[OrderItem]
    customer_name: str = ""
    customer_phone: str = ""
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
    snapshots: dict = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
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
        customer_name: str = "",
        customer_phone: str = "",
        coupon_code: str | None = None,
        now: datetime.datetime | None = None,
    ) -> Order:
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
            customer_name=customer_name,
            customer_phone=customer_phone,
            payment_method=payment_method,
            delivery_mode=delivery_mode,
            delivery_address=delivery_address or "",
            coupon_code=coupon_code,
            created_at=now,
        )

    def confirm_payment(self, reference: str, status: PaymentStatus) -> None:
        """Snapshot the approved payment: paid_at + payment_reference.

        payment_reference invariants (I1-I3):
        I1: payment_reference is non-null only once the order is paid
            (paid_at non-null); paid is monotonic.
        I2: For MercadoPago orders, payment_reference is the reference of
            the approved attempt.
        I3: Non-approved payment events (pending/rejected/failed) never set
            payment_reference nor paid_at; use register_payment_event.
        """
        if self.paid:
            raise ValueError("Order is already paid; paid is monotonic")
        if self.payment_method == PaymentMethod.CASH:
            raise ValueError("Cash orders cannot be auto-paid")
        if status is not PaymentStatus.APPROVED:
            raise ValueError("confirm_payment only applies to approved payments")
        self.paid_at = datetime.datetime.now(datetime.UTC)
        self.payment_reference = reference
        self.payment_status = status

    def register_payment_event(self, status: PaymentStatus) -> None:
        """Record a non-approved provider event: payment_status only."""
        if self.paid:
            raise ValueError("Order is already paid; paid is monotonic")
        if self.payment_method == PaymentMethod.CASH:
            raise ValueError("Cash orders have no provider payment status")
        if status is PaymentStatus.APPROVED:
            raise ValueError("Use confirm_payment to register approved payments")
        self.payment_status = status

    def mark_cash_payment(self) -> None:
        if self.paid:
            raise ValueError("Order is already paid")
        if self.payment_method != PaymentMethod.CASH:
            raise ValueError("mark_cash_payment is only for cash orders")
        self.paid_at = datetime.datetime.now(datetime.UTC)

    def init_mercadopago(self) -> None:
        if self.status != OrderStatus.NUEVO:
            raise ValueError("payment_method is immutable after order confirmation")
        self.payment_method = PaymentMethod.MERCADOPAGO


def is_payment_expired(order: Order, now: datetime.datetime) -> bool:
    if (
        order.payment_method != PaymentMethod.MERCADOPAGO
        or order.status != OrderStatus.NUEVO
        or order.paid
        or order.payment_status != PaymentStatus.PENDING
    ):
        return False
    created_at = order.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=datetime.UTC)
    return now - created_at >= PAYMENT_EXPIRY
