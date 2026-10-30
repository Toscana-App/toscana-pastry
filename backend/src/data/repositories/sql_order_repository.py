"""Order repository (C1.2 / C6 + Fase 6, P6).

Dos conjuntos de operaciones sobre la misma tabla unificada (OrderORM):
- C1: portal (codigo, pagos, order_window singleton).
- P6: admin (snapshots congelados, transiciones de estado, stock,
  WhatsApp). Los metodos P6 usan los nombres *_full/list_orders para no
  chocar con los de C1.
"""

# pyright: reportArgumentType=false, reportIndexIssue=false, reportAssignmentType=false

from __future__ import annotations

import dataclasses
import datetime
import json
import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import (
    IngredientORM,
    OrderEventORM,
    OrderItemORM,
    OrderORM,
    OrderWindowORM,
    PaymentEventORM,
    StockMovementORM,
)
from domain.models import Ingredient
from domain.order_pricing import plan_order_deductions
from domain.orders import (
    InsufficientOrderStockError,
)
from domain.stock import apply_movement

from domain.order import Order, OrderItem, OrderStatus, PaymentMethod, PaymentStatus
from domain.order import _generate_code
from domain.order_window import OrderWindow
from domain.orders import (
    ORDER_TRANSITIONS,
    Order as P6Order,
    OrderItem as P6OrderItem,
    OrderItemSnapshot,
    OrderItemSnapshotLine,
)


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

    # ─── P6 (admin): listado, snapshots, transiciones, stock ─────────

    async def list_orders(
        self,
        status: str | None,
        customer_id: str | None,
        q: str | None,
        date_from: object | None,
        date_to: object | None,
        page: int,
        page_size: int,
    ) -> tuple[list[P6Order], int]:
        stmt = select(OrderORM).options(selectinload(OrderORM.order_items))
        conds = []
        if q:
            folded = accent_fold(q)
            ors = [
                func.accent_fold(OrderORM.customer_name).like(f"%{folded}%"),
                OrderORM.customer_phone.like(f"%{folded}%"),
            ]
            conds.append(or_(*ors))
        if status:
            conds.append(OrderORM.status == status)
        if customer_id:
            conds.append(OrderORM.customer_id == customer_id)
        if date_from is not None:
            conds.append(OrderORM.date >= date_from)
        if date_to is not None:
            conds.append(OrderORM.date <= date_to)
        if conds:
            stmt = stmt.where(*conds)
        count_stmt = select(func.count()).select_from(OrderORM)
        if conds:
            count_stmt = count_stmt.where(*conds)
        total = (
            await self.session.execute(count_stmt)
        ).scalar_one()
        rows = (
            (await self.session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
        )
        return [_order_to_domain_p6(row) for row in rows], total

    async def get_full(self, order_id: str) -> P6Order | None:
        orm = await self._load_orm_p6(order_id)
        if orm is None:
            return None
        return _order_to_domain_p6(orm)

    async def create_full(self, order: P6Order) -> P6Order:
        try:
            now = datetime.datetime.now(datetime.UTC)
            orm = OrderORM(
                id=order.id,
                customer_id=order.customer_id,
                code=_generate_code(),
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                date=order.date,
                status=order.status,
                margin_pct=(
                    str(order.margin_pct) if order.margin_pct is not None else None
                ),
                created_at=now,
                updated_at=now,
            )
            self.session.add(orm)
            for item in order.items:
                self.session.add(
                    OrderItemORM(
                        id=item.id or str(uuid.uuid4()),
                        order_id=order.id,
                        product_id=item.product_id,
                        product_name=item.product_name,
                        quantity=item.qty,
                        qty=item.qty,
                        portions=item.portions,
                        note=item.note,
                        position=item.position,
                        snapshot=_snapshot_to_json(
                            order.snapshots.get(item.safe_id)
                        ),
                    )
                )
            await self.session.commit()
            reloaded = await self._load_orm_p6(order.id)
            return _order_to_domain_p6(reloaded)
        except Exception:
            await self.session.rollback()
            raise

    async def update_full(self, order: P6Order) -> P6Order | None:
        try:
            orm = await self._load_orm_p6(order.id)
            if orm is None:
                return None
            orm.customer_id = order.customer_id
            orm.customer_name = order.customer_name
            orm.customer_phone = order.customer_phone
            orm.margin_pct = (
                str(order.margin_pct) if order.margin_pct is not None else None
            )
            orm.updated_at = datetime.datetime.now(datetime.UTC)
            # Reemplazo completo de lineas + snapshots (regla 4).
            for existing in list(orm.order_items):
                await self.session.delete(existing)
            for item in order.items:
                self.session.add(
                    OrderItemORM(
                        id=item.id or str(uuid.uuid4()),
                        order_id=order.id,
                        product_id=item.product_id,
                        product_name=item.product_name,
                        quantity=item.qty,
                        qty=item.qty,
                        portions=item.portions,
                        note=item.note,
                        position=item.position,
                        snapshot=_snapshot_to_json(
                            order.snapshots.get(item.safe_id)
                        ),
                    )
                )
            await self.session.commit()
            reloaded = await self._load_orm_p6(order.id)
            return _order_to_domain_p6(reloaded)
        except Exception:
            await self.session.rollback()
            raise

    async def confirm(self, order: P6Order) -> P6Order:
        """nuevo -> confirmado con descuento atomico de stock (RNF-P6-01).

        InsufficientOrderStockError: nada se persiste (rollback completo)."""
        deductions = plan_order_deductions(order.snapshots)
        try:
            ingredient_rows: dict[str, IngredientORM] = {}
            if deductions:
                rows = (
                    await self.session.execute(
                        select(IngredientORM)
                        .where(
                            IngredientORM.id.in_(list(deductions.keys())),
                            IngredientORM.deleted_at.is_(None),
                        )
                        .with_for_update()
                    )
                ).scalars().all()
                ingredient_rows = {row.id: row for row in rows}

            shortage: dict[str, Decimal] = {}
            for ingredient_id, needed in deductions.items():
                row = ingredient_rows.get(ingredient_id)
                available = (
                    Decimal(row.stock_qty) if row is not None else Decimal("0")
                )
                if available < needed:
                    shortage[ingredient_id] = needed - available
            if shortage:
                raise InsufficientOrderStockError(shortage)

            for ingredient_id, needed in deductions.items():
                row = ingredient_rows[ingredient_id]
                ingredient = _ingredient_to_domain_p6(row)
                updated, movement = apply_movement(
                    ingredient,
                    -needed,
                    reason="pedido",
                    ref=order.id,
                )
                row.stock_qty = str(updated.stock_qty)
                self.session.add(
                    StockMovementORM(
                        id=movement.id,
                        ingredient_id=ingredient_id,
                        qty_delta=str(movement.qty_delta),
                        reason=movement.reason,
                        ref=movement.ref,
                        created_at=movement.created_at,
                    )
                )

            orm = await self._load_orm_p6(order.id)
            orm.status = "confirmado"
            orm.updated_at = datetime.datetime.now(datetime.UTC)
            order = dataclasses.replace(order, status="confirmado")
            await self.session.commit()
            return order
        except Exception:
            await self.session.rollback()
            raise

    async def cancel(self, order: P6Order) -> P6Order:
        """confirmado -> cancelado con reposicion de stock (RNF-P6-01)."""
        deductions = plan_order_deductions(order.snapshots)
        try:
            ingredient_rows: dict[str, IngredientORM] = {}
            if deductions:
                rows = (
                    await self.session.execute(
                        select(IngredientORM)
                        .where(
                            IngredientORM.id.in_(list(deductions.keys())),
                            IngredientORM.deleted_at.is_(None),
                        )
                        .with_for_update()
                    )
                ).scalars().all()
                ingredient_rows = {row.id: row for row in rows}

            for ingredient_id, needed in deductions.items():
                row = ingredient_rows.get(ingredient_id)
                if row is None:
                    continue
                ingredient = _ingredient_to_domain_p6(row)
                updated, movement = apply_movement(
                    ingredient,
                    needed,
                    reason="anulacion",
                    ref=order.id,
                )
                row.stock_qty = str(updated.stock_qty)
                self.session.add(
                    StockMovementORM(
                        id=movement.id,
                        ingredient_id=ingredient_id,
                        qty_delta=str(movement.qty_delta),
                        reason=movement.reason,
                        ref=movement.ref,
                        created_at=movement.created_at,
                    )
                )

            orm = await self._load_orm_p6(order.id)
            orm.status = "cancelado"
            orm.updated_at = datetime.datetime.now(datetime.UTC)
            order = dataclasses.replace(order, status="cancelado")
            await self.session.commit()
            return order
        except Exception:
            await self.session.rollback()
            raise

    async def mark_delivered(self, order: P6Order) -> P6Order:
        """confirmado -> entregado (RNF-P6-01): sin efecto sobre stock."""
        try:
            orm = await self._load_orm_p6(order.id)
            orm.status = "entregado"
            orm.updated_at = datetime.datetime.now(datetime.UTC)
            order = dataclasses.replace(order, status="entregado")
            await self.session.commit()
            return order
        except Exception:
            await self.session.rollback()
            raise

    async def mark_whatsapp_sent(self, order: P6Order, sent_at: datetime.datetime) -> None:
        orm = await self._load_orm_p6(order.id)
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

    async def _load_orm_p6(self, order_id: str) -> OrderORM | None:
        # populate_existing: el session corre con expire_on_commit=False, así
        # que sin esta opcion la relationship order_items ya cargada antes de
        # un update_full no se repuebla tras el commit (respuesta con lineas
        # viejas, RNF-P6-03).
        result = await self.session.execute(
            select(OrderORM)
            .where(OrderORM.id == order_id)
            .options(selectinload(OrderORM.order_items))
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()


def _snapshot_to_json(snapshot: OrderItemSnapshot | None) -> str:
    if snapshot is None:
        raise ValueError("snapshot requerido")
    return json.dumps(
        {
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
        },
        ensure_ascii=False,
    )


def _json_to_snapshot(raw: str) -> OrderItemSnapshot:
    data = json.loads(raw)
    lines = tuple(
        OrderItemSnapshotLine(
            ingredient_id=line["ingredient_id"],
            ingredient_name=line["ingredient_name"],
            qty=Decimal(line["qty"]),
            unit=line["unit"],
            cost=Decimal(line["cost"]),
            is_missing=bool(line.get("is_missing", False)),
        )
        for line in data.get("lines", [])
    )
    return OrderItemSnapshot(
        lines=lines,
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


def _order_to_domain_p6(orm: OrderORM) -> P6Order:
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
        item.id: _json_to_snapshot(item.snapshot)
        for item in orm.order_items
        if item.snapshot is not None
    }
    return P6Order(
        customer_id=orm.customer_id,
        customer_name=orm.customer_name,
        customer_phone=orm.customer_phone,
        # Columna compartida C1/P6: C1 escribe datetime aware, P6 usa fecha de
        # calendario. Servidor en UTC → .date() del aware-UTC recupera la fecha
        # intencional (evita pydantic Date "inexact" en el response).
        date=orm.date.date() if isinstance(orm.date, datetime.datetime) else orm.date,
        status=orm.status,
        margin_pct=Decimal(orm.margin_pct) if orm.margin_pct is not None else None,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        whatsapp_sent_at=orm.whatsapp_sent_at,
        id=orm.id,
        items=items,
        snapshots=snapshots,
    )


def _ingredient_to_domain_p6(orm: IngredientORM) -> Ingredient:
    return Ingredient(
        name=orm.name,
        unit=orm.unit,
        price_per_unit=Decimal(orm.price_per_unit),
        stock_qty=Decimal(orm.stock_qty),
        low_stock_threshold=Decimal(orm.low_stock_threshold),
        id=orm.id,
        deleted_at=orm.deleted_at,
    )
