import dataclasses
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func, insert, literal, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from data.models import (
    BudgetDocumentORM,
    BudgetEventORM,
    BudgetItemORM,
    BudgetORM,
    BudgetVersionORM,
    TenantSequenceORM,
)
from domain.budgets import (
    BUDGET_STATUSES,
    Budget,
    BudgetItem,
    CalculationMode,
    format_sequence,
)

BUDGET_SEQUENCE_KEY = "budget"




def _budget_to_domain(orm: BudgetORM) -> Budget:
    items = tuple(
        BudgetItem(
            product_id=item.product_id,
            product_name=item.product_name,
            qty=item.qty,
            unit_cost=Decimal(item.unit_cost),
            unit_selling=Decimal(item.unit_selling),
            price_overridden=item.price_overridden,
            id=item.id,
        )
        for item in orm.items
    )
    return Budget(
        customer_id=orm.customer_id,
        customer_name=orm.customer_name,
        customer_phone=orm.customer_phone,
        delivery_address=orm.delivery_address,
        items=items,
        margin_pct=Decimal(orm.margin_pct) if orm.margin_pct is not None else None,
        calculation_mode=CalculationMode(orm.calculation_mode),
        status=orm.status,
        version=orm.version,
        seq=orm.seq,
        id=orm.id,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        sent_at=orm.sent_at,
        order_id=orm.order_id,
    )


def _snapshot_to_json(budget: Budget) -> str:
    totals = budget.totals
    return json.dumps(
        {
            "seq": budget.seq,
            "customer": {
                "id": budget.customer_id,
                "name": budget.customer_name,
                "phone": budget.customer_phone,
                "delivery_address": budget.delivery_address,
            },
            "margin_pct": str(budget.margin_pct)
            if budget.margin_pct is not None
            else None,
            "calculation_mode": budget.calculation_mode.value,
            "items": [
                {
                    "product_id": item.product_id,
                    "product_name": item.product_name,
                    "qty": item.qty,
                    "unit_cost": str(item.unit_cost),
                    "unit_selling": str(item.unit_selling),
                    "price_overridden": item.price_overridden,
                }
                for item in budget.items
            ],
            "totals": {
                "subtotal": str(totals.subtotal),
                "total_costos": str(totals.total_costos),
                "ganancia": str(totals.ganancia),
                "iva": str(totals.iva),
                "total_venta": str(totals.total_venta),
            },
        }
    )


class SQLBudgetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session


    async def get(self, budget_id: str) -> Optional[Budget]:
        result = await self.session.execute(
            select(BudgetORM)
            .where(BudgetORM.id == budget_id)
            .options(selectinload(BudgetORM.items))
        )
        orm = result.scalars().first()
        return _budget_to_domain(orm) if orm else None

    async def list(
        self,
        status: Optional[str],
        q: Optional[str],
        date_from: Optional[date],
        date_to: Optional[date],
        page: int,
        page_size: int,
    ) -> Tuple[List[Budget], int]:
        filters = []
        if status:
            filters.append(BudgetORM.status == status)
        if q and q.strip():
            from data.accent import accent_fold

            folded = accent_fold(q) or q
            filters.append(
                or_(
                    func.accent_fold(BudgetORM.customer_name).like(f"%{folded}%"),
                    BudgetORM.seq.like(f"%{folded}%"),
                )
            )
        if date_from is not None:
            filters.append(BudgetORM.created_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc))
        if date_to is not None:
            filters.append(BudgetORM.created_at <= datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc))
        total = (
            await self.session.execute(
                select(func.count()).select_from(BudgetORM).where(*filters)
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(BudgetORM)
                .where(*filters)
                .options(selectinload(BudgetORM.items))
                .order_by(BudgetORM.created_at.desc(), BudgetORM.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_budget_to_domain(orm) for orm in rows], total


    async def _bump_sequence(self) -> Optional[int]:
        return (
            await self.session.execute(
                update(TenantSequenceORM)
                .where(TenantSequenceORM.key == BUDGET_SEQUENCE_KEY)
                .values(current=TenantSequenceORM.current + 1)
                .returning(TenantSequenceORM.current)
                .execution_options(synchronize_session=False)
            )
        ).scalar_one_or_none()

    async def _next_sequence(self) -> str:
        current = await self._bump_sequence()
        if current is None:
            try:
                async with self.session.begin_nested():
                    self.session.add(
                        TenantSequenceORM(key=BUDGET_SEQUENCE_KEY, current=0)
                    )
            except IntegrityError:
                pass
            current = await self._bump_sequence()
        assert current is not None
        return format_sequence(current)

    async def create(self, budget: Budget) -> Budget:
        try:
            seq = await self._next_sequence()
            now = datetime.now(timezone.utc)
            orm = BudgetORM(
                id=budget.id,
                seq=seq,
                customer_id=budget.customer_id,
                customer_name=budget.customer_name,
                customer_phone=budget.customer_phone,
                delivery_address=budget.delivery_address,
                status=budget.status,
                calculation_mode=budget.calculation_mode.value,
                margin_pct=str(budget.margin_pct) if budget.margin_pct is not None else None,
                version=budget.version,
                created_at=now,
                updated_at=now,
            )
            self.session.add(orm)
            for index, item in enumerate(budget.items):
                self.session.add(
                    BudgetItemORM(
                        id=item.id,
                        budget_id=budget.id,
                        product_id=item.product_id,
                        product_name=item.product_name,
                        qty=item.qty,
                        unit_cost=str(item.unit_cost),
                        unit_selling=str(item.unit_selling),
                        price_overridden=item.price_overridden,
                        position=index,
                    )
                )
            await self.session.commit()
            return dataclasses.replace(
                budget, seq=seq, created_at=now, updated_at=now
            )
        except Exception:
            await self.session.rollback()
            raise

    async def update(self, budget: Budget) -> Optional[Budget]:
        result = await self.session.execute(
            select(BudgetORM)
            .where(BudgetORM.id == budget.id)
            .options(selectinload(BudgetORM.items))
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        try:
            orm.customer_id = budget.customer_id
            orm.customer_name = budget.customer_name
            orm.customer_phone = budget.customer_phone
            orm.delivery_address = budget.delivery_address
            orm.calculation_mode = budget.calculation_mode.value
            orm.margin_pct = (
                str(budget.margin_pct) if budget.margin_pct is not None else None
            )
            orm.status = budget.status
            orm.version = budget.version
            orm.sent_at = budget.sent_at
            orm.updated_at = datetime.now(timezone.utc)
            for old in list(orm.items):
                await self.session.delete(old)
            for index, item in enumerate(budget.items):
                self.session.add(
                    BudgetItemORM(
                        id=item.id,
                        budget_id=budget.id,
                        product_id=item.product_id,
                        product_name=item.product_name,
                        qty=item.qty,
                        unit_cost=str(item.unit_cost),
                        unit_selling=str(item.unit_selling),
                        price_overridden=item.price_overridden,
                        position=index,
                    )
                )
            await self.session.commit()
            return dataclasses.replace(
                budget, updated_at=orm.updated_at
            )
        except Exception:
            await self.session.rollback()
            raise

    async def delete(self, budget_id: str) -> bool:
        result = await self.session.execute(
            select(BudgetORM).where(BudgetORM.id == budget_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return False
        try:
            await self.session.delete(orm)
            versions = (
                await self.session.execute(
                    select(BudgetVersionORM).where(
                        BudgetVersionORM.budget_id == budget_id
                    )
                )
            ).scalars().all()
            for version in versions:
                await self.session.delete(version)
            documents = (
                await self.session.execute(
                    select(BudgetDocumentORM).where(
                        BudgetDocumentORM.budget_id == budget_id
                    )
                )
            ).scalars().all()
            for document in documents:
                await self.session.delete(document)
            events = (
                await self.session.execute(
                    select(BudgetEventORM).where(
                        BudgetEventORM.budget_id == budget_id
                    )
                )
            ).scalars().all()
            for event in events:
                await self.session.delete(event)
            await self.session.commit()
            return True
        except Exception:
            await self.session.rollback()
            raise


    async def mark_converted(self, budget_id: str, order_id: str) -> bool:
        try:
            result = await self.session.execute(
                update(BudgetORM)
                .where(BudgetORM.id == budget_id, BudgetORM.order_id.is_(None))
                .values(order_id=order_id)
                .execution_options(synchronize_session=False)
            )
            await self.session.commit()
            return result.rowcount == 1
        except Exception:
            await self.session.rollback()
            raise


    async def mark_sent(self, budget: Budget) -> Budget:
        try:
            now = datetime.now(timezone.utc)
            orm = await self.session.execute(
                select(BudgetORM).where(BudgetORM.id == budget.id)
            )
            row = orm.scalars().first()
            if row is None:
                raise ValueError(f"presupuesto no encontrado: {budget.id}")
            row.status = budget.status
            row.version = budget.version
            row.sent_at = budget.sent_at
            row.updated_at = budget.updated_at
            self.session.add(
                BudgetVersionORM(
                    id=str(uuid.uuid4()),
                    budget_id=budget.id,
                    version=budget.version,
                    snapshot=_snapshot_to_json(budget),
                    created_at=now,
                )
            )
            await self.session.commit()
            return dataclasses.replace(
                budget,
                status="enviado",
                version=budget.version,
                sent_at=budget.sent_at,
                updated_at=budget.updated_at,
            )
        except Exception:
            await self.session.rollback()
            raise


    async def record_whatsapp_sent_within_limit(
        self, budget_id: str, masked_phone: str, since: datetime, limit: int
    ) -> Optional[datetime]:
        try:
            now = datetime.now(timezone.utc)
            sent_count = (
                select(func.count())
                .select_from(BudgetEventORM)
                .where(
                    BudgetEventORM.type == "whatsapp_sent",
                    BudgetEventORM.created_at >= since,
                )
                .scalar_subquery()
            )
            stmt = insert(BudgetEventORM).from_select(
                ["id", "budget_id", "type", "payload", "created_at"],
                select(
                    literal(str(uuid.uuid4())),
                    literal(budget_id),
                    literal("whatsapp_sent"),
                    literal(masked_phone),
                    literal(now, type_=BudgetEventORM.created_at.type),
                ).where(sent_count < limit),
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            return now if result.rowcount == 1 else None
        except Exception:
            await self.session.rollback()
            raise
