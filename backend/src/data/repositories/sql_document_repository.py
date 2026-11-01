"""SQL de PDFs de presupuesto (Fase 8, P9).

Una fila vigente por presupuesto, clave (budget_id, content_hash):
editado el contenido → hash nuevo → save() reemplaza la fila (el PDF
viejo se descarta; no hay valor en conservar versiones del documento).
El binario vive en la DB (SQLite): a esta escala la simplicidad de un
solo store justifica el costo.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import BudgetDocumentORM


class SQLDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, budget_id: str, content_hash: str) -> Optional[bytes]:
        result = await self.session.execute(
            select(BudgetDocumentORM).where(
                BudgetDocumentORM.budget_id == budget_id,
                BudgetDocumentORM.content_hash == content_hash,
            )
        )
        orm = result.scalars().first()
        return orm.pdf_data if orm is not None else None

    async def save(self, budget_id: str, content_hash: str, pdf: bytes) -> None:
        result = await self.session.execute(
            select(BudgetDocumentORM).where(
                BudgetDocumentORM.budget_id == budget_id
            )
        )
        orm = result.scalars().first()
        now = datetime.now(timezone.utc)
        try:
            if orm is None:
                orm = BudgetDocumentORM(
                    id=str(uuid.uuid4()),
                    budget_id=budget_id,
                    content_hash=content_hash,
                    pdf_data=pdf,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(orm)
            else:
                orm.content_hash = content_hash
                orm.pdf_data = pdf
                orm.updated_at = now
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
