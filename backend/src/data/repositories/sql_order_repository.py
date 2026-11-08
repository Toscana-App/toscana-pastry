
from __future__ import annotations

import dataclasses
import datetime
import json
import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from data.accent import accent_fold
from data.models import (
    CouponORM,
    IngredientORM,
    OrderEventORM,
    OrderItemORM,
    OrderORM,
    OrderWindowORM,
    PaymentAttemptORM,
    PaymentEventORM,
    StockMovementORM,
)
from domain.checkout_provider import PaymentResult
from domain.order import (
    _generate_code,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    overridable_payment_statuses,
)
from domain.models import Ingredient, StockMovement
from domain.order_window import OrderWindow
from domain.orders import Order as P6Order
from domain.orders import (
    OrderItem as P6OrderItem,
    OrderItemSnapshot,
    OrderItemSnapshotLine,
    OrderNotEditableError,
)
from domain.use_cases.transition_order_status import TransitionOrderStatus


def _to_domain(orm: OrderORM, item_orms: Sequence[OrderItemORM] | None = None) -> Order:
    if item_orms is None:
        item_orms = []
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
        code=orm.code,
        date=orm.date,
        status=OrderStatus(orm.status),
        payment_method=PaymentMethod(orm.payment_method),
        delivery_mode=(orm.delivery_mode if orm.delivery_mode else "delivery"),
        delivery_address=(orm.delivery_address or ""),
        coupon_code=orm.coupon_code,
        discount_amount=(
            Decimal(orm.discount_amount) if orm.discount_amount else None
        ),
        payment_reference=orm.payment_reference,
        paid_at=orm.paid_at,
        payment_status=(
            PaymentStatus(orm.payment_status)
            if orm.payment_status
            else None
        ),
        created_at=orm.created_at,
        items=items,
    )





def _snapshot_to_json(snapshot: OrderItemSnapshot) -> str:
    return json.dumps(
        {
            "lines": [
                {
                    "ingredient_id": line.ingredient_id,
                    "ingredient_name": line.ingredient_name,
                    "qty": str(line.qty),
                    "unit": line.unit,
                    "cost": str(line.cost),
                    "is_missing": line.is_missing,
                }
                for line in snapshot.lines
            ],
            "materials": str(snapshot.materials),
            "waste": str(snapshot.waste),
            "materials_con_merma": str(snapshot.materials_con_merma),
            "labor": str(snapshot.labor),
            "gas": str(snapshot.gas),
            "base": str(snapshot.base),
            "margin_pct": str(snapshot.margin_pct),
            "final": str(snapshot.final),
            "rounded": str(snapshot.rounded),
            "missing": list(snapshot.missing),
        }
    )


def _json_to_snapshot(raw: str) -> OrderItemSnapshot:
    data = json.loads(raw)
    return OrderItemSnapshot(
        lines=tuple(
            OrderItemSnapshotLine(
                ingredient_id=line["ingredient_id"],
                ingredient_name=line["ingredient_name"],
                qty=Decimal(line["qty"]),
                unit=line["unit"],
                cost=Decimal(line["cost"]),
                is_missing=line.get("is_missing", False),
            )
            for line in data.get("lines", [])
        ),
        materials=Decimal(data["materials"]),
        waste=Decimal(data["waste"]),
        materials_con_merma=Decimal(data["materials_con_merma"]),
        labor=Decimal(data["labor"]),
        gas=Decimal(data["gas"]),
        base=Decimal(data["base"]),
        margin_pct=Decimal(data["margin_pct"]),
        final=Decimal(data["final"]),
        rounded=Decimal(data["rounded"]),
        missing=tuple(data.get("missing", [])),
    )





def _as_date(value: datetime.date | datetime.datetime) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    return value


def _as_datetime(
    value: datetime.date | datetime.datetime, end_of_day: bool = False
) -> datetime.datetime:
    if isinstance(value, datetime.datetime):
        return value
    time = datetime.time.max if end_of_day else datetime.time.min
    return datetime.datetime.combine(value, time, tzinfo=datetime.UTC)

