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
    calc_extra_line_cost,
    calc_labor_line_cost,
    calc_material_line_cost,
    compute_costs,
)

# Item enriquecido del listado/price-list (RF-P3CC-01/04):
# (producto, costs del motor, nombre de categoria o None).
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


def _list_sort_key(sort: str):
    """Clave de orden del listado (RF-P3CC-01, D5): `name` es texto
    (mismo criterio que el orden SQL B9); `margin` el percent
    almacenado (columna String -> Decimal); `cost`/`price` los montos
    calculados por el motor (los montos no estan persistidos)."""
    if sort == "name":
        return lambda row: row[0].name.lower()
    if sort == "margin":
        return lambda row: row[0].margin_percent
    if sort == "cost":
        return lambda row: row[1].product_total_cost
    if sort == "price":
        return lambda row: row[1].final_sale_price
    raise ValueError(f"sort invalido: {sort!r}")


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
        """Lista solo no-eliminados con busqueda por nombre Y SKU
        (accent-fold, D5), filtros y paginacion (RF-P3CC-01).

        Cada item va enriquecido: (producto, costs del motor con el
        `rounding_mode` dado, nombre de categoria o None). `sort` =
        name (comportamiento B9 por defecto) | cost | price | margin;
        cost/price/margin se ordenan en Python sobre el set completo
        (los montos no estan persistidos) y la paginacion tambien es
        en Python (escala admin). Ties -> name asc; `dir` invierte
        solo el campo primario."""
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
        page_size: int,
        rounding_mode: str,
    ) -> tuple[list[ListRow], int]:
        """Price list (RF-P3CC-04): solo productos activos no
        eliminados, con la misma busqueda/filtro de `list`, orden fijo
        por nombre (D5)."""
        rows, total = await self._matched_rows(q, category_id, "active", rounding_mode)
        start = (page - 1) * page_size
        return rows[start : start + page_size], total

    async def dashboard_data(
        self, rounding_mode: str
    ) -> tuple[dict[str, int], list[tuple[CalcProduct, CalcProductCosts]]]:
        """Datos crudos del dashboard (RF-P3CC-05): counts de
        productos no eliminados por status + los activos con sus costs
        ya calculados por el motor con el `rounding_mode` dado."""
        rows, _total = await self._matched_rows(None, None, None, rounding_mode)
        counts: dict[str, int] = {}
        for product, _costs, _category in rows:
            counts[product.status] = counts.get(product.status, 0) + 1
        active = [
            (product, costs)
            for product, costs, _category in rows
            if product.status == "active"
        ]
        return counts, active

    async def _matched_rows(
        self,
        q: str | None,
        category_id: str | None,
        status_filter: str | None,
        rounding_mode: str,
    ) -> tuple[list[ListRow], int]:
        """Todas las filas que matchean los filtros (sin paginacion),
        cada una con sus costs del motor y el nombre de su categoria;
        orden base por nombre (func.lower), igual que B9."""
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
                )
            )
            .scalars()
            .all()
        )
        category_names = await self._category_names()
        enriched: list[ListRow] = []
        for row in rows:
            product = _product_to_domain(row)
            material_lines, labor_lines, extra_lines = await self.get_lines(row.id)
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
        return enriched, total

    async def _category_names(self) -> dict[str, str]:
        """Id -> nombre de las categorias de producto (una sola
        consulta, para enriquecer el item del listado/price-list)."""
        rows = (
            (await self.session.execute(select(CalcProductCategoryORM)))
            .scalars()
            .all()
        )
        return {str(row.id): str(row.name) for row in rows}

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
        if orm is None:
            return None
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
        # Flush para que la fila padre exista antes que las lineas hija
        # (FK product_id); Postgres lo exige, SQLite no.
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
        ni las versiones.

        Regla 9: las lineas de material pierden la referencia a
        calc_materials (material_id -> NULL) para que el material pueda
        borrarse; los snapshots historicos se conservan."""
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

    async def recalculate(
        self, product_id: str, rounding_mode: str
    ) -> tuple[
        CalcProduct,
        tuple[
            list[CalcProductMaterialLine],
            list[CalcProductLaborLine],
            list[CalcProductExtraCostLine],
        ],
        CalcProductCosts,
    ] | None:
        """Recalculate (reglas 5/6): re-resuelve los snapshots de
        materiales desde calc_materials actuales (D4: unit_cost None ->
        0.00), recalcula line_total_cost de cada linea y marca
        last_recalculated_at. Crea version SOLO si el final
        redondeado difiere del calculado ANTES de re-resolver."""
        result = await self.session.execute(
            select(CalcProductORM).where(
                CalcProductORM.id == product_id,
                CalcProductORM.deleted_at.is_(None),
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        recalculated = await self._recalculate_one(orm, rounding_mode)
        await self.session.commit()
        return recalculated

    async def recalculate_all(self, rounding_mode: str) -> int:
        """Recalculate-all (RF-P3CC-03): aplica a CADA producto
        `active` no eliminado lo mismo que el recalculate individual
        (snapshots re-resueltos, lineas recalculadas,
        last_recalculated_at en todos, version solo si el final
        redondeado cambio), en UNA sola transaccion (un unico commit
        al final). Devuelve la cantidad recalculada."""
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
        for orm in orms:
            await self._recalculate_one(orm, rounding_mode)
        await self.session.commit()
        return len(orms)

    async def _recalculate_one(
        self,
        orm: CalcProductORM,
        rounding_mode: str,
    ) -> tuple[
        CalcProduct,
        tuple[
            list[CalcProductMaterialLine],
            list[CalcProductLaborLine],
            list[CalcProductExtraCostLine],
        ],
        CalcProductCosts,
    ]:
        """Cuerpo del recalculate (reglas 5/6) SIN commit: lo comparte
        el recalculate individual (que comitea a su turno, con
        comportamiento identico al de B9) y el recalculate-all
        (transaccion unica)."""
        product_id = orm.id
        product = _product_to_domain(orm)
        material_lines, labor_lines, extra_lines = await self.get_lines(product_id)
        old_costs = compute_costs(
            material_lines,
            labor_lines,
            extra_lines,
            product.margin_percent,
            product.discount_percent,
            product.tax_percent,
            rounding_mode,
        )

        material_orms = (
            (
                await self.session.execute(
                    select(CalcMaterialORM).where(
                        CalcMaterialORM.id.in_(
                            [line.material_id for line in material_lines]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        material_by_id = {row.id: row for row in material_orms}

        for line_orm in (
            (
                await self.session.execute(
                    select(CalcProductMaterialORM).where(
                        CalcProductMaterialORM.product_id == product_id
                    )
                )
            )
            .scalars()
            .all()
        ):
            material = material_by_id.get(line_orm.material_id)
            if material is not None:
                unit_cost = (
                    Decimal(material.unit_cost)
                    if material.unit_cost is not None
                    else Decimal("0.00")
                )
                line_orm.material_name = material.name
                line_orm.unit_of_measure_snapshot = material.unit_of_measure
                line_orm.unit_cost_snapshot = str(unit_cost)
                line_orm.line_total_cost = str(
                    calc_material_line_cost(
                        Decimal(line_orm.quantity_used), unit_cost
                    )
                )
        for line_orm in (
            (
                await self.session.execute(
                    select(CalcProductLaborORM).where(
                        CalcProductLaborORM.product_id == product_id
                    )
                )
            )
            .scalars()
            .all()
        ):
            line_orm.line_total_cost = str(
                calc_labor_line_cost(
                    Decimal(line_orm.hourly_rate), Decimal(line_orm.minutes_required)
                )
            )
        for line_orm in (
            (
                await self.session.execute(
                    select(CalcProductExtraCostORM).where(
                        CalcProductExtraCostORM.product_id == product_id
                    )
                )
            )
            .scalars()
            .all()
        ):
            line_orm.line_total_cost = str(
                calc_extra_line_cost(
                    Decimal(line_orm.unit_cost), Decimal(line_orm.quantity)
                )
            )
        orm.last_recalculated_at = datetime.now(UTC)

        material_lines, labor_lines, extra_lines = await self.get_lines(product_id)
        new_costs = compute_costs(
            material_lines,
            labor_lines,
            extra_lines,
            product.margin_percent,
            product.discount_percent,
            product.tax_percent,
            rounding_mode,
        )
        if new_costs.final_sale_price != old_costs.final_sale_price:
            version_number = await self._next_version_number(product_id)
            self.session.add(
                CalcProductVersionORM(
                    id=str(uuid.uuid4()),
                    product_id=product_id,  # = orm.id
                    version_number=version_number,
                    product_total_cost=str(new_costs.product_total_cost),
                    profit_amount=str(new_costs.profit_amount),
                    discount_amount=str(new_costs.discount_amount),
                    adjusted_profit_amount=str(new_costs.adjusted_profit_amount),
                    tax_amount=str(new_costs.tax_amount),
                    final_sale_price=str(new_costs.final_sale_price),
                    changed_at=datetime.now(UTC),
                )
            )
        product = _product_to_domain(orm)
        return product, (material_lines, labor_lines, extra_lines), new_costs

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
