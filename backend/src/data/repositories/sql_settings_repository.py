from typing import Optional
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domain.models import BusinessSettings
from data.models import BusinessSettingsORM

def _to_domain(orm: BusinessSettingsORM) -> BusinessSettings:
    return BusinessSettings(
        hourly_rate=Decimal(orm.hourly_rate),
        margin_pct=Decimal(orm.margin_pct),
        round_step=Decimal(orm.round_step),
        include_labor=orm.include_labor,
        include_gas=orm.include_gas,
        gas_pct=Decimal(orm.gas_pct if orm.gas_pct is not None else "0"),
        include_waste=orm.include_waste,
        waste_pct=Decimal(orm.waste_pct if orm.waste_pct is not None else "0"),
        urgent_surcharge_pct=Decimal(
            orm.urgent_surcharge_pct if orm.urgent_surcharge_pct is not None else "0"
        ),
        default_prep_minutes=orm.default_prep_minutes,
        default_servings=orm.default_servings,
        default_difficulty=orm.default_difficulty,
    )

class SQLSettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self) -> Optional[BusinessSettings]:
        result = await self.session.execute(select(BusinessSettingsORM).limit(1))
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def save(self, settings: BusinessSettings) -> BusinessSettings:
        result = await self.session.execute(select(BusinessSettingsORM).limit(1))
        orm = result.scalars().first()
        values = dict(
            hourly_rate=str(settings.hourly_rate),
            margin_pct=str(settings.margin_pct),
            round_step=str(settings.round_step),
            gas_pct=str(settings.gas_pct),
            waste_pct=str(settings.waste_pct),
            urgent_surcharge_pct=str(settings.urgent_surcharge_pct),
            include_labor=settings.include_labor,
            include_gas=settings.include_gas,
            include_waste=settings.include_waste,
            default_prep_minutes=settings.default_prep_minutes,
            default_servings=settings.default_servings,
            default_difficulty=settings.default_difficulty,
        )
        if orm is None:
            orm = BusinessSettingsORM(**values)
            self.session.add(orm)
        else:
            for key, value in values.items():
                setattr(orm, key, value)
        await self.session.commit()
        return settings
