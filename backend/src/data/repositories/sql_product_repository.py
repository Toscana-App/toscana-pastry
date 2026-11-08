"""Producto y receta (RF-P2-10/11). Money como String (RNF-P4-02)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import build_search_pattern
from data.models import ProductORM, RecipeItemORM
from domain.models import Product, RecipeItem
from domain.repositories import ProductRepository


def _item_to_domain(orm: RecipeItemORM) -> RecipeItem:
    return RecipeItem(  # type: ignore[arg-type]
        ingredient_id=orm.ingredient_id,  # type: ignore[arg-type]
        qty=Decimal(orm.qty),  # type: ignore[arg-type]
        unit=orm.unit,  # type: ignore[arg-type]
        id=orm.id,  # type: ignore[arg-type]
    )


def _to_domain(orm: ProductORM) -> Product:
    return Product(  # type: ignore[arg-type]
        name=orm.name,  # type: ignore[arg-type]
        category=orm.category,  # type: ignore[arg-type]
        recipe=tuple(_item_to_domain(item) for item in orm.recipe_items),  # type: ignore[arg-type]
        description=orm.description,  # type: ignore[arg-type]
        prep_time_min=orm.prep_time_min,  # type: ignore[arg-type]
        servings=orm.servings,  # type: ignore[arg-type]
        difficulty=orm.difficulty,  # type: ignore[arg-type]
        id=orm.id,  # type: ignore[arg-type]
        deleted_at=orm.deleted_at,  # type: ignore[arg-type]
    )


def _not_deleted():
    return [ProductORM.deleted_at.is_(None)]  # type: ignore[misc]


class SQLProductRepository(ProductRepository):
    """P3/P4. Montos/cantidades como TEXT (RNF-P4-02). La receta viaja
    junto al producto (lazy="selectin" en el ORM, seguro para async)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        q: str | None,
        category: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Product], int]:
        filters: list = _not_deleted()
        if q is not None:  # estricto: blank/control/>120 → 422 (min_length=1 evita q="")
            # accent_fold registrada en el engine (data/db.py): "limon"
            # encuentra "Limón" sin importar acentos (RF-P3-01).
            # build_search_pattern valida, pliega y escapa los metacaracteres
            # de LIKE (substring literal); el valor viaja como parámetro bind.
            filters.append(
                func.accent_fold(ProductORM.name).like(
                    build_search_pattern(q), escape="\\"
                )
            )
        if category:
            filters.append(ProductORM.category == category)
        total = (
            await self.session.execute(
                select(func.count())
                .select_from(ProductORM)
                .where(*filters)
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(ProductORM)
                .where(*filters)
                .order_by(func.lower(ProductORM.name))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_to_domain(orm) for orm in rows], total

    async def get(self, product_id: str) -> Product | None:
        result = await self.session.execute(
            select(ProductORM).where(
                ProductORM.id == product_id,
                *(_not_deleted()),
            )
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def create(self, product: Product) -> Product:
        orm = ProductORM(
            id=product.id,
            name=product.name,
            category=product.category,
            description=product.description,
            prep_time_min=product.prep_time_min,
            servings=product.servings,
            difficulty=product.difficulty,
        )
        orm.recipe_items = [
            RecipeItemORM(
                id=item.id,
                ingredient_id=item.ingredient_id,
                qty=str(item.qty),
                unit=item.unit,
                position=index,
            )
            for index, item in enumerate(product.recipe)
        ]
        self.session.add(orm)
        await self.session.commit()
        return product

    async def update(self, product: Product) -> Product | None:
        result = await self.session.execute(
            select(ProductORM).where(
                ProductORM.id == product.id,
                *(_not_deleted()),
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.name = product.name  # type: ignore[arg-type]
        orm.category = product.category  # type: ignore[arg-type]
        orm.description = product.description  # type: ignore[arg-type]
        orm.prep_time_min = product.prep_time_min  # type: ignore[arg-type]
        orm.servings = product.servings  # type: ignore[arg-type]
        orm.difficulty = product.difficulty  # type: ignore[arg-type]
        # La receta se reemplaza en bloque (RF-P4-02): cascade
        # delete-orphan limpia las lineas viejas.
        orm.recipe_items = [
            RecipeItemORM(
                id=item.id,
                ingredient_id=item.ingredient_id,
                qty=str(item.qty),
                unit=item.unit,
                position=index,
            )
            for index, item in enumerate(product.recipe)
        ]
        await self.session.commit()
        return product

    async def soft_delete(self, product_id: str) -> Product | None:
        result = await self.session.execute(
            select(ProductORM).where(
                ProductORM.id == product_id,
                *(_not_deleted()),
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.deleted_at = datetime.now(UTC)  # type: ignore[arg-type]
        await self.session.commit()
        return _to_domain(orm)

    async def count_orders(self, product_id: str) -> int:
        # Fase 6 (pedidos): sin tabla de pedidos, ningun producto puede
        # estar referenciado. Igual que count_active_recipes pre-Fase 5.
        return 0

    async def distinct_categories(self) -> list[str]:
        result = await self.session.execute(
            select(ProductORM.category)
            .where(*_not_deleted())
            .group_by(ProductORM.category)
            .order_by(func.lower(ProductORM.category))
        )
        return [row[0] for row in result.all()]
