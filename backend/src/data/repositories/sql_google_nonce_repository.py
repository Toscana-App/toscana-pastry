import datetime
import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import GoogleNonceORM
from domain.repositories import GoogleNonceRepository


class SQLGoogleNonceRepository(GoogleNonceRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def issue(self, nonce: str, ttl_seconds: int) -> str:
        now = datetime.datetime.now(datetime.UTC)
        nonce_id = uuid.uuid4()
        self.session.add(
            GoogleNonceORM(
                id=nonce_id,
                nonce=nonce,
                expires_at=now + datetime.timedelta(seconds=ttl_seconds),
            )
        )
        await self.session.commit()
        return str(nonce_id)

    async def consume(self, nonce_id: str) -> str | None:
        """Atomic one-time consume (same pattern as refresh-token rotation):
        a single UPDATE ... WHERE consumed_at IS NULL AND expires_at > now()
        ... RETURNING nonce. Unknown ids, expired rows and replays return None.
        """
        try:
            nonce_uuid = uuid.UUID(nonce_id)
        except (ValueError, TypeError):
            return None
        now = datetime.datetime.now(datetime.UTC)
        result = await self.session.execute(
            update(GoogleNonceORM)
            .where(
                GoogleNonceORM.id == nonce_uuid,
                GoogleNonceORM.consumed_at.is_(None),
                GoogleNonceORM.expires_at > now,
            )
            .values(consumed_at=now)
            .returning(GoogleNonceORM.nonce)
        )
        await self.session.commit()
        row = result.first()
        return row[0] if row is not None else None
