from decimal import Decimal
from typing import cast

from sqlalchemy import func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import CouponORM
from domain.coupon import Coupon, DuplicateCouponCodeError


def _to_domain(orm: CouponORM) -> Coupon:
    return Coupon(
        code=orm.code,
        type=orm.type,
        value=Decimal(orm.value),
        valid_from=orm.valid_from,
        valid_until=orm.valid_until,
        max_uses=orm.max_uses,
        status=orm.status,
        uses=orm.uses,
        id=orm.id,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_orm(domain: Coupon) -> CouponORM:
    return CouponORM(
        id=domain.id,
        code=domain.code,
        code_key=accent_fold(domain.code),
        type=domain.type,
        value=str(domain.value),
        valid_from=domain.valid_from,
        valid_until=domain.valid_until,
        max_uses=domain.max_uses,
        status=domain.status,
        uses=domain.uses,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
    )


class SQLCouponRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _commit_unique(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as err:
            await self.session.rollback()
            if "code_key" in str(err.orig):
                raise DuplicateCouponCodeError() from err
            raise

    async def list(
        self,
        q: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Coupon], int]:
        filters = []
        if q and q.strip():
            folded = accent_fold(q) or q
            filters.append(
                func.accent_fold(CouponORM.code).like(f"%{folded}%")
            )
        if status:
            filters.append(CouponORM.status == status)
        count_stmt = (
            select(func.count()).select_from(CouponORM).where(*filters)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = (
            await self.session.execute(
                select(CouponORM)
                .where(*filters)
                .order_by(func.accent_fold(CouponORM.code))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_to_domain(r) for r in rows], total

    async def get(self, coupon_id: str) -> Coupon | None:
        result = await self.session.execute(
            select(CouponORM).where(CouponORM.id == coupon_id)
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def get_by_code(self, code: str) -> Coupon | None:
        folded = accent_fold(code) or code
        result = await self.session.execute(
            select(CouponORM).where(CouponORM.code_key == folded)
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def create(self, coupon: Coupon) -> Coupon:
        self.session.add(_to_orm(coupon))
        await self._commit_unique()
        return coupon

    async def update(self, coupon: Coupon) -> Coupon | None:
        result = await self.session.execute(
            select(CouponORM).where(CouponORM.id == coupon.id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.code = coupon.code
        orm.code_key = accent_fold(coupon.code)
        orm.type = coupon.type
        orm.value = str(coupon.value)
        orm.valid_from = coupon.valid_from
        orm.valid_until = coupon.valid_until
        orm.max_uses = coupon.max_uses
        orm.status = coupon.status
        orm.updated_at = coupon.updated_at
        await self._commit_unique()
        return _to_domain(orm)

    async def set_status(
        self, coupon_id: str, status: str
    ) -> Coupon | None:
        result = await self.session.execute(
            select(CouponORM).where(CouponORM.id == coupon_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.status = status
        await self.session.commit()
        return _to_domain(orm)

    async def delete(self, coupon_id: str) -> Coupon | None:
        result = await self.session.execute(
            select(CouponORM).where(CouponORM.id == coupon_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        await self.session.delete(orm)
        await self.session.commit()
        return _to_domain(orm)

    async def increment_uses(self, coupon_id: str) -> Coupon | None:
        result = await self.session.execute(
            select(CouponORM).where(CouponORM.id == coupon_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.uses += 1
        await self.session.commit()
        return _to_domain(orm)

    async def claim_use(self, coupon_id: str) -> bool:
        """Incrementa `uses` atomicamente SOLO si no alcanza el tope.

        No hace commit: el claim se confirma junto al pedido (mismo
        transaccion) y se revierte si el pedido no se crea. Devuelve False
        si el tope se alcanzo (la corrida ganadora quedo primero).
        """
        result = cast(
            "CursorResult",
            await self.session.execute(
                update(CouponORM)
                .where(
                    CouponORM.id == coupon_id,
                    or_(
                        CouponORM.max_uses.is_(None),
                        CouponORM.uses < CouponORM.max_uses,
                    ),
                )
                .values(uses=CouponORM.uses + 1)
            ),
        )
        return (result.rowcount or 0) > 0
