"""Order repository (C1.2 / C6).

Mapeo ORM↔dominio y operaciones de pago + order_window singleton.
"""

from __future__ import annotations

import datetime
import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import (
    CouponORM,
    OrderItemORM,
    OrderORM,
    OrderWindowORM,
    PaymentAttemptORM,
    PaymentEventORM,
)
from domain.checkout_provider import PaymentResult
from domain.order import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    overridable_payment_statuses,
)
from domain.order_window import OrderWindow


def _to_domain(orm: OrderORM, item_orms: Sequence[OrderItemORM] | None = None) -> Order:
    """Convert OrderORM to domain Order."""
    if item_orms is None:
        item_orms = []  # type: ignore[assignment]
    items = []
    for item_orm in item_orms:
        items.append(
            OrderItem(  # type: ignore[arg-type]
                product_id=item_orm.product_id,  # type: ignore[arg-type]
                product_name=item_orm.product_name,  # type: ignore[arg-type]
                quantity=item_orm.quantity,  # type: ignore[arg-type]
                unit_price=Decimal(item_orm.unit_price),  # type: ignore[arg-type]
                portion_note=item_orm.portion_note,  # type: ignore[arg-type]
            )
        )
    return Order(  # type: ignore[arg-type]
        id=orm.id,  # type: ignore[arg-type]
        customer_id=orm.customer_id,  # type: ignore[arg-type]
        code=orm.code,  # type: ignore[arg-type]
        date=orm.date,  # type: ignore[arg-type]
        status=OrderStatus(orm.status),  # type: ignore[arg-type]
        payment_method=PaymentMethod(orm.payment_method),  # type: ignore[arg-type]
        delivery_mode=(orm.delivery_mode if orm.delivery_mode else "delivery"),  # type: ignore[arg-type]
        delivery_address=(orm.delivery_address or ""),  # type: ignore[arg-type]
        coupon_code=orm.coupon_code,  # type: ignore[arg-type]
        discount_amount=(  # type: ignore[arg-type]
            Decimal(orm.discount_amount) if orm.discount_amount else None
        ),
        payment_reference=orm.payment_reference,  # type: ignore[arg-type]
        paid_at=orm.paid_at,  # type: ignore[arg-type]
        payment_status=(  # type: ignore[arg-type]
            PaymentStatus(orm.payment_status)  # type: ignore[arg-type]
            if orm.payment_status
            else None
        ),
        created_at=orm.created_at,  # type: ignore[arg-type]
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
            code=order.code,
            date=order.date,
            status=order.status.value,
            payment_method=order.payment_method.value,
            delivery_mode=order.delivery_mode.value if hasattr(order.delivery_mode, "value") else str(order.delivery_mode),
            delivery_address=order.delivery_address or "",
            coupon_code=order.coupon_code,
            discount_amount=str(order.discount_amount) if order.discount_amount else None,
            payment_reference=order.payment_reference,
            paid_at=order.paid_at,
            payment_status=order.payment_status.value if order.payment_status else None,
            created_at=order.created_at,
        )
        self.session.add(orm)
        await self.session.flush()
        return order

    async def add(self, order: Order) -> Order:
        """Persist a new order with its line items in one transaction."""
        await self.create(order)
        for item in order.items:
            self.session.add(
                OrderItemORM(
                    id=str(uuid.uuid4()),
                    order_id=order.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    quantity=item.quantity,
                    unit_price=str(item.unit_price),
                    portion_note=item.portion_note,
                )
            )
        await self.session.commit()
        return order

    async def get_by_code(self, code: str) -> Order | None:
        """Fetch order by its portal code (RF-P11-08)."""
        result = await self.session.execute(
            select(OrderORM).where(OrderORM.code == code)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        items_result = await self.session.execute(
            select(OrderItemORM).where(OrderItemORM.order_id == orm.id)
        )
        return _to_domain(orm, items_result.scalars().all())

    async def list_by_customer(self, customer_id: str, *, page: int = 1, page_size: int = 20) -> tuple[list[Order], int]:
        """List orders for a customer (RF-P11-08). Returns (orders, total_count)."""
        count_query = select(OrderORM).where(OrderORM.customer_id == customer_id)
        count_result = await self.session.execute(count_query)
        total = len(count_result.scalars().all())

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(OrderORM)
            .where(OrderORM.customer_id == customer_id)
            .order_by(OrderORM.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        orm_list = result.scalars().all()
        orders = []
        for orm in orm_list:
            items_result = await self.session.execute(
                select(OrderItemORM).where(OrderItemORM.order_id == orm.id)
            )
            orders.append(_to_domain(orm, items_result.scalars().all()))
        return orders, total

    async def get_order_window(self) -> OrderWindow:
        """Get the singleton order window configuration."""
        result = await self.session.execute(
            select(OrderWindowORM).where(OrderWindowORM.id == "singleton")
        )
        orm = result.scalars().first()
        if orm is None:
            # Create default (open)
            orm = OrderWindowORM(
                id="singleton",
                open=True,
                reopens_at=None,
                message="",
            )
            self.session.add(orm)
            await self.session.flush()
        return OrderWindow(  # type: ignore[arg-type]
            open=orm.open,  # type: ignore[arg-type]
            reopens_at=orm.reopens_at,  # type: ignore[arg-type]
            message=orm.message,  # type: ignore[arg-type]
        )

    async def update_order_window(self, window: OrderWindow) -> None:
        """Update the singleton order window configuration."""
        result = await self.session.execute(
            select(OrderWindowORM).where(OrderWindowORM.id == "singleton")
        )
        orm = result.scalars().first()
        if orm is None:
            orm = OrderWindowORM(  # type: ignore[arg-type]
                id="singleton",
                open=window.open,
                reopens_at=window.reopens_at,
                message=window.message,
            )
            self.session.add(orm)
        else:
            orm.open = window.open  # type: ignore[assignment]
            orm.reopens_at = window.reopens_at  # type: ignore[assignment]
            orm.message = window.message  # type: ignore[assignment]
        await self.session.commit()

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
        orm.payment_reference = reference  # type: ignore[assignment]
        orm.payment_status = status.value  # type: ignore[assignment]
        if paid_at is not None:
            orm.paid_at = paid_at  # type: ignore[assignment]
        await self.session.commit()
        return _to_domain(orm)

    async def mark_paid_at(
        self, order_id: str, paid_at: datetime.datetime
    ) -> bool:
        """Set only ``paid_at`` (cash orders keep ``payment_status`` null).

        Guarded on ``paid_at IS NULL`` so ``paid`` stays monotonic.
        """
        result = await self.session.execute(
            update(OrderORM)
            .where(OrderORM.id == order_id, OrderORM.paid_at.is_(None))
            .values(paid_at=paid_at)
        )
        await self.session.commit()
        return result.rowcount == 1  # type: ignore[attr-defined]

    async def claim_payment_pending(self, order_id: str) -> bool:
        """Atomically move an unpaid order with no payment to ``pending``.

        Row-guarded: of several concurrent initiations only one claims.
        """
        result = await self.session.execute(
            update(OrderORM)
            .where(
                OrderORM.id == order_id,
                OrderORM.paid_at.is_(None),
                OrderORM.payment_status.is_(None),
            )
            .values(payment_status=PaymentStatus.PENDING.value)
        )
        await self.session.commit()
        return result.rowcount == 1  # type: ignore[attr-defined]

    async def release_payment_pending(self, order_id: str) -> None:
        """Undo a claim whose preference was never created."""
        await self.session.execute(
            update(OrderORM)
            .where(
                OrderORM.id == order_id,
                OrderORM.payment_status == PaymentStatus.PENDING.value,
                OrderORM.payment_reference.is_(None),
            )
            .values(payment_status=None)
        )
        await self.session.commit()

    async def expire_pending_payment(self, order_id: str) -> bool:
        """Cancel an unpaid order whose payment is still pending and release its coupon use.

        The caller decides expiry (``domain.order.is_payment_expired``). The
        update is row-guarded (nuevo + pending + unpaid) so a concurrent
        webhook that already approved the payment wins. Returns True when this
        call cancelled the order.
        """
        coupon_code = (
            await self.session.execute(
                select(OrderORM.coupon_code).where(OrderORM.id == order_id)
            )
        ).scalar_one_or_none()
        result = await self.session.execute(
            update(OrderORM)
            .where(
                OrderORM.id == order_id,
                OrderORM.status == OrderStatus.NUEVO.value,
                OrderORM.paid_at.is_(None),
                OrderORM.payment_status == PaymentStatus.PENDING.value,
            )
            .values(
                status=OrderStatus.CANCELADO.value,
                payment_status=PaymentStatus.FAILED.value,
            )
        )
        cancelled = result.rowcount == 1  # type: ignore[attr-defined]
        if cancelled and coupon_code:
            await self.session.execute(
                update(CouponORM)
                .where(
                    func.accent_fold(CouponORM.code) == accent_fold(coupon_code),
                    CouponORM.uses > 0,
                )
                .values(uses=CouponORM.uses - 1)
            )
        await self.session.commit()
        return cancelled

    async def apply_payment_event(
        self,
        event_id: str,
        order_id: str,
        provider_payment_id: str,
        status: PaymentStatus,
        paid_at: datetime.datetime,
    ) -> bool:
        """Record the event and apply its status in ONE transaction.

        The event is inserted first (primary key = dedupe); a duplicate
        returns False with no effect. The order update is conditional on the
        status priority (approved > rejected = failed > pending) and, for
        ``approved``, on ``paid_at IS NULL``; cash orders are never touched.
        """
        self.session.add(
            PaymentEventORM(
                id=event_id,
                provider_payment_id=provider_payment_id,
                order_id=order_id,
                status=status.value,
                created_at=datetime.datetime.now(datetime.UTC),
            )
        )
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            return False

        replaceable = [s.value for s in overridable_payment_statuses(status)]
        conditions = [
            OrderORM.id == order_id,
            OrderORM.payment_method != PaymentMethod.CASH.value,
            or_(
                OrderORM.payment_status.is_(None),
                OrderORM.payment_status.in_(replaceable),
            ),
        ]
        values: dict[str, object] = {
            "payment_reference": provider_payment_id,
            "payment_status": status.value,
        }
        if status == PaymentStatus.APPROVED:
            conditions.append(OrderORM.paid_at.is_(None))
            values["paid_at"] = paid_at
        await self.session.execute(update(OrderORM).where(*conditions).values(**values))
        await self.session.commit()
        return True

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

    async def get_payment_attempt(
        self, order_id: str, idempotency_key: str
    ) -> PaymentResult | None:
        """Saved POST /orders/{id}/payment response for this key, if any."""
        orm = await self.session.get(PaymentAttemptORM, f"{order_id}:{idempotency_key}")
        if orm is None:
            return None
        return PaymentResult(reference=orm.reference, checkout_url=orm.checkout_url)  # type: ignore[arg-type]

    async def save_payment_attempt(
        self, order_id: str, idempotency_key: str, result: PaymentResult
    ) -> PaymentResult:
        """Store the response for this key; on a concurrent duplicate, return
        the one that was stored first."""
        self.session.add(
            PaymentAttemptORM(
                id=f"{order_id}:{idempotency_key}",
                order_id=order_id,
                reference=result.reference,
                checkout_url=result.checkout_url,
            )
        )
        await self.session.execute(
            update(OrderORM)
            .where(
                OrderORM.id == order_id,
                OrderORM.paid_at.is_(None),
                OrderORM.payment_status == PaymentStatus.PENDING.value,
            )
            .values(payment_reference=result.reference)
        )
        try:
            await self.session.commit()
            return result
        except IntegrityError:
            await self.session.rollback()
            saved = await self.get_payment_attempt(order_id, idempotency_key)
            return saved or result

    async def get_payment_event(self, event_id: str) -> bool:
        """Check if a payment event already exists (dedupe).

        Returns True if the event exists, False otherwise.
        """
        return await self.session.get(PaymentEventORM, event_id) is not None
