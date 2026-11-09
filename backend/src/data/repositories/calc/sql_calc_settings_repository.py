from typing import Optional
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.calc_settings import CalcSettings, DEFAULT_CALC_SETTINGS
from data.models import CalcSettingsORM


def _to_domain(orm: CalcSettingsORM) -> CalcSettings:
    return CalcSettings(
        business_name=orm.business_name,
        main_currency_name=orm.main_currency_name,
        main_currency_symbol=orm.main_currency_symbol,
        default_margin_percent=Decimal(orm.default_margin_percent),
        default_discount_percent=Decimal(orm.default_discount_percent),
        default_tax_percent=Decimal(orm.default_tax_percent),
        rounding_mode=orm.rounding_mode,
    )


class SQLCalcSettingsRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self) -> Optional[CalcSettings]:
        result = await self.session.execute(select(CalcSettingsORM).limit(1))
        orm = result.scalars().first()
        if orm is None:
            return DEFAULT_CALC_SETTINGS
        return _to_domain(orm)

    async def save(self, settings: CalcSettings) -> CalcSettings:
        result = await self.session.execute(select(CalcSettingsORM).limit(1))
        orm = result.scalars().first()
        values = dict(
            business_name=settings.business_name,
            main_currency_name=settings.main_currency_name,
            main_currency_symbol=settings.main_currency_symbol,
            default_margin_percent=str(settings.default_margin_percent),
            default_discount_percent=str(settings.default_discount_percent),
            default_tax_percent=str(settings.default_tax_percent),
            rounding_mode=settings.rounding_mode,
        )
        if orm is None:
            orm = CalcSettingsORM(**values)
            self.session.add(orm)
        else:
            for key, value in values.items():
                setattr(orm, key, value)
        await self.session.commit()
        return settings
