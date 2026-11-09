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

    first = await _take_sequence(factory)
    results = await asyncio.gather(*[_take_sequence(factory) for _ in range(10)])
    await engine.dispose()

    all_seqs = [first, *results]
    assert len(set(all_seqs)) == len(all_seqs)
    assert sorted(all_seqs) == [f"#{n:05d}" for n in range(1, 12)]


@pytest.mark.asyncio
async def test_duplicate_budget_seq_raises_integrity_error():
    from datetime import datetime, timezone

    from sqlalchemy.exc import IntegrityError

    from data.models import BudgetORM

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    now = datetime.now(timezone.utc)

    def _budget(budget_id: str) -> BudgetORM:
        return BudgetORM(
            id=budget_id, seq="#00001", customer_id="c1", customer_name="N",
            customer_phone="1", created_at=now, updated_at=now,
        )

    async with factory() as session:
        session.add(_budget("b1"))
        await session.commit()
        session.add(_budget("b2"))
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()
