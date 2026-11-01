"""Repository para CalcProduct (RF-P4CC-01..08).

CRUD de productos + lineas (materiales con snapshots resueltos por el
servidor, RF-P4CC-02/05), reemplazo completo de lineas (regla 4),
soft delete (regla 8), SKU unica case/acento-insensitive (regla 7) y
versiones append-only del precio (reglas 5/6, RF-P4CC-07).
"""

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false
# El ORM usa el estilo Column legacy (mismo que B1-B8): pyright tipa los
# atributos de instancia como Column[T], no como el valor. En runtime son
# los valores; el mapeo ORM->dominio pasa por Decimal()/str() explicitos.

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import (
    CalcMaterialORM,
    CalcProductExtraCostORM,
    CalcProductLaborORM,
    CalcProductMaterialORM,
    CalcProductORM,
    CalcProductVersionORM,
)
from domain.calc_material import CalcMaterial
from domain.calc_product import (
    CalcProduct,
    CalcProductCosts,
    CalcProductExtraCostLine,
    CalcProductLaborLine,
    CalcProductMaterialLine,
    CalcProductVersion,
)

_ZERO = Decimal("0")


def _product_to_domain(orm: CalcProductORM) -> CalcProduct:
    return CalcProduct(
        id=orm.id,
        name=orm.name,
        sku=orm.sku,
        category_id=orm.product_category_id,
        description=orm.description,
        notes=orm.notes,
        margin_percent=Decimal(orm.margin_percent),
        discount_percent=Decimal(orm.discount_percent),
        tax_percent=Decimal(orm.tax_percent),
        status=orm.status,
        last_recalculated_at=orm.last_recalculated_at,
        deleted_at=orm.deleted_at,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _product_to_orm(domain: CalcProduct) -> CalcProductORM:
    return CalcProductORM(
        id=domain.id,
        name=domain.name,
        sku=domain.sku,
        product_category_id=domain.category_id,
        description=domain.description,
        notes=domain.notes,
        margin_percent=str(domain.margin_percent),
        discount_percent=str(domain.discount_percent),
        tax_percent=str(domain.tax_percent),
        status=domain.status,
        last_recalculated_at=domain.last_recalculated_at,
        deleted_at=domain.deleted_at,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
    )


def _material_line_to_orm(line: CalcProductMaterialLine) -> CalcProductMaterialORM:
    return CalcProductMaterialORM(
        id=line.id,
        product_id=None,  # se asigna al construir (el dataclass no conoce el producto)
        material_id=line.material_id,
        material_name=line.material_name,
        unit_of_measure_snapshot=line.unit_of_measure_snapshot,
        unit_cost_snapshot=str(line.unit_cost_snapshot),
        quantity_used=str(line.quantity_used),
        line_total_cost=str(line.line_total_cost),
        sort_order=line.sort_order,
    )


def _labor_line_to_orm(line: CalcProductLaborLine) -> CalcProductLaborORM:
    return CalcProductLaborORM(
        id=line.id,
        product_id=None,  # se asigna al construir
        activity_name=line.activity_name,
        hourly_rate=str(line.hourly_rate),
        minutes_required=str(line.minutes_required),
        line_total_cost=str(line.line_total_cost),
        sort_order=line.sort_order,
    )


def _extra_line_to_orm(line: CalcProductExtraCostLine) -> CalcProductExtraCostORM:
    return CalcProductExtraCostORM(
        id=line.id,
        product_id=None,  # se asigna al construir
        concept_name=line.concept_name,
        unit_cost=str(line.unit_cost),
        quantity=str(line.quantity),
        line_total_cost=str(line.line_total_cost),
        sort_order=line.sort_order,
    )


def _material_line_to_domain(orm: CalcProductMaterialORM) -> CalcProductMaterialLine:
    return CalcProductMaterialLine(
        id=orm.id,
        material_id=orm.material_id,
        material_name=orm.material_name,
        quantity_used=Decimal(orm.quantity_used),
        unit_of_measure_snapshot=orm.unit_of_measure_snapshot,
        unit_cost_snapshot=Decimal(orm.unit_cost_snapshot),
        line_total_cost=Decimal(orm.line_total_cost),
        sort_order=orm.sort_order,
    )


def _labor_line_to_domain(orm: CalcProductLaborORM) -> CalcProductLaborLine:
    return CalcProductLaborLine(
        id=orm.id,
        activity_name=orm.activity_name,
        hourly_rate=Decimal(orm.hourly_rate),
        minutes_required=Decimal(orm.minutes_required),
        line_total_cost=Decimal(orm.line_total_cost),
        sort_order=orm.sort_order,
    )


def _extra_line_to_domain(orm: CalcProductExtraCostORM) -> CalcProductExtraCostLine:
    return CalcProductExtraCostLine(
        id=orm.id,
        concept_name=orm.concept_name,
        unit_cost=Decimal(orm.unit_cost),
        quantity=Decimal(orm.quantity),
        line_total_cost=Decimal(orm.line_total_cost),
        sort_order=orm.sort_order,
    )


def _material_to_domain(orm: CalcMaterialORM) -> CalcMaterial:
    return CalcMaterial(
        id=orm.id,
        name=orm.name,
        internal_code=orm.internal_code,
        category_id=orm.material_category_id,
        supplier_id=orm.supplier_id,
        unit_of_measure=orm.unit_of_measure,
        purchase_total_price=(
            Decimal(orm.purchase_total_price)
            if orm.purchase_total_price is not None
            else None
        ),
        package_quantity=(
            Decimal(orm.package_quantity)
            if orm.package_quantity is not None
            else None
        ),
        notes=orm.notes,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _version_to_domain(orm: CalcProductVersionORM) -> CalcProductVersion:
    return CalcProductVersion(
        id=orm.id,
        product_id=orm.product_id,
        version_number=orm.version_number,
        product_total_cost=Decimal(orm.product_total_cost),
        profit_amount=Decimal(orm.profit_amount),
        discount_amount=Decimal(orm.discount_amount),
        adjusted_profit_amount=Decimal(orm.adjusted_profit_amount),
        tax_amount=Decimal(orm.tax_amount),
        final_sale_price=Decimal(orm.final_sale_price),
        changed_at=orm.changed_at,
    )


class SQLCalcProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        q: str | None,
        category_id: str | None,
        status_filter: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[CalcProduct], int]:
        """Lista solo no-eliminados con busqueda por nombre Y SKU
        (accent-fold, D5), filtros y paginacion; orden fijo por nombre."""
        filters = [CalcProductORM.deleted_at.is_(None)]
        if q and q.strip():
            folded = accent_fold(q) or q
            filters.append(
                func.accent_fold(CalcProductORM.name).like(f"%{folded}%")
                | (
                    CalcProductORM.sku.isnot(None)
                    & func.accent_fold(CalcProductORM.sku).like(f"%{folded}%")
                )
            )
        if category_id and category_id.strip():
            filters.append(CalcProductORM.product_category_id == category_id.strip())
        if status_filter and status_filter.strip():
            filters.append(CalcProductORM.status == status_filter.strip())
        count_stmt = (
            select(func.count()).select_from(CalcProductORM).where(*filters)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = (
            (
                await self.session.execute(
                    select(CalcProductORM)
                    .where(*filters)
                    .order_by(func.lower(CalcProductORM.name))
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return [_product_to_domain(r) for r in rows], total

    async def get(self, product_id: str) -> CalcProduct | None:
        """Detalle; eliminados -> None (regla 8)."""
        result = await self.session.execute(
            select(CalcProductORM).where(
                CalcProductORM.id == product_id,
                CalcProductORM.deleted_at.is_(None),
            )
        )
        orm = result.scalars().first()
        return _product_to_domain(orm) if orm else None

    async def get_material(self, material_id: str) -> CalcMaterial | None:
        """Material en dominio para resolver snapshots (RF-P4CC-02).

        Mismo mapeo que `SQLCalcMaterialRepository.get`: `unit_cost`
        derivada en el dominio (incomplete -> None -> snapshot 0.00, D4).
        """
        result = await self.session.execute(
            select(CalcMaterialORM).where(CalcMaterialORM.id == material_id)
        )
        orm = result.scalars().first()
        return _material_to_domain(orm) if orm else None

    async def get_materials(
        self, material_ids: list[str]
    ) -> dict[str, CalcMaterial]:
        """Materiales actuales por id (para recalcular snapshots)."""
        if not material_ids:
            return {}
        rows = (
            (
                await self.session.execute(
                    select(CalcMaterialORM).where(
                        CalcMaterialORM.id.in_(material_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        return {row.id: _material_to_domain(row) for row in rows}

    async def find_sku_owner(
        self, sku: str, exclude_product_id: str | None = None
    ) -> CalcProductORM | None:
        """Propietario vigente de un SKU (regla 7): unico entre no
        eliminados, case/acento-insensitive (accent_fold)."""
        folded = accent_fold(sku) or sku
        filters = [
            func.accent_fold(CalcProductORM.sku) == folded,
            CalcProductORM.sku.isnot(None),
            CalcProductORM.deleted_at.is_(None),
        ]
        if exclude_product_id is not None:
            filters.append(CalcProductORM.id != exclude_product_id)
        result = await self.session.execute(
            select(CalcProductORM).where(*filters)
        )
        return result.scalars().first()

    async def get_lines(
        self, product_id: str
    ) -> tuple[
        list[CalcProductMaterialLine],
        list[CalcProductLaborLine],
        list[CalcProductExtraCostLine],
    ]:
        """Lineas del producto, por tipo, ordenadas por sort_order."""
        material_rows = (
            (
                await self.session.execute(
                    select(CalcProductMaterialORM)
                    .where(CalcProductMaterialORM.product_id == product_id)
                    .order_by(CalcProductMaterialORM.sort_order)
                )
            )
            .scalars()
            .all()
        )
        labor_rows = (
            (
                await self.session.execute(
                    select(CalcProductLaborORM)
                    .where(CalcProductLaborORM.product_id == product_id)
                    .order_by(CalcProductLaborORM.sort_order)
                )
            )
            .scalars()
            .all()
        )
        extra_rows = (
            (
                await self.session.execute(
                    select(CalcProductExtraCostORM)
                    .where(CalcProductExtraCostORM.product_id == product_id)
                    .order_by(CalcProductExtraCostORM.sort_order)
                )
            )
            .scalars()
            .all()
        )
        return (
            [_material_line_to_domain(r) for r in material_rows],
            [_labor_line_to_domain(r) for r in labor_rows],
            [_extra_line_to_domain(r) for r in extra_rows],
        )

    async def create(
        self,
        product: CalcProduct,
        material_lines: list[CalcProductMaterialLine],
        labor_lines: list[CalcProductLaborLine],
        extra_lines: list[CalcProductExtraCostLine],
    ) -> CalcProduct:
        """Producto + lineas en una sola transaccion (regla 4)."""
        self.session.add(_product_to_orm(product))
        for line in material_lines:
            orm = _material_line_to_orm(line)
            orm.product_id = product.id
            self.session.add(orm)
        for line in labor_lines:
            orm = _labor_line_to_orm(line)
            orm.product_id = product.id
            self.session.add(orm)
        for line in extra_lines:
            orm = _extra_line_to_orm(line)
            orm.product_id = product.id
            self.session.add(orm)
        await self.session.commit()
        return product

    async def update(
        self,
        product: CalcProduct,
        material_lines: list[CalcProductMaterialLine] | None,
        labor_lines: list[CalcProductLaborLine] | None,
        extra_lines: list[CalcProductExtraCostLine] | None,
    ) -> CalcProduct | None:
        """Edita el producto y reemplaza el set completo de lineas de
        los tipos enviados (regla 4: None = no cambia, lista =
        borrar viejas + insertar nuevas) en el mismo commit."""
        result = await self.session.execute(
            select(CalcProductORM).where(
                CalcProductORM.id == product.id,
                CalcProductORM.deleted_at.is_(None),
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        new = _product_to_orm(product)
        orm.name = new.name
        orm.sku = new.sku
        orm.product_category_id = new.product_category_id
        orm.description = new.description
        orm.notes = new.notes
        orm.margin_percent = new.margin_percent
        orm.discount_percent = new.discount_percent
        orm.tax_percent = new.tax_percent
        orm.status = new.status
        orm.updated_at = new.updated_at

        if material_lines is not None:
            await self._replace_lines(
                CalcProductMaterialORM,
                _material_line_to_orm,
                product.id,
                material_lines,
            )
        if labor_lines is not None:
            await self._replace_lines(
                CalcProductLaborORM, _labor_line_to_orm, product.id, labor_lines
            )
        if extra_lines is not None:
            await self._replace_lines(
                CalcProductExtraCostORM,
                _extra_line_to_orm,
                product.id,
                extra_lines,
            )
        await self.session.commit()
        return _product_to_domain(orm)

    async def _replace_lines(
        self,
        model,
        to_orm,
        product_id: str,
        lines: list,
    ) -> None:
        existing = (
            (
                await self.session.execute(
                    select(model).where(model.product_id == product_id)
                )
            )
            .scalars()
            .all()
        )
        for row in existing:
            await self.session.delete(row)
        for line in lines:
            orm = to_orm(line)
            orm.product_id = product_id
            self.session.add(orm)

    async def soft_delete(self, product_id: str) -> CalcProduct | None:
        """Soft delete (regla 8): setea deleted_at; nunca borra la fila
        ni las versiones."""
        result = await self.session.execute(
            select(CalcProductORM).where(
                CalcProductORM.id == product_id,
                CalcProductORM.deleted_at.is_(None),
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.deleted_at = datetime.now(UTC)
        await self.session.commit()
        return _product_to_domain(orm)

    async def save_lines(
        self,
        product_id: str,
        material_lines: list[CalcProductMaterialLine],
        labor_lines: list[CalcProductLaborLine],
        extra_lines: list[CalcProductExtraCostLine],
        last_recalculated_at: datetime,
    ) -> CalcProduct | None:
        """Persiste los valores recalculados de las lineas existentes
        (por id) y `last_recalculated_at`. No hace commit: lo hace
        `commit()` junto con `add_version` (misma transaccion)."""
        result = await self.session.execute(
            select(CalcProductORM).where(
                CalcProductORM.id == product_id,
                CalcProductORM.deleted_at.is_(None),
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        for line in material_lines:
            row = await self.session.get(CalcProductMaterialORM, line.id)
            if row is not None:
                row.material_name = line.material_name
                row.unit_of_measure_snapshot = line.unit_of_measure_snapshot
                row.unit_cost_snapshot = str(line.unit_cost_snapshot)
                row.line_total_cost = str(line.line_total_cost)
        for labor in labor_lines:
            row = await self.session.get(CalcProductLaborORM, labor.id)
            if row is not None:
                row.line_total_cost = str(labor.line_total_cost)
        for extra in extra_lines:
            row = await self.session.get(CalcProductExtraCostORM, extra.id)
            if row is not None:
                row.line_total_cost = str(extra.line_total_cost)
        orm.last_recalculated_at = last_recalculated_at
        return _product_to_domain(orm)

    async def add_version(
        self, product_id: str, costs: CalcProductCosts
    ) -> None:
        """Agrega la siguiente version append-only del precio
        (RF-P4CC-07). No hace commit (ver `commit()`)."""
        version_number = await self._next_version_number(product_id)
        self.session.add(
            CalcProductVersionORM(
                id=str(uuid.uuid4()),
                product_id=product_id,
                version_number=version_number,
                product_total_cost=str(costs.product_total_cost),
                profit_amount=str(costs.profit_amount),
                discount_amount=str(costs.discount_amount),
                adjusted_profit_amount=str(costs.adjusted_profit_amount),
                tax_amount=str(costs.tax_amount),
                final_sale_price=str(costs.final_sale_price),
                changed_at=datetime.now(UTC),
            )
        )
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def _next_version_number(self, product_id: str) -> int:
        result = await self.session.execute(
            select(func.max(CalcProductVersionORM.version_number)).where(
                CalcProductVersionORM.product_id == product_id
            )
        )
        current_max = result.scalar_one()
        return (current_max + 1) if current_max is not None else 1

    async def list_versions(
        self, product_id: str, page: int, page_size: int
    ) -> tuple[list[CalcProductVersion], int]:
        """Versiones paginadas, mas recientes primero (RF-P4CC-07)."""
        filters = [CalcProductVersionORM.product_id == product_id]
        count_stmt = (
            select(func.count())
            .select_from(CalcProductVersionORM)
            .where(*filters)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = (
            (
                await self.session.execute(
                    select(CalcProductVersionORM)
                    .where(*filters)
                    .order_by(CalcProductVersionORM.version_number.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return [_version_to_domain(r) for r in rows], total
