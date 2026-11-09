

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import (
    CalcMaterialORM,
    CalcProductCategoryORM,
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
    compute_costs,
)

ListRow = tuple[CalcProduct, CalcProductCosts, str | None]

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
        product_id=None,
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
        product_id=None,
        activity_name=line.activity_name,
        hourly_rate=str(line.hourly_rate),
        minutes_required=str(line.minutes_required),
        line_total_cost=str(line.line_total_cost),
        sort_order=line.sort_order,
    )


def _extra_line_to_orm(line: CalcProductExtraCostLine) -> CalcProductExtraCostORM:
    return CalcProductExtraCostORM(
        id=line.id,
        product_id=None,
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


def _list_sort_key(sort: str):
    if sort == "name":
        return lambda row: row[0].name.lower()
    if sort == "margin":
        return lambda row: row[0].margin_percent
    if sort == "cost":
        return lambda row: row[1].product_total_cost
    if sort == "price":
        return lambda row: row[1].final_sale_price
    raise ValueError(f"sort invalido: {sort!r}")


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
        sort: str = "name",
        dir: str = "asc",
        rounding_mode: str = "none",
    ) -> tuple[list[ListRow], int]:
        if sort == "name":
            filters = self._filters(q, category_id, status_filter)
            total = (
                await self.session.execute(
                    select(func.count()).select_from(CalcProductORM).where(*filters)
                )
            ).scalar_one()
            name_order = func.lower(CalcProductORM.name)
            orms = (
                (
                    await self.session.execute(
                        select(CalcProductORM)
                        .where(*filters)
                        .order_by(
                            name_order.desc() if dir == "desc" else name_order
                        )
                        .limit(page_size)
                        .offset((page - 1) * page_size)
                    )
                )
                .scalars()
                .all()
            )
            return await self._enrich(orms, rounding_mode), total
        rows, total = await self._matched_rows(
            q, category_id, status_filter, rounding_mode
        )
        key = _list_sort_key(sort)
        ordered = sorted(rows, key=lambda row: row[0].name.lower())
        ordered = sorted(ordered, key=key, reverse=(dir == "desc"))
        start = (page - 1) * page_size
        return ordered[start : start + page_size], total

    async def list_price_list(
        self,
        q: str | None,
        category_id: str | None,
        page: int,
        page_size: int | None,
        rounding_mode: str,
    ) -> tuple[list[ListRow], int]:
        rows, total = await self._matched_rows(q, category_id, "active", rounding_mode)
        if page_size is None:
            return rows, total
        start = (page - 1) * page_size
        return rows[start : start + page_size], total

    async def dashboard_data(
        self, rounding_mode: str
    ) -> tuple[dict[str, int], list[tuple[CalcProduct, CalcProductCosts]]]:
        base = CalcProductORM.deleted_at.is_(None)
        count_rows = await self.session.execute(
            select(CalcProductORM.status, func.count())
            .where(base)
            .group_by(CalcProductORM.status)
        )
        counts = {str(status): int(n) for status, n in count_rows.all()}
        orms = (
            (
                await self.session.execute(
                    select(CalcProductORM)
                    .where(base, CalcProductORM.status == "active")
                    .order_by(func.lower(CalcProductORM.name))
                )
            )
            .scalars()
            .all()
        )
        active = [
            (product, costs)
            for product, costs, _category in await self._enrich(
                orms, rounding_mode
            )
        ]
        return counts, active

    async def _matched_rows(
        self,
        q: str | None,
        category_id: str | None,
        status_filter: str | None,
        rounding_mode: str,
    ) -> tuple[list[ListRow], int]:
        filters = self._filters(q, category_id, status_filter)
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
                )
            )
            .scalars()
            .all()
        )
        return await self._enrich(rows, rounding_mode), total

    @staticmethod
    def _filters(
        q: str | None, category_id: str | None, status_filter: str | None
    ) -> list:
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
        return filters

    async def _enrich(
        self, orms: list[CalcProductORM], rounding_mode: str
    ) -> list[ListRow]:
        category_names = await self._category_names()
        lines = await self._lines_for([str(o.id) for o in orms])
        enriched: list[ListRow] = []
        for row in orms:
            product = _product_to_domain(row)
            material_lines, labor_lines, extra_lines = lines[str(row.id)]
            costs = compute_costs(
                material_lines,
                labor_lines,
                extra_lines,
                product.margin_percent,
                product.discount_percent,
                product.tax_percent,
                rounding_mode,
            )
            enriched.append(
                (product, costs, category_names.get(row.product_category_id))
            )
        return enriched

    async def _lines_for(self, product_ids: list[str]) -> dict[str, tuple]:
        result: dict[str, tuple] = {pid: ([], [], []) for pid in product_ids}
        specs = (
            (CalcProductMaterialORM, _material_line_to_domain, 0),
            (CalcProductLaborORM, _labor_line_to_domain, 1),
            (CalcProductExtraCostORM, _extra_line_to_domain, 2),
        )
        for start in range(0, len(product_ids), 500):
            chunk = product_ids[start : start + 500]
            for orm_cls, to_domain, idx in specs:
                found = (
                    (
                        await self.session.execute(
                            select(orm_cls)
                            .where(orm_cls.product_id.in_(chunk))
                            .order_by(orm_cls.sort_order)
                        )
                    )
                    .scalars()
                    .all()
                )
                for line in found:
                    result[str(line.product_id)][idx].append(to_domain(line))
        return result

    async def _category_names(self) -> dict[str, str]:
        rows = (
            (await self.session.execute(select(CalcProductCategoryORM)))
            .scalars()
            .all()
        )
        return {str(row.id): str(row.name) for row in rows}

    async def get(self, product_id: str) -> CalcProduct | None:
        result = await self.session.execute(
            select(CalcProductORM).where(
                CalcProductORM.id == product_id,
                CalcProductORM.deleted_at.is_(None),
            )
        )
        orm = result.scalars().first()
        return _product_to_domain(orm) if orm else None

    async def get_material(self, material_id: str) -> CalcMaterial | None:
        result = await self.session.execute(
            select(CalcMaterialORM).where(CalcMaterialORM.id == material_id)
        )
        orm = result.scalars().first()
        return _material_to_domain(orm) if orm else None

    async def get_materials(
        self, material_ids: list[str]
    ) -> dict[str, CalcMaterial]:
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
        self.session.add(_product_to_orm(product))
        await self.session.flush()
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
        await self.session.execute(
            update(CalcProductMaterialORM)
            .where(CalcProductMaterialORM.product_id == product_id)
            .values(material_id=None)
        )
        await self.session.commit()
        return _product_to_domain(orm)

    async def list_active(self) -> list[CalcProduct]:
        orms = (
            (
                await self.session.execute(
                    select(CalcProductORM).where(
                        CalcProductORM.status == "active",
                        CalcProductORM.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        return [_product_to_domain(orm) for orm in orms]

    async def save_lines(
        self,
        product_id: str,
        material_lines: list[CalcProductMaterialLine],
        labor_lines: list[CalcProductLaborLine],
        extra_lines: list[CalcProductExtraCostLine],
        last_recalculated_at: datetime,
    ) -> CalcProduct | None:
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
