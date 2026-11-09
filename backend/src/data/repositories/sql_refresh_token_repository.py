import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import RefreshTokenORM
from domain.repositories import RefreshTokenRepository


class SQLRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(
        self, jti: str, user_id: str, family_id: str, expires_at: datetime.datetime
    ) -> None:
        self.session.add(
            RefreshTokenORM(
                jti=jti, user_id=user_id, family_id=family_id, expires_at=expires_at
            )
        )
        await self.session.commit()

    async def consume(self, jti: str) -> bool:
        now = datetime.datetime.now(datetime.UTC)
        result = await self.session.execute(
            update(RefreshTokenORM)
            .where(
                RefreshTokenORM.jti == jti,
                RefreshTokenORM.revoked_at.is_(None),
                RefreshTokenORM.expires_at > now,
            )
            .values(revoked_at=now)
        )
        await self.session.commit()
        return result.rowcount == 1

    async def revoke_family(self, family_id: str) -> None:
        await self.session.execute(
            update(RefreshTokenORM)
            .where(
                RefreshTokenORM.family_id == family_id,
                RefreshTokenORM.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.datetime.now(datetime.UTC))
        )
        await self.session.commit()
