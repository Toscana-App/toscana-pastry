from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING, Sequence

from domain.models import UserRole

if TYPE_CHECKING:
    from domain.models import BusinessSettings

_CENT = Decimal("0.01")


def derive_audience_price(
    base_price: Decimal,
    consumer_markup_pct: Decimal,
    audience: str,
) -> Decimal:
    if audience == "consumidor_final":
        markup = consumer_markup_pct / Decimal("100")
        return (base_price * (Decimal("1") + markup)).quantize(
            _CENT, rounding=ROUND_HALF_UP
        )
    return base_price


@dataclass(frozen=True)
class PricingBreakdown:

    materials: Decimal
    waste: Decimal
    materials_con_merma: Decimal
    labor: Decimal
    gas: Decimal
    base: Decimal
    margin_pct: Decimal
    rounded: Decimal
    audience: str


class AudienceForbiddenError(ValueError):
    pass


def resolve_audience(user_role: UserRole | str, requested: str | None) -> str:
    role_audiences: dict[UserRole, str | None] = {
        UserRole.ADMIN: None,
        UserRole.NEGOCIO: "revendedores",
        UserRole.CUSTOMER: "consumidor_final",
    }

    if user_role not in role_audiences:
        raise AudienceForbiddenError(f"Rol {user_role} sin audiencia asignada")
    default = role_audiences[user_role]
    if default is None:
        return requested if requested else "revendedores"

    if requested and requested != default:
        raise AudienceForbiddenError(
            f"Tu rol no tiene acceso a la lista de {requested}"
        )
    return default


def compute_dual_pricing(
    line_items: Sequence[tuple[Decimal, str, Decimal, str]],
    prep_minutes: int,
    settings: "BusinessSettings",
    user_role: UserRole | str,
    requested_audience: str | None = None,
) -> PricingBreakdown:
    from domain.pricing import calculate_price

    audience = resolve_audience(user_role, requested_audience)

    base_breakdown = calculate_price(
        line_items, prep_minutes, settings.to_pricing()
    )

    if audience == "consumidor_final":
        final_price = derive_audience_price(
            base_breakdown.rounded,
            settings.consumer_markup_pct,
            audience,
        )
        return PricingBreakdown(
            materials=base_breakdown.materials,
            waste=base_breakdown.waste,
            materials_con_merma=base_breakdown.materials_con_merma,
            labor=base_breakdown.labor,
            gas=base_breakdown.gas,
            base=base_breakdown.base,
            margin_pct=base_breakdown.margin_pct,
            rounded=final_price,
            audience=audience,
        )

    return PricingBreakdown(
        materials=base_breakdown.materials,
        waste=base_breakdown.waste,
        materials_con_merma=base_breakdown.materials_con_merma,
        labor=base_breakdown.labor,
        gas=base_breakdown.gas,
        base=base_breakdown.base,
        margin_pct=base_breakdown.margin_pct,
        rounded=base_breakdown.rounded,
        audience=audience,
    )
