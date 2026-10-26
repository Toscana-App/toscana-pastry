"""Order domain entity (RF-P6-12, C1.1).

Extends the base Order with payment fields:
    payment_method  – {mercadopago, cash}
    payment_reference – provider payment ID (server-managed)
    paid_at           – server-managed timestamp
    payment_status    – {pending, approved, rejected, failed} | None
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


class PaymentStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


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


@dataclass
class Order:
    """Order entity with payment tracking (RF-P6-12).

    Invariants:
        - payment_method is immutable once status != "nuevo".
        - paid (derived: paid_at is not None) is monotonic false → true.
        - For cash orders, payment_status is always None.
    """

    customer_id: str
    date: datetime.datetime
    items: list[OrderItem]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: OrderStatus = OrderStatus.NUEVO
    payment_method: PaymentMethod = PaymentMethod.CASH
    payment_reference: str | None = None
    paid_at: datetime.datetime | None = None
    payment_status: PaymentStatus | None = None
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @property
    def paid(self) -> bool:
        return self.paid_at is not None

    @property
    def total(self) -> Decimal:
        return sum((item.total for item in self.items), start=Decimal("0"))

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
