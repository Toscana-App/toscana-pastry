"""Servicio de precios duales por audiencia.

Puro: Decimal adentro, Decimal afuera. Sin frameworks, sin I/O.
Deriva consumidor_final a partir del precio base (revendedores) aplicando
el markup configurable de tenant settings.
"""
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
    """Deriva el precio para la audiencia dada a partir del precio base.

    - ``revendedores``: devuelve ``base_price`` sin modificaciones.
    - ``consumidor_final``: ``base_price × (1 + markup/100)``,
      cuantizado a ``0.01`` con ``ROUND_HALF_UP``.

    Esta es la única fuente de verdad para la fórmula de markup.
    ``compute_dual_pricing`` y el router de pricelist delegan aquí.
    """
    if audience == "consumidor_final":
        markup = consumer_markup_pct / Decimal("100")
        return (base_price * (Decimal("1") + markup)).quantize(
            _CENT, rounding=ROUND_HALF_UP
        )
    return base_price


@dataclass(frozen=True)
class PricingBreakdown:
    """Desglose de precios por audiencia."""

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
    """El rol del usuario no tiene acceso a la audiencia solicitada."""


def resolve_audience(user_role: UserRole | str, requested: str | None) -> str:
    """Resuelve la audiencia según el rol del usuario.

    - admin: usa requested si se especifica; por defecto ``revendedores``.
    - negocio: siempre ``revendedores``.
    - cliente: siempre ``consumidor_final``.

    Raises:
        AudienceForbiddenError: si el rol no tiene acceso a la audiencia
        solicitada.
    """
    role_audiences: dict[UserRole, str | None] = {
        UserRole.ADMIN: None,
        UserRole.NEGOCIO: "revendedores",
        UserRole.CUSTOMER: "consumidor_final",
    }

    if user_role not in role_audiences:
        raise AudienceForbiddenError(f"Rol {user_role} sin audiencia asignada")
    default = role_audiences[user_role]
    if default is None:
        # admin: usa requested o default
        return requested if requested else "revendedores"

    # No-admin: la audiencia es fija
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
    """Calcula el breakdown de precios para la audiencia del rol.

    El precio base (revendedores) es el que devuelve ``calculate_price``.
    El precio consumidor_final es ``base × (1 + markup/100)``, derivado en
    cada lectura, nunca persistido.
    """
    from domain.pricing import calculate_price

    audience = resolve_audience(user_role, requested_audience)

    # Precio base (revendedores)
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
