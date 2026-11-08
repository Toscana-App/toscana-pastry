from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import REAL, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import build_search_pattern
from data.models import IngredientORM, ProductORM, RecipeItemORM, StockMovementORM
from domain.models import Ingredient, StockMovement, StockStatus


def _to_domain(orm: IngredientORM) -> Ingredient:
    return Ingredient(  # type: ignore[arg-type]
        name=orm.name,  # type: ignore[arg-type]
        unit=orm.unit,  # type: ignore[arg-type]
        price_per_unit=Decimal(orm.price_per_unit),  # type: ignore[arg-type]
        stock_qty=Decimal(orm.stock_qty),  # type: ignore[arg-type]
        low_stock_threshold=Decimal(orm.low_stock_threshold),  # type: ignore[arg-type]
        id=orm.id,  # type: ignore[arg-type]
        deleted_at=orm.deleted_at,  # type: ignore[arg-type]
    )


def _movement_to_domain(orm: StockMovementORM) -> StockMovement:
    return StockMovement(  # type: ignore[arg-type]
        qty_delta=Decimal(orm.qty_delta),  # type: ignore[arg-type]
        reason=orm.reason,  # type: ignore[arg-type]
        id=orm.id,  # type: ignore[arg-type]
        ingredient_id=orm.ingredient_id,  # type: ignore[arg-type]
        ref=orm.ref,  # type: ignore[arg-type]
        created_at=orm.created_at,  # type: ignore[arg-type]
    )


def _not_deleted():
    return [IngredientORM.deleted_at.is_(None)]


def _status_filter(status: StockStatus):
    """Estado derivado comparado en SQL. El CAST a REAL es solo para
    comparar (cero / orden); ninguna aritmetica de dinero pasa por aca."""
    qty = func.cast(IngredientORM.stock_qty, REAL)
    threshold = func.cast(IngredientORM.low_stock_threshold, REAL)
    if status is StockStatus.EMPTY:
        return qty == 0
    if status is StockStatus.LOW:
        return (qty > 0) & (qty <= threshold)
    return qty > threshold


class SQLIngredientRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        q: Optional[str],
        status: Optional[StockStatus],
        page: int,
        page_size: int,
    ) -> Tuple[List[Ingredient], int]:
        filters = _not_deleted()
        if q and q.strip():
            # accent_fold esta registrada en el engine (data/db.py): "cafe"
            # encuentra "Cafe" sin importar acentos. build_search_pattern
            # valida el término (422 vía SearchQueryError), pliega acentos y
            # escapa los metacaracteres de LIKE: la búsqueda es siempre un
            # substring literal (anti wildcard-injection); `escape="\"` hace
            # que SQLite y Postgres respeten el escape. El valor viaja como
            # parámetro bind, nunca concatena texto SQL.
            filters.append(
                func.accent_fold(IngredientORM.name).like(
                    build_search_pattern(q), escape="\\"
                )
            )
        if status is not None:
            filters.append(_status_filter(status))
        total = (
            await self.session.execute(
                select(func.count())
                .select_from(IngredientORM)
                .where(*filters)
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(IngredientORM)
                .where(*filters)
                .order_by(func.lower(IngredientORM.name))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_to_domain(orm) for orm in rows], total

    async def get(self, ingredient_id: str) -> Optional[Ingredient]:
        result = await self.session.execute(
            select(IngredientORM).where(
                IngredientORM.id == ingredient_id,
                *(_not_deleted()),
            )
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def get_many(self, ingredient_ids: Sequence[str]) -> List[Ingredient]:
        if not ingredient_ids:
            return []
        result = await self.session.execute(
            select(IngredientORM).where(
                IngredientORM.id.in_(set(ingredient_ids)),
                *(_not_deleted()),
            )
        )
        return [_to_domain(orm) for orm in result.scalars().all()]

    async def create(
        self,
        ingredient: Ingredient,
        initial_movement: Optional[StockMovement] = None,
    ) -> Ingredient:
        self.session.add(
            IngredientORM(
                id=ingredient.id,
                name=ingredient.name,
                unit=ingredient.unit,
                price_per_unit=str(ingredient.price_per_unit),
                stock_qty=str(ingredient.stock_qty),
                low_stock_threshold=str(ingredient.low_stock_threshold),
            )
        )
        if initial_movement is not None:
            self.session.add(self._movement_orm(ingredient.id, initial_movement))
        await self.session.commit()
        return ingredient

    async def update(self, ingredient: Ingredient) -> Optional[Ingredient]:
        result = await self.session.execute(
            select(IngredientORM).where(
                IngredientORM.id == ingredient.id,
                *(_not_deleted()),
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.name = ingredient.name
        orm.unit = ingredient.unit
        orm.price_per_unit = str(ingredient.price_per_unit)
        orm.low_stock_threshold = str(ingredient.low_stock_threshold)
        await self.session.commit()
        return ingredient

    async def soft_delete(self, ingredient_id: str) -> Optional[Ingredient]:
        result = await self.session.execute(
            select(IngredientORM).where(
                IngredientORM.id == ingredient_id,
                *(_not_deleted()),
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.deleted_at = datetime.now(timezone.utc)
        await self.session.commit()
        return _to_domain(orm)

    async def count_active_recipes(self, ingredient_id: str) -> int:
        # Fase 5 (productos): cuenta los productos NO borrados cuya receta
        # referencia a este insumo. Alimenta el 409 de borrado (UC-05).
        result = await self.session.execute(
            select(func.count())
            .select_from(RecipeItemORM)
            .join(ProductORM, RecipeItemORM.product_id == ProductORM.id)
            .where(
                RecipeItemORM.ingredient_id == ingredient_id,
                ProductORM.deleted_at.is_(None),
            )
        )
        return result.scalar_one()

    def _movement_orm(self, ingredient_id: str, movement: StockMovement):
        return StockMovementORM(
            id=movement.id,
            ingredient_id=ingredient_id,
            qty_delta=str(movement.qty_delta),
            reason=movement.reason,
            ref=movement.ref,
            created_at=movement.created_at,
        )

    async def add_movement(
        self,
        ingredient_id: str,
        movement: StockMovement,
        new_stock_qty: Decimal,
    ) -> Optional[StockMovement]:
        """Stock nuevo y movimiento en UN commit: el historial y el saldo
        nunca divergen (RF-P2-04)."""
        result = await self.session.execute(
            select(IngredientORM).where(
                IngredientORM.id == ingredient_id,
                *(_not_deleted()),
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.stock_qty = str(new_stock_qty)
        self.session.add(self._movement_orm(ingredient_id, movement))
        await self.session.commit()
        return movement

    async def list_movements(
        self, ingredient_id: str, page: int, page_size: int
    ) -> Tuple[List[StockMovement], int]:
        total = (
            await self.session.execute(
                select(func.count())
                .select_from(StockMovementORM)
                .where(StockMovementORM.ingredient_id == ingredient_id)
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(StockMovementORM)
                .where(StockMovementORM.ingredient_id == ingredient_id)
                .order_by(
                    StockMovementORM.created_at.desc(),
                    StockMovementORM.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_movement_to_domain(orm) for orm in rows], total
