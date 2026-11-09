
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
    return RecipeItem(
        ingredient_id=orm.ingredient_id,
        qty=Decimal(orm.qty),
        unit=orm.unit,
        id=orm.id,
    )


def _to_domain(orm: ProductORM) -> Product:
    return Product(
        name=orm.name,
        category=orm.category,
        recipe=tuple(_item_to_domain(item) for item in orm.recipe_items),
        description=orm.description,
        prep_time_min=orm.prep_time_min,
        servings=orm.servings,
        difficulty=orm.difficulty,
        available=orm.available,
        image_url=orm.image_url,
        id=orm.id,
        deleted_at=orm.deleted_at,
    )


def _not_deleted():
    return [ProductORM.deleted_at.is_(None)]


class SQLProductRepository(ProductRepository):

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
        if q is not None:
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
            available=product.available,
            image_url=product.image_url,
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
        orm.name = product.name
        orm.category = product.category
        orm.description = product.description
        orm.prep_time_min = product.prep_time_min
        orm.servings = product.servings
        orm.difficulty = product.difficulty
        orm.available = product.available
        orm.image_url = product.image_url
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
        orm.deleted_at = datetime.now(UTC)
        await self.session.commit()
        return _to_domain(orm)

    async def count_orders(self, product_id: str) -> int:
        return 0

    async def distinct_categories(self) -> list[str]:
        result = await self.session.execute(
            select(ProductORM.category)
            .where(*_not_deleted())
            .group_by(ProductORM.category)
            .order_by(func.lower(ProductORM.category))
        )
        return [row[0] for row in result.all()]