def _order_to_domain(orm: OrderORM) -> P6Order:
    items = tuple(
        P6OrderItem(
            product_id=item.product_id,
            qty=item.qty,
            portions=item.portions,
            note=item.note,
            product_name=item.product_name,
            id=item.id,
            position=item.position,
        )
        for item in orm.order_items
    )
    snapshots = {
        item.id: (
            _json_to_snapshot(item.snapshot)
            if item.snapshot
            else OrderItemSnapshot()
        )
        for item in orm.order_items
    }
    return P6Order(
        customer_id=orm.customer_id,
        customer_name=orm.customer_name,
        customer_phone=orm.customer_phone,
        date=_as_date(orm.date),
        status=orm.status,
        margin_pct=Decimal(orm.margin_pct) if orm.margin_pct is not None else None,
        created_at=orm.created_at,
        updated_at=orm.updated_at or orm.created_at,
        whatsapp_sent_at=orm.whatsapp_sent_at,
        id=orm.id,
        paid=orm.paid_at is not None,
        payment_method=str(orm.payment_method or "cash"),
        items=items,
        snapshots=snapshots,
    )


class SQLOrderRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, order_id: str) -> Order | None:
        result = await self.session.execute(
            select(OrderORM).where(OrderORM.id == order_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None

        items_result = await self.session.execute(
            select(OrderItemORM).where(OrderItemORM.order_id == order_id)
        )
        item_orms = items_result.scalars().all()

        return _to_domain(orm, item_orms)

    async def create(self, order: Order) -> Order:
        orm = OrderORM(
            id=order.id,
            customer_id=order.customer_id,
            customer_name=order.customer_name or None,
            customer_phone=order.customer_phone or None,
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
            updated_at=order.created_at,
        )
        self.session.add(orm)
        await self.session.flush()
        return order

    async def add(self, order: Order) -> Order:
        await self.create(order)
        for index, item in enumerate(order.items):
            snapshot = order.snapshots.get(item.id)
            self.session.add(
                OrderItemORM(
                    id=item.id,
                    order_id=order.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    quantity=item.quantity,
                    unit_price=str(item.unit_price),
                    portion_note=item.portion_note,
                    qty=item.quantity,
                    portions=item.portions or None,
                    note=item.portion_note,
                    position=index,
                    snapshot=_snapshot_to_json(snapshot) if snapshot is not None else None,
                )
            )
        await self.session.commit()
        return order

    async def get_by_code(self, code: str) -> Order | None:
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
        result = await self.session.execute(
            select(OrderWindowORM).where(OrderWindowORM.id == "singleton")
        )
        orm = result.scalars().first()
        if orm is None:
            orm = OrderWindowORM(
                id="singleton",
                open=True,
                reopens_at=None,
                message="",
            )
            self.session.add(orm)
            await self.session.flush()
        return OrderWindow(
            open=orm.open,
            reopens_at=orm.reopens_at,
            message=orm.message,
        )

    async def update_order_window(self, window: OrderWindow) -> None:
        result = await self.session.execute(
            select(OrderWindowORM).where(OrderWindowORM.id == "singleton")
        )
        orm = result.scalars().first()
        if orm is None:
            orm = OrderWindowORM(
                id="singleton",
                open=window.open,
                reopens_at=window.reopens_at,
                message=window.message,
            )
            self.session.add(orm)
        else:
            orm.open = window.open
            orm.reopens_at = window.reopens_at
            orm.message = window.message
        await self.session.commit()

    async def update_payment_status(
        self,
        order_id: str,
        reference: str,
        status: PaymentStatus,
        paid_at: datetime.datetime | None = None,
    ) -> Order | None:
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

    async def mark_paid_at(
        self, order_id: str, paid_at: datetime.datetime
    ) -> bool:
        result = await self.session.execute(
            update(OrderORM)
            .where(OrderORM.id == order_id, OrderORM.paid_at.is_(None))
            .values(paid_at=paid_at)
        )
        await self.session.commit()
        return result.rowcount == 1

    async def claim_payment_pending(self, order_id: str) -> bool:
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
        return result.rowcount == 1

    async def release_payment_pending(self, order_id: str) -> None:
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
        cancelled = result.rowcount == 1
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
        orm = await self.session.get(PaymentAttemptORM, f"{order_id}:{idempotency_key}")
        if orm is None:
            return None
        return PaymentResult(reference=orm.reference, checkout_url=orm.checkout_url)

    async def save_payment_attempt(
        self, order_id: str, idempotency_key: str, result: PaymentResult
    ) -> PaymentResult:
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
        return await self.session.get(PaymentEventORM, event_id) is not None



    async def get_full(self, order_id: str) -> Optional[P6Order]:
        result = await self.session.execute(
            select(OrderORM)
            .where(OrderORM.id == order_id)
            .options(selectinload(OrderORM.order_items))
        )
        orm = result.scalars().first()
        return _order_to_domain(orm) if orm else None

    async def list_orders(
        self,
        status: Optional[str],
        customer_id: Optional[str],
        q: Optional[str],
        date_from: Optional[datetime.date],
        date_to: Optional[datetime.date],
        page: int,
        page_size: int,
        paid: Optional[bool] = None,
    ) -> Tuple[List[P6Order], int]:
        filters = []
        if status:
            filters.append(OrderORM.status == status)
        if customer_id:
            filters.append(OrderORM.customer_id == customer_id)
        if paid is not None:
            filters.append(
                OrderORM.paid_at.isnot(None) if paid else OrderORM.paid_at.is_(None)
            )
        if q and q.strip():
            from data.accent import accent_fold

            folded = accent_fold(q) or q
            filters.append(
                func.accent_fold(OrderORM.customer_name).like(f"%{folded}%")
            )
        if date_from is not None:
            filters.append(OrderORM.date >= _as_datetime(date_from))
        if date_to is not None:
            filters.append(OrderORM.date <= _as_datetime(date_to, end_of_day=True))
        total = (
            await self.session.execute(
                select(func.count()).select_from(OrderORM).where(*filters)
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(OrderORM)
                .where(*filters)
                .options(selectinload(OrderORM.order_items))
                .order_by(OrderORM.created_at.desc(), OrderORM.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_order_to_domain(orm) for orm in rows], total


    async def create_full(self, order: P6Order) -> P6Order:
        now = datetime.datetime.now(datetime.UTC)
        orm = OrderORM(
            id=order.id,
            code=_generate_code(),
            customer_id=order.customer_id,
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
            date=_as_datetime(order.date),
            status=order.status,
            margin_pct=str(order.margin_pct) if order.margin_pct is not None else None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(orm)
        for index, item in enumerate(order.items):
            self.session.add(
                OrderItemORM(
                    id=item.id,
                    order_id=order.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    quantity=item.qty,
                    qty=item.qty,
                    portions=item.portions,
                    note=item.note,
                    position=index,
                    snapshot=_snapshot_to_json(order.snapshots[item.id]),
                )
            )
        await self.session.commit()
        return dataclasses.replace(order, created_at=now, updated_at=now)

    async def update_full(self, order: P6Order) -> Optional[P6Order]:
        orm = await self._lock_order(order.id)
        if orm is None:
            return None
        if orm.status != "nuevo":
            current = orm.status
            await self.session.rollback()
            raise OrderNotEditableError(current)
        orm.customer_id = order.customer_id
        orm.customer_name = order.customer_name
        orm.customer_phone = order.customer_phone
        orm.date = _as_datetime(order.date)
        orm.margin_pct = (
            str(order.margin_pct) if order.margin_pct is not None else None
        )
        orm.updated_at = datetime.datetime.now(datetime.UTC)
        for old in list(orm.order_items):
            await self.session.delete(old)
        for index, item in enumerate(order.items):
            self.session.add(
                OrderItemORM(
                    id=item.id,
                    order_id=order.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    quantity=item.qty,
                    qty=item.qty,
                    portions=item.portions,
                    note=item.note,
                    position=index,
                    snapshot=_snapshot_to_json(order.snapshots[item.id]),
                )
            )
        await self.session.commit()
        return order


    async def confirm(self, order: P6Order) -> P6Order:
        return await TransitionOrderStatus(self).execute(order.id, "confirmado")

    async def cancel(self, order: P6Order) -> P6Order:
        return await TransitionOrderStatus(self).execute(order.id, "cancelado")

    async def mark_delivered(self, order: P6Order) -> P6Order:
        return await TransitionOrderStatus(self).execute(order.id, "entregado")


    async def lock_order(self, order_id: str) -> Optional[P6Order]:
        orm = await self._lock_order(order_id)
        return _order_to_domain(orm) if orm is not None else None

    async def lock_ingredients(
        self, ingredient_ids: List[str]
    ) -> Dict[str, Ingredient]:
        rows = await self._lock_ingredients(ingredient_ids)
        return {i: _ingredient_to_domain(row) for i, row in rows.items()}

    async def apply_movements(
        self, changes: List[Tuple[Ingredient, StockMovement]]
    ) -> None:
        for updated, movement in changes:
            row = await self.session.get(IngredientORM, updated.id)
            row.stock_qty = str(updated.stock_qty)
            self.session.add(
                StockMovementORM(
                    id=movement.id,
                    ingredient_id=movement.ingredient_id,
                    qty_delta=str(movement.qty_delta),
                    reason=movement.reason,
                    ref=movement.ref,
                    created_at=movement.created_at,
                )
            )

    async def set_status(self, order_id: str, status: str) -> None:
        orm = await self.session.get(OrderORM, order_id)
        orm.status = status
        orm.updated_at = datetime.datetime.now(datetime.UTC)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


    async def mark_whatsapp_sent(
        self, order: P6Order, sent_at: datetime
    ) -> None:
        orm = await self._load_orm(order.id)
        if orm is None:
            return
        orm.whatsapp_sent_at = sent_at
        self.session.add(
            OrderEventORM(
                id=str(uuid.uuid4()),
                order_id=order.id,
                type="whatsapp_link",
                payload="",
                created_at=sent_at,
            )
        )
        await self.session.commit()


    async def _lock_order(self, order_id: str) -> Optional[OrderORM]:
        result = await self.session.execute(
            select(OrderORM)
            .where(OrderORM.id == order_id)
            .options(selectinload(OrderORM.order_items))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def _lock_ingredients(
        self, ingredient_ids: List[str]
    ) -> Dict[str, IngredientORM]:
        if not ingredient_ids:
            return {}
        rows = (
            await self.session.execute(
                select(IngredientORM)
                .where(
                    IngredientORM.id.in_(ingredient_ids),
                    IngredientORM.deleted_at.is_(None),
                )
                .order_by(IngredientORM.id)
                .with_for_update()
            )
        ).scalars().all()
        return {row.id: row for row in rows}

    async def _load_orm(self, order_id: str) -> Optional[OrderORM]:
        result = await self.session.execute(
            select(OrderORM).where(OrderORM.id == order_id)
        )
        return result.scalars().first()


def _ingredient_to_domain(orm: IngredientORM):
    from domain.models import Ingredient

    return Ingredient(
        name=orm.name,
        unit=orm.unit,
        price_per_unit=Decimal(orm.price_per_unit),
        stock_qty=Decimal(orm.stock_qty),
        low_stock_threshold=Decimal(orm.low_stock_threshold),
        id=orm.id,
        deleted_at=orm.deleted_at,
    )
