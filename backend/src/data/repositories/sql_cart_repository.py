
import datetime
from typing import cast

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import CartItemORM, CartORM
from domain.cart import CART_TTL_DAYS


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


class SQLCartRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_state(
        self, user_id: str
    ) -> tuple[list[tuple[str, int]], str | None]:
        cutoff = _now() - datetime.timedelta(days=CART_TTL_DAYS)
        pruned = cast(
            "CursorResult",
            await self.session.execute(
                delete(CartItemORM).where(
                    CartItemORM.user_id == user_id,
                    CartItemORM.updated_at < cutoff,
                )
            ),
        )
        if pruned.rowcount:
            remaining = await self.count_items(user_id)
            if remaining == 0:
                cart = await self.session.get(CartORM, user_id)
                if cart is not None and cart.coupon_code is not None:
                    cart.coupon_code = None
            await self.session.commit()
        cart = await self.session.get(CartORM, user_id)
        coupon_code = cart.coupon_code if cart is not None else None
        result = await self.session.execute(
            select(CartItemORM).where(CartItemORM.user_id == user_id)
        )
        lines = [(row.product_id, row.qty) for row in result.scalars().all()]
        return lines, coupon_code

    async def count_items(self, user_id: str) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(CartItemORM)
            .where(CartItemORM.user_id == user_id)
        )
        return int(result.scalar_one())

    async def item_exists(self, user_id: str, product_id: str) -> bool:
        result = await self.session.execute(
            select(CartItemORM).where(
                CartItemORM.user_id == user_id,
                CartItemORM.product_id == product_id,
            )
        )
        return result.scalars().first() is not None

    async def upsert_item(
        self, user_id: str, product_id: str, qty: int
    ) -> None:
        result = await self.session.execute(
            select(CartItemORM).where(
                CartItemORM.user_id == user_id,
                CartItemORM.product_id == product_id,
            )
        )
        row = result.scalars().first()
        if row is not None:
            row.qty = qty
            row.updated_at = _now()
        else:
            self.session.add(
                CartItemORM(
                    user_id=user_id,
                    product_id=product_id,
                    qty=qty,
                    updated_at=_now(),
                )
            )
        await self._touch_cart(user_id)

    async def remove_item(self, user_id: str, product_id: str) -> bool:
        result = await self.session.execute(
            select(CartItemORM).where(
                CartItemORM.user_id == user_id,
                CartItemORM.product_id == product_id,
            )
        )
        row = result.scalars().first()
        if row is None:
            return False
        await self.session.delete(row)
        if await self.count_items(user_id) == 0:
            await self.clear_coupon(user_id)
        await self._touch_cart(user_id)
        return True

    async def delete_lines(self, user_id: str, product_ids: list[str]) -> int:
        """Elimina lineas (ej: productos eliminados). Devuelve cuantas."""
        if not product_ids:
            return 0
        result = cast(
            "CursorResult",
            await self.session.execute(
                delete(CartItemORM).where(
                    CartItemORM.user_id == user_id,
                    CartItemORM.product_id.in_(product_ids),
                )
            ),
        )
        await self.session.commit()
        return result.rowcount or 0

    async def set_coupon_code(self, user_id: str, code: str) -> None:
        await self._touch_cart(user_id)
        cart = await self.session.get(CartORM, user_id)
        assert cart is not None
        cart.coupon_code = code

    async def clear_coupon(self, user_id: str) -> None:
        cart = await self.session.get(CartORM, user_id)
        if cart is not None:
            cart.coupon_code = None
            await self._touch_cart(user_id)

    async def commit(self) -> None:
        await self.session.commit()

    async def _touch_cart(self, user_id: str) -> None:
        cart = await self.session.get(CartORM, user_id)
        if cart is None:
            self.session.add(CartORM(user_id=user_id))
            await self.session.flush()
