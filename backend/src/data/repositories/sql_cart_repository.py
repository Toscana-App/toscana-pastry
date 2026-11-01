"""Repository del carrito server-side (RF-P11-03, C4).

Mapeo ORM↔dominio. El carrito persiste solo (product_id, qty) + el cupon
aplicado: el precio se deriva en cada lectura (RNF-P11-03).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import CartItemORM, CartORM


class SQLCartRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_state(
        self, user_id: str
    ) -> tuple[list[tuple[str, int]], str | None]:
        """Devuelve ((product_id, qty)[...], coupon_code | None)."""
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
        """Crea o actualiza la cantidad de la linea (idempotente)."""
        result = await self.session.execute(
            select(CartItemORM).where(
                CartItemORM.user_id == user_id,
                CartItemORM.product_id == product_id,
            )
        )
        row = result.scalars().first()
        if row is not None:
            row.qty = qty
        else:
            self.session.add(
                CartItemORM(user_id=user_id, product_id=product_id, qty=qty)
            )
        await self._touch_cart(user_id)

    async def remove_item(self, user_id: str, product_id: str) -> bool:
        """Elimina la linea. True si existía."""
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
        await self._touch_cart(user_id)
        return True

    async def set_coupon_code(self, user_id: str, code: str) -> None:
        await self._touch_cart(user_id)
        cart = await self.session.get(CartORM, user_id)
        assert cart is not None  # _touch_cart la crea si no existe
        cart.coupon_code = code

    async def clear_coupon(self, user_id: str) -> None:
        cart = await self.session.get(CartORM, user_id)
        if cart is not None:
            cart.coupon_code = None
            await self._touch_cart(user_id)

    async def commit(self) -> None:
        await self.session.commit()

    async def _touch_cart(self, user_id: str) -> None:
        """Garantiza el registro del carrito para el usuario."""
        cart = await self.session.get(CartORM, user_id)
        if cart is None:
            self.session.add(CartORM(user_id=user_id))
            await self.session.flush()
