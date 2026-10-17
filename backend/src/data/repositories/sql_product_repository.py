from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import ProductORM, RecipeItemORM
from domain.models import Product, RecipeItem


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
        id=orm.id,
        deleted_at=orm.deleted_at,
    )


def _not_deleted():
    return [ProductORM.deleted_at.is_(None)]


class SQLProductRepository:
    """P3/P4. Montos/cantidades como TEXT (RNF-P4-02). La receta viaja
    junto al producto (lazy="selectin" en el ORM, seguro para async)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        q: Optional[str],
        category: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[List[Product], int]:
        filters = _not_deleted()
        if q and q.strip():
            # accent_fold registrada en el engine (data/db.py): "limon"
            # encuentra "Limón" sin importar acentos (RF-P3-01).
            folded = accent_fold(q) or q
            filters.append(func.accent_fold(ProductORM.name).like(f"%{folded}%"))
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

    async def get(self, product_id: str) -> Optional[Product]:
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

    async def update(self, product: Product) -> Optional[Product]:
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

    async def soft_delete(self, product_id: str) -> Optional[Product]:
        result = await self.session.execute(
            select(ProductORM).where(
                ProductORM.id == product_id,
                *(_not_deleted()),
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.deleted_at = datetime.now(timezone.utc)
        await self.session.commit()
        return _to_domain(orm)

    async def count_orders(self, product_id: str) -> int:
        # Fase 6 (pedidos): sin tabla de pedidos, ningun producto puede
        # estar referenciado. Igual que count_active_recipes pre-Fase 5.
        return 0

    async def distinct_categories(self) -> List[str]:
        result = await self.session.execute(
            select(ProductORM.category)
            .where(*_not_deleted())
            .distinct()
            .order_by(func.lower(ProductORM.category))
        )
        return [row[0] for row in result.all()]
