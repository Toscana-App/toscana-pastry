"""Repository para CalcMaterial (RF-P2CC-01..05).

CRUD de materiales + historial append-only de costo unitario
(RF-P2CC-04). `unit_cost` y `status` llegan ya derivados en el dominio
(RF-P2CC-02/03): el repository solo persiste y registra cambios.
"""

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false
# El ORM usa el estilo Column legacy (mismo que B1-B7): pyright tipa los
# atributos de instancia como Column[T], no como el valor. En runtime son
# los valores; el mapeo ORM->dominio pasa por Decimal()/str() explicitos.

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import (
    CalcMaterialCostHistoryORM,
    CalcMaterialORM,
    CalcProductMaterialORM,
    CalcProductORM,
)
from domain.calc_material import (
    CalcMaterial,
    CalcMaterialCostHistory,
)


def _to_domain(orm: CalcMaterialORM) -> CalcMaterial:
    price = orm.purchase_total_price
    qty = orm.package_quantity
    return CalcMaterial(
        id=orm.id,
        name=orm.name,
        internal_code=orm.internal_code,
        category_id=orm.material_category_id,
        supplier_id=orm.supplier_id,
        unit_of_measure=orm.unit_of_measure,
        purchase_total_price=Decimal(price) if price is not None else None,
        package_quantity=Decimal(qty) if qty is not None else None,
        notes=orm.notes,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_orm(domain: CalcMaterial) -> CalcMaterialORM:
    return CalcMaterialORM(
        id=domain.id,
        name=domain.name,
        internal_code=domain.internal_code,
        material_category_id=domain.category_id,
        supplier_id=domain.supplier_id,
        unit_of_measure=domain.unit_of_measure,
        purchase_total_price=(
            str(domain.purchase_total_price)
            if domain.purchase_total_price is not None
            else None
        ),
        package_quantity=(
            str(domain.package_quantity)
            if domain.package_quantity is not None
            else None
        ),
        notes=domain.notes,
        unit_cost=(str(domain.unit_cost) if domain.unit_cost is not None else None),
        status=domain.status,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
    )


def _history_domain(orm: CalcMaterialCostHistoryORM) -> CalcMaterialCostHistory:
    previous = orm.previous_unit_cost
    new = orm.new_unit_cost
    return CalcMaterialCostHistory(
        id=orm.id,
        material_id=orm.material_id,
        previous_unit_cost=Decimal(previous) if previous is not None else None,
        new_unit_cost=Decimal(new) if new is not None else None,
        changed_at=orm.changed_at,
    )


class SQLCalcMaterialRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        q: str | None,
        category_id: str | None,
        supplier_id: str | None,
        status_filter: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[CalcMaterial], int]:
        """Lista con busqueda por nombre Y codigo interno (RF-P2CC-05),
        filtros por categoria/proveedor/status y paginacion."""
        filters = []
        if q and q.strip():
            folded = accent_fold(q) or q
            filters.append(
                func.accent_fold(CalcMaterialORM.name).like(f"%{folded}%")
                | (
                    CalcMaterialORM.internal_code.isnot(None)
                    & func.accent_fold(CalcMaterialORM.internal_code).like(
                        f"%{folded}%"
                    )
                )
            )
        if category_id and category_id.strip():
            filters.append(CalcMaterialORM.material_category_id == category_id.strip())
        if supplier_id and supplier_id.strip():
            filters.append(CalcMaterialORM.supplier_id == supplier_id.strip())
        if status_filter and status_filter.strip():
            filters.append(CalcMaterialORM.status == status_filter.strip())
        count_stmt = select(func.count()).select_from(CalcMaterialORM).where(*filters)
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = (
            (
                await self.session.execute(
                    select(CalcMaterialORM)
                    .where(*filters)
                    .order_by(func.lower(CalcMaterialORM.name))
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return [_to_domain(r) for r in rows], total

    async def get(self, material_id: str) -> CalcMaterial | None:
        result = await self.session.execute(
            select(CalcMaterialORM).where(CalcMaterialORM.id == material_id)
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def create(self, material: CalcMaterial) -> CalcMaterial:
        """Crea el material; si queda con unit_cost, registra la alta
        inicial en el historial (RF-P2CC-04): previous=None, new=valor."""
        self.session.add(_to_orm(material))
        # Sin relationship() el UoW no ordena por FK: insertar el material
        # primero para que el historial no viole la FK (Postgres / PRAGMA).
        await self.session.flush()
        if material.unit_cost is not None:
            self.session.add(
                CalcMaterialCostHistoryORM(
                    id=str(uuid.uuid4()),
                    material_id=material.id,
                    previous_unit_cost=None,
                    new_unit_cost=str(material.unit_cost),
                    changed_at=datetime.now(UTC),
                )
            )
        await self.session.commit()
        return material

    async def update(self, material: CalcMaterial) -> CalcMaterial | None:
        """Edita el material y registra en el historial SOLO si el
        unit_cost computado cambio (RF-P2CC-04): incluye valor -> None
        al quitar precio o cantidad."""
        result = await self.session.execute(
            select(CalcMaterialORM).where(CalcMaterialORM.id == material.id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        previous_unit_cost = (
            Decimal(orm.unit_cost) if orm.unit_cost is not None else None
        )
        orm.name = material.name
        orm.internal_code = material.internal_code
        orm.material_category_id = material.category_id
        orm.supplier_id = material.supplier_id
        orm.unit_of_measure = material.unit_of_measure
        orm.purchase_total_price = (
            str(material.purchase_total_price)
            if material.purchase_total_price is not None
            else None
        )
        orm.package_quantity = (
            str(material.package_quantity)
            if material.package_quantity is not None
            else None
        )
        orm.notes = material.notes
        orm.unit_cost = (
            str(material.unit_cost) if material.unit_cost is not None else None
        )
        orm.status = material.status
        orm.updated_at = material.updated_at
        if material.unit_cost != previous_unit_cost:
            self.session.add(
                CalcMaterialCostHistoryORM(
                    id=str(uuid.uuid4()),
                    material_id=material.id,
                    previous_unit_cost=(
                        str(previous_unit_cost)
                        if previous_unit_cost is not None
                        else None
                    ),
                    new_unit_cost=(
                        str(material.unit_cost)
                        if material.unit_cost is not None
                        else None
                    ),
                    changed_at=datetime.now(UTC),
                )
            )
        await self.session.commit()
        return _to_domain(orm)

    async def delete(self, material_id: str) -> CalcMaterial | None:
        result = await self.session.execute(
            select(CalcMaterialORM).where(CalcMaterialORM.id == material_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        await self.session.delete(orm)
        await self.session.commit()
        return _to_domain(orm)

    async def count_in_use(self, material_id: str) -> int:
        """Productos no eliminados con lineas que referencian este
        material (B9): COUNT DISTINCT product_id en
        calc_product_materials, excluyendo soft-deletes."""
        result = await self.session.execute(
            select(func.count(func.distinct(CalcProductMaterialORM.product_id)))
            .join(
                CalcProductORM,
                CalcProductORM.id == CalcProductMaterialORM.product_id,
            )
            .where(
                CalcProductMaterialORM.material_id == material_id,
                CalcProductORM.deleted_at.is_(None),
            )
        )
        return result.scalar_one()

    async def count_by_status(self) -> dict[str, int]:
        """Counts de materiales por status derivado persistido (B8):
        {"active": N, "incomplete": M}; para el dashboard
        (RF-P3CC-05)."""
        rows = (
            await self.session.execute(
                select(CalcMaterialORM.status, func.count()).group_by(
                    CalcMaterialORM.status
                )
            )
        ).all()
        return {str(status_value): count for status_value, count in rows}

    async def count_cost_history(self, material_id: str) -> int:
        """Filas de historial de costo (append-only) del material."""
        result = await self.session.execute(
            select(func.count())
            .select_from(CalcMaterialCostHistoryORM)
            .where(CalcMaterialCostHistoryORM.material_id == material_id)
        )
        return result.scalar_one()

    async def list_cost_history(
        self, material_id: str, page: int, page_size: int
    ) -> tuple[list[CalcMaterialCostHistory], int]:
        """Historial paginado, mas recientes primero (RF-P2CC-04)."""
        filters = [CalcMaterialCostHistoryORM.material_id == material_id]
        count_stmt = (
            select(func.count()).select_from(CalcMaterialCostHistoryORM).where(*filters)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = (
            (
                await self.session.execute(
                    select(CalcMaterialCostHistoryORM)
                    .where(*filters)
                    .order_by(CalcMaterialCostHistoryORM.changed_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return [_history_domain(r) for r in rows], total
