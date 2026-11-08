from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import ImportRowORM, ImportSessionORM
from domain.imports import (
    ImportRow,
    ImportRowStatus,
    ImportSession,
    ImportStatus,
    STAGING_TTL,
)
from domain.repositories import ImportRepository

_CHUNK_SIZE = 500


def _chunks(seq: Sequence[Any], size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


class SQLImportRepository(ImportRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, session: ImportSession) -> ImportSession:
        self.session.add(
            ImportSessionORM(
                id=session.id,
                tenant_id=session.tenant_id,
                user_id=session.user_id,
                entity=session.entity,
                status=session.status.value,
                filename=session.filename,
                delimiter=session.delimiter,
                encoding=session.encoding,
                template_columns=json.dumps(session.template_columns, ensure_ascii=False),
                total_rows=session.total_rows,
                valid_rows=session.valid_rows,
                invalid_rows=session.invalid_rows,
                created_at=session.created_at,
                confirmed_at=session.confirmed_at,
            )
        )
        await self.session.commit()
        return session

    async def bulk_insert_rows(
        self, import_id: str, tenant_id: str, rows: Sequence[ImportRow]
    ) -> int:
        for chunk in _chunks(rows, _CHUNK_SIZE):
            self.session.add_all(
                [
                    ImportRowORM(
                        id=str(uuid.uuid4()),
                        import_id=import_id,
                        tenant_id=tenant_id,
                        row_number=row.row_number,
                        status=row.status.value,
                        data=json.dumps(row.data, ensure_ascii=False),
                        errors=json.dumps(list(row.errors), ensure_ascii=False),
                    )
                    for row in chunk
                ]
            )
            await self.session.flush()
        await self.session.commit()
        return len(rows)

    async def get_session(
        self, import_id: str, tenant_id: str
    ) -> ImportSession | None:
        result = await self.session.execute(
            select(ImportSessionORM).where(
                ImportSessionORM.id == import_id,
                ImportSessionORM.tenant_id == tenant_id,
            )
        )
        orm = result.scalars().first()
        return self._to_session(orm) if orm is not None else None

    async def list_rows(
        self,
        import_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ImportRow], int]:
        stmt = select(ImportRowORM).where(ImportRowORM.import_id == import_id)
        if status is not None:
            stmt = stmt.where(ImportRowORM.status == status)
        count_stmt = select(func.count(ImportRowORM.id)).where(
            ImportRowORM.import_id == import_id
        )
        if status is not None:
            count_stmt = count_stmt.where(ImportRowORM.status == status)
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = (
            (
                await self.session.execute(
                    stmt.order_by(ImportRowORM.row_number)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return [self._to_row(orm) for orm in rows], total

    async def set_status(
        self,
        import_id: str,
        status: str,
        confirmed_at: datetime | None = None,
    ) -> None:
        values: dict[str, Any] = {"status": status}
        if confirmed_at is not None:
            values["confirmed_at"] = confirmed_at
        await self.session.execute(
            update(ImportSessionORM)
            .where(ImportSessionORM.id == import_id)
            .values(**values)
        )

    async def delete_staging_rows(self, import_id: str) -> int:
        result = await self.session.execute(
            delete(ImportRowORM).where(ImportRowORM.import_id == import_id)
        )
        return result.rowcount

    async def purge_expired(self, now: datetime) -> int:
        cutoff = now - STAGING_TTL
        result = await self.session.execute(
            delete(ImportSessionORM).where(ImportSessionORM.created_at < cutoff)
        )
        await self.session.commit()
        return result.rowcount

    @staticmethod
    def _to_session(orm: ImportSessionORM) -> ImportSession:
        return ImportSession(
            id=orm.id,
            tenant_id=orm.tenant_id,
            user_id=orm.user_id,
            entity=orm.entity,
            status=ImportStatus(orm.status),
            filename=orm.filename,
            delimiter=orm.delimiter,
            encoding=orm.encoding,
            template_columns=json.loads(orm.template_columns),
            total_rows=orm.total_rows,
            valid_rows=orm.valid_rows,
            invalid_rows=orm.invalid_rows,
            created_at=orm.created_at,
            confirmed_at=orm.confirmed_at,
        )

    @staticmethod
    def _to_row(orm: ImportRowORM) -> ImportRow:
        return ImportRow(
            row_number=orm.row_number,
            status=ImportRowStatus(orm.status),
            data=json.loads(orm.data),
            errors=json.loads(orm.errors),
        )
