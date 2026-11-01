"""Dashboard de la calculadora de costos (RF-P3CC-05).

Función pura sobre datos crudos ya aportados por los repositories
(counts por status + activos con sus costs calculados por el motor
con el `rounding_mode` de settings, RF-P3CC-05). Estilo
`domain/calc_product.py`: dataclasses frozen, Decimal en todos los
montos, sin I/O y sin float (RNF-P4-03). Paridad de métricas con el
Dashboard legacy: promedios sobre activos, top por precio desc,
bottom por margen asc.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from domain.calc_product import CalcProduct, CalcProductCosts

_ZERO = Decimal("0")
_CENTS = Decimal("0.01")
_LIMIT = 5


def _cents(value: Decimal) -> Decimal:
    """Cuantiza a centavos con ROUND_HALF_UP (RNF-P4-03)."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _average(values: list[Decimal]) -> Decimal:
    """Promedio Decimal cuantizado a centavos; 0 valores -> 0.00
    (paridad legacy `: 0`)."""
    if not values:
        return Decimal("0.00")
    return _cents(sum(values, _ZERO) / Decimal(len(values)))


@dataclass(frozen=True)
class TopByPriceItem:
    """Item de `top_by_price`: {id, name, final_sale_price,
    margin_percent}."""

    id: str
    name: str
    final_sale_price: Decimal
    margin_percent: Decimal


@dataclass(frozen=True)
class BottomByMarginItem:
    """Item de `bottom_by_margin`: {id, name, product_total_cost,
    margin_percent}."""

    id: str
    name: str
    product_total_cost: Decimal
    margin_percent: Decimal


@dataclass(frozen=True)
class DashboardStats:
    """Los 8 campos exactos de `GET /calc/dashboard` (RF-P3CC-05).

    `archived` NO va en la respuesta. Los montos de promedio viajan
    como Decimal (los schemas los serializan a str).
    """

    active_materials: int
    active_products: int
    draft_products: int
    incomplete_materials: int
    avg_product_cost: Decimal
    avg_final_price: Decimal
    top_by_price: list[TopByPriceItem] = field(default_factory=list)
    bottom_by_margin: list[BottomByMarginItem] = field(default_factory=list)


def build_dashboard_stats(
    material_status_counts: dict[str, int],
    product_status_counts: dict[str, int],
    active_products: list[tuple[CalcProduct, CalcProductCosts]],
) -> DashboardStats:
    """Métricas del dashboard (RF-P3CC-05), función pura.

    - counts: tomados del status derivado persistido (B8/B9); claves
      ausentes -> 0.
    - promedios: Decimal sobre los activos, cuantizados a centavos.
    - top_by_price / bottom_by_margin: hasta 5; ties rotos por
      `name` asc (determinista).
    """
    active_finals = [costs.final_sale_price for _, costs in active_products]
    active_totals = [costs.product_total_cost for _, costs in active_products]

    top_by_price = [
        TopByPriceItem(
            id=product.id,
            name=product.name,
            final_sale_price=costs.final_sale_price,
            margin_percent=product.margin_percent,
        )
        for product, costs in sorted(
            active_products,
            key=lambda pair: (-pair[1].final_sale_price, pair[0].name),
        )[:_LIMIT]
    ]
    bottom_by_margin = [
        BottomByMarginItem(
            id=product.id,
            name=product.name,
            product_total_cost=costs.product_total_cost,
            margin_percent=product.margin_percent,
        )
        for product, costs in sorted(
            active_products,
            key=lambda pair: (pair[0].margin_percent, pair[0].name),
        )[:_LIMIT]
    ]

    return DashboardStats(
        active_materials=material_status_counts.get("active", 0),
        active_products=product_status_counts.get("active", 0),
        draft_products=product_status_counts.get("draft", 0),
        incomplete_materials=material_status_counts.get("incomplete", 0),
        avg_product_cost=_average(active_totals),
        avg_final_price=_average(active_finals),
        top_by_price=top_by_price,
        bottom_by_margin=bottom_by_margin,
    )
