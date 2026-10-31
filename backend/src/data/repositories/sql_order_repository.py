"""SQL de pedidos (Fase 6).

La confirmacion y la cancelacion son UNA sola transaccion: lock de filas
de insumos (RNF-P6-02), chequeo de stock, movimientos y cambio de estado
juntos. Si no alcanza stock, se rollbackea TODO (RNF-P6-04): ningun
movimiento ni cambio queda aplicado.
"""
import dataclasses
import json
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from data.models import (
    IngredientORM,
    OrderEventORM,
    OrderItemORM,
    OrderORM,
    StockMovementORM,
)
from domain.models import Ingredient, StockMovement
from domain.orders import (
    Order,
    OrderNotEditableError,
    OrderItem,
    OrderItemSnapshot,
    OrderItemSnapshotLine,
)
from domain.use_cases.transition_order_status import TransitionOrderStatus


# ---------------------------------------------------------------------------
# (De)serializacion del snapshot (JSON en TEXT: money como texto, RNF-P4-02)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------


def _order_to_domain(orm: OrderORM) -> Order:
    items = tuple(
        OrderItem(
            product_id=item.product_id,
            qty=item.qty,
            portions=item.portions,
            note=item.note,
            product_name=item.product_name,
            id=item.id,
            position=item.position,
        )
        for item in orm.items
    )
    snapshots = {
        item.id: _json_to_snapshot(item.snapshot) for item in orm.items
    }
    return Order(
        customer_id=orm.customer_id,
        customer_name=orm.customer_name,
        customer_phone=orm.customer_phone,
        date=orm.date,
        status=orm.status,
        margin_pct=Decimal(orm.margin_pct) if orm.margin_pct is not None else None,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        whatsapp_sent_at=orm.whatsapp_sent_at,
        id=orm.id,
        items=items,
        snapshots=snapshots,
    )


class SQLOrderRepository:  # implementa OrderRepository y OrderTransitionStore
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------ get

    async def get(self, order_id: str) -> Optional[Order]:
        result = await self.session.execute(
            select(OrderORM)
            .where(OrderORM.id == order_id)
            .options(selectinload(OrderORM.items))
        )
        orm = result.scalars().first()
        return _order_to_domain(orm) if orm else None

    async def list(
        self,
        status: Optional[str],
        customer_id: Optional[str],
        q: Optional[str],
        date_from: Optional[date],
        date_to: Optional[date],
        page: int,
        page_size: int,
    ) -> Tuple[List[Order], int]:
        filters = []
        if status:
            filters.append(OrderORM.status == status)
        if customer_id:
            filters.append(OrderORM.customer_id == customer_id)
        if q and q.strip():
            from data.accent import accent_fold

            folded = accent_fold(q) or q
            filters.append(
                func.accent_fold(OrderORM.customer_name).like(f"%{folded}%")
            )
        if date_from is not None:
            filters.append(OrderORM.date >= date_from)
        if date_to is not None:
            filters.append(OrderORM.date <= date_to)
        total = (
            await self.session.execute(
                select(func.count()).select_from(OrderORM).where(*filters)
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(OrderORM)
                .where(*filters)
                .options(selectinload(OrderORM.items))
                .order_by(OrderORM.created_at.desc(), OrderORM.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_order_to_domain(orm) for orm in rows], total

    # -------------------------------------------------------------- mutables

    async def create(self, order: Order) -> Order:
        now = datetime.now(timezone.utc)
        orm = OrderORM(
            id=order.id,
            customer_id=order.customer_id,
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
            date=order.date,
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
                    qty=item.qty,
                    portions=item.portions,
                    note=item.note,
                    position=index,
                    snapshot=_snapshot_to_json(order.snapshots[item.id]),
                )
            )
        await self.session.commit()
        return dataclasses.replace(order, created_at=now, updated_at=now)

    async def update(self, order: Order) -> Optional[Order]:
        """Reemplazo de lineas + snapshots (solo estado `nuevo`; el router
        valida antes). Los snapshots antiguos se borran: un pedido nuevo no
        tiene historico de precio que conservar."""
        orm = await self._lock_order(order.id)
        if orm is None:
            return None
        if orm.status != "nuevo":
            # Revalidado bajo lock: un confirm concurrente no puede quedar
            # con snapshots reemplazados (RNF-P6-03).
            current = orm.status
            await self.session.rollback()
            raise OrderNotEditableError(current)
        orm.customer_id = order.customer_id
        orm.customer_name = order.customer_name
        orm.customer_phone = order.customer_phone
        orm.date = order.date
        orm.margin_pct = (
            str(order.margin_pct) if order.margin_pct is not None else None
        )
        orm.updated_at = datetime.now(timezone.utc)
        for old in list(orm.items):
            await self.session.delete(old)
        for index, item in enumerate(order.items):
            self.session.add(
                OrderItemORM(
                    id=item.id,
                    order_id=order.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    qty=item.qty,
                    portions=item.portions,
                    note=item.note,
                    position=index,
                    snapshot=_snapshot_to_json(order.snapshots[item.id]),
                )
            )
        await self.session.commit()
        return order

    # ------------------------------------------------- stock + estado atomico
    # Las reglas (transicion valida, stock suficiente) las decide el caso de
    # uso TransitionOrderStatus; estos metodos solo delegan.

    async def confirm(self, order: Order) -> Order:
        """nuevo -> confirmado con descuento de stock atomico (RNF-P6-02/04)."""
        return await TransitionOrderStatus(self).execute(order.id, "confirmado")

    async def cancel(self, order: Order) -> Order:
        """confirmado -> cancelado con reposicion de stock (RNF-P6-01)."""
        return await TransitionOrderStatus(self).execute(order.id, "cancelado")

    async def mark_delivered(self, order: Order) -> Order:
        """confirmado -> entregado (RNF-P6-01): sin efecto sobre stock."""
        return await TransitionOrderStatus(self).execute(order.id, "entregado")

    # ------------------------------------------- primitivas transaccionales

    async def lock_order(self, order_id: str) -> Optional[Order]:
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
        orm.updated_at = datetime.now(timezone.utc)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    # ------------------------------------------------------------- whatsapp

    async def mark_whatsapp_sent(
        self, order: Order, sent_at: datetime
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

    # ---------------------------------------------------------------- utils

    async def _lock_order(self, order_id: str) -> Optional[OrderORM]:
        """Lee la fila del pedido con FOR UPDATE (primer lock de la
        transaccion; despues los insumos, siempre en ese orden) y refresca
        el estado desde la base, no desde el identity map."""
        result = await self.session.execute(
            select(OrderORM)
            .where(OrderORM.id == order_id)
            .options(selectinload(OrderORM.items))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def _lock_ingredients(
        self, ingredient_ids: List[str]
    ) -> Dict[str, IngredientORM]:
        """FOR UPDATE de insumos en orden determinista por id (evita
        deadlocks entre pedidos que comparten insumos)."""
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
