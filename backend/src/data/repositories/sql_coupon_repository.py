"""Repository para cupones (RF-P11-14, C3).

Estilo sql_calc_supplier_repository.py: mapeo ORM↔dominio y commit en
cada mutacion. La unicidad case/accent-insensitive de `code` se resuelve con la
columna `code_key` (= accent_fold(code), UNIQUE); un IntegrityError
sobre ella se traduce a DuplicateCouponCodeError.

`get_by_code` e `increment_uses` quedan limpios para C4 (carrito:
aplicar cupon + confirmar pedido).
"""
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import CouponORM
from domain.coupon import Coupon, DuplicateCouponCodeError


def _to_domain(orm: CouponORM) -> Coupon:
    # SQLite devuelve valid_from/valid_until naive: el dominio los
    # reconvierte a aware UTC (Coupon._aware_utc).
    return Coupon(
        code=orm.code,
        type=orm.type,  # type: ignore[arg-type]
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
        """Listado admin: ?q case/accent-insensitive en code, ?status."""
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
        """Busca case/accent-insensitive (unicidad, RF-P11-14)."""
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
        """Cambia el status (pausa-reactiva, y el auto-pause de DELETE)."""
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
        """Incrementa el contador de usos.

        C3 no lo invoca: C4 lo consumira al confirmar un pedido
        (snapshoteo de coupon_code + discount_amount, RF-P11-14).
        """
        result = await self.session.execute(
            select(CouponORM).where(CouponORM.id == coupon_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.uses += 1
        await self.session.commit()
        return _to_domain(orm)
