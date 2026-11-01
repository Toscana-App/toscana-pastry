"""Repository de envios WhatsApp (RF-P10-07/08, C7).

Mapeo ORM↔dominio y operaciones: list con filtros (status, rango de
fechas, paginacion, orden desc por sent_at), stats por ventana y
conteo por provider desde una fecha (budget RNF-P10-06).
"""

from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import WhatsAppSendORM
from domain.whatsapp_send import WhatsAppSend


def _aware(value: datetime.datetime | None) -> datetime.datetime | None:
    """SQLite devuelve datetimes naive; el contrato de dominio es UTC aware.

    Normaliza a aware-UTC cuando el backend (SQLite) no preserva el tzinfo.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.UTC)
    return value


def _to_domain(orm: WhatsAppSendORM) -> WhatsAppSend:
    return WhatsAppSend(  # type: ignore[arg-type]
        id=orm.id,  # type: ignore[arg-type]
        provider=orm.provider,  # type: ignore[arg-type]
        phone=orm.phone,  # type: ignore[arg-type]
        message=orm.message,  # type: ignore[arg-type]
        reference_kind=orm.reference_kind,  # type: ignore[arg-type]
        reference_id=orm.reference_id,  # type: ignore[arg-type]
        sent_at=_aware(orm.sent_at),  # type: ignore[arg-type]
        status=orm.status,  # type: ignore[arg-type]
        message_id=orm.message_id,  # type: ignore[arg-type]
        failed_reason=orm.failed_reason,  # type: ignore[arg-type]
        delivered_at=_aware(orm.delivered_at),  # type: ignore[arg-type]
        read_at=_aware(orm.read_at),  # type: ignore[arg-type]
    )


def _to_orm(domain: WhatsAppSend) -> WhatsAppSendORM:
    return WhatsAppSendORM(
        id=domain.id,
        provider=domain.provider,
        phone=domain.phone,
        message=domain.message,
        reference_kind=domain.reference_kind,
        reference_id=domain.reference_id,
        sent_at=domain.sent_at,
        status=domain.status,
        message_id=domain.message_id,
        failed_reason=domain.failed_reason,
        delivered_at=domain.delivered_at,
        read_at=domain.read_at,
    )


class SQLWhatsAppSendRepository:
    """SQL repository for WhatsAppSend entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, send: WhatsAppSend) -> WhatsAppSend:
        self.session.add(_to_orm(send))
        await self.session.commit()
        return send

    async def update(self, send: WhatsAppSend) -> WhatsAppSend:
        """Persiste un envio actualizado (estado/timestamps)."""
        result = await self.session.execute(
            select(WhatsAppSendORM).where(WhatsAppSendORM.id == send.id)
        )
        orm = result.scalars().first()
        if orm is None:
            return send
        orm.provider = send.provider  # type: ignore[assignment]
        orm.phone = send.phone  # type: ignore[assignment]
        orm.message = send.message  # type: ignore[assignment]
        orm.reference_kind = send.reference_kind  # type: ignore[assignment]
        orm.reference_id = send.reference_id  # type: ignore[assignment]
        orm.sent_at = send.sent_at  # type: ignore[assignment]
        orm.status = send.status  # type: ignore[assignment]
        orm.message_id = send.message_id  # type: ignore[assignment]
        orm.failed_reason = send.failed_reason  # type: ignore[assignment]
        orm.delivered_at = send.delivered_at  # type: ignore[assignment]
        orm.read_at = send.read_at  # type: ignore[assignment]
        await self.session.commit()
        return send

    async def get(self, send_id: str) -> WhatsAppSend | None:
        result = await self.session.execute(
            select(WhatsAppSendORM).where(WhatsAppSendORM.id == send_id)
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def list(
        self,
        *,
        status: str | None = None,
        from_: datetime.datetime | None = None,
        to: datetime.datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[WhatsAppSend], int]:
        """Lista envios con filtros ?status, ?from, ?to (paginado, desc)."""
        filters = []
        if status:
            filters.append(WhatsAppSendORM.status == status)
        if from_ is not None:
            filters.append(WhatsAppSendORM.sent_at >= from_)
        if to is not None:
            filters.append(WhatsAppSendORM.sent_at <= to)

        count_stmt = (
            select(func.count()).select_from(WhatsAppSendORM).where(*filters)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()

        rows = (
            await self.session.execute(
                select(WhatsAppSendORM)
                .where(*filters)
                .order_by(WhatsAppSendORM.sent_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return [_to_domain(r) for r in rows], total

    async def stats(self, *, window_days: int = 30) -> dict[str, int]:
        """Agrega envios por estado en la ultima ventana (dias)."""
        since = (
            datetime.datetime.now(datetime.UTC)
            - datetime.timedelta(days=window_days)
        )
        rows = (
            await self.session.execute(
                select(WhatsAppSendORM.status, func.count())
                .where(WhatsAppSendORM.sent_at >= since)
                .group_by(WhatsAppSendORM.status)
            )
        ).all()

        counts = dict.fromkeys(("sent", "delivered", "read", "failed"), 0)
        counts: dict[str, int]
        for status, count in rows:
            if status in counts:
                counts[status] = int(count)
        counts["total"] = sum(counts.values())
        return counts

    async def count_provider_since(
        self, *, provider: str, since: datetime.datetime
    ) -> int:
        """Cuenta envios de un provider desde una fecha (budget RNF-P10-06)."""
        result = await self.session.execute(
            select(func.count())
            .select_from(WhatsAppSendORM)
            .where(
                WhatsAppSendORM.provider == provider,
                WhatsAppSendORM.sent_at >= since,
            )
        )
        return int(result.scalar_one())
