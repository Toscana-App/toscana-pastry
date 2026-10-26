"""Order repository (C1.2).

Mapeo ORM↔dominio y operaciones de pago.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import OrderItemORM, OrderORM, PaymentEventORM
from domain.order import Order, OrderItem, OrderStatus, PaymentMethod, PaymentStatus


def _to_domain(orm: OrderORM, item_orms: list[OrderItemORM] | None = None) -> Order:
    """Convert OrderORM to domain Order."""
    if item_orms is None:
        item_orms = []  # type: ignore[assignment]
    items = []
    for item_orm in item_orms:
        items.append(
            OrderItem(
                product_id=item_orm.product_id,
                product_name=item_orm.product_name,
                quantity=item_orm.quantity,
                unit_price=Decimal(item_orm.unit_price),
                portion_note=item_orm.portion_note,
            )
        )
    return Order(
        id=orm.id,
        customer_id=orm.customer_id,
        date=orm.date,
        status=OrderStatus(orm.status),  # type: ignore[arg-type]
        payment_method=PaymentMethod(orm.payment_method),  # type: ignore[arg-type]
        payment_reference=orm.payment_reference,
        paid_at=orm.paid_at,
        payment_status=(
            PaymentStatus(orm.payment_status)  # type: ignore[arg-type]
            if orm.payment_status
            else None
        ),
        created_at=orm.created_at,
        items=items,
    )


class SQLOrderRepository:
    """SQL repository for Order entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, order_id: str) -> Order | None:
        result = await self.session.execute(
            select(OrderORM).where(OrderORM.id == order_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None

        # Fetch order items separately to avoid lazy-load issues
        items_result = await self.session.execute(
            select(OrderItemORM).where(OrderItemORM.order_id == order_id)
        )
        item_orms = items_result.scalars().all()

        return _to_domain(orm, item_orms)

    async def create(self, order: Order) -> Order:
        orm = OrderORM(
            id=order.id,
            customer_id=order.customer_id,
            date=order.date,
            status=order.status.value,
            payment_method=order.payment_method.value,
            payment_reference=order.payment_reference,
            paid_at=order.paid_at,
            payment_status=order.payment_status.value if order.payment_status else None,
            created_at=order.created_at,
        )
        self.session.add(orm)
        await self.session.flush()
        return order

    async def update_payment_status(
        self,
        order_id: str,
        reference: str,
        status: PaymentStatus,
        paid_at: datetime.datetime | None = None,
    ) -> Order | None:
        """Update payment fields on an order in a single transaction."""
        result = await self.session.execute(
            select(OrderORM).where(OrderORM.id == order_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.payment_reference = reference
        orm.payment_status = status.value
        if paid_at is not None:
            orm.paid_at = paid_at
        await self.session.commit()
        return _to_domain(orm)

    async def record_payment_event(
        self, event_id: str, order_id: str, provider_payment_id: str, status: PaymentStatus
    ) -> bool:
        """Record a payment event for dedupe.

        Returns True if the event was newly inserted, False if it was a
        duplicate (already exists).
        """
        event = PaymentEventORM(
            id=event_id,
            provider_payment_id=provider_payment_id,
            order_id=order_id,
            status=status.value,
            created_at=datetime.datetime.now(datetime.UTC),
        )
        self.session.add(event)
        try:
            await self.session.commit()
            return True
        except Exception:
            await self.session.rollback()
            return False

    async def get_payment_event(self, provider_payment_id: str) -> bool:
        """Check if a payment event already exists (dedupe).

        Returns True if the event exists, False otherwise.
        """
        result = await self.session.execute(
            select(PaymentEventORM).where(
                PaymentEventORM.provider_payment_id == provider_payment_id
            )
        )
        return result.scalars().first() is not None
