"""Secuencia #000NN de presupuestos (RNF-P8-04).

SQLite no soporta SELECT ... FOR UPDATE ni concurrencia real de filas: este
test usa una base en archivo con sesiones independientes y asyncio.gather.
Prueba que el UPDATE atomico no entrega valores repetidos ni salta numeros
cuando varias transacciones compiten (SQLite serializa los escritores). No
prueba el bloqueo de fila de PostgreSQL.
"""
import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from data.models import Base
from data.repositories.sql_budget_repository import SQLBudgetRepository


async def _take_sequence(factory) -> str:
    async with factory() as session:
        seq = await SQLBudgetRepository(session)._next_sequence()
        await session.commit()
        return seq


@pytest.mark.asyncio
async def test_concurrent_sequences_are_unique_and_gapless(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{(tmp_path / 'seq.db').as_posix()}"
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # First call creates the row; the rest compete for it.
    first = await _take_sequence(factory)
    results = await asyncio.gather(*[_take_sequence(factory) for _ in range(10)])
    await engine.dispose()

    all_seqs = [first, *results]
    assert len(set(all_seqs)) == len(all_seqs)
    assert sorted(all_seqs) == [f"#{n:05d}" for n in range(1, 12)]
