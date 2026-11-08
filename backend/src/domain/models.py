import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Tuple
from enum import Enum

from domain.pricing import PricingSettings


class UserRole(str, Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"
    NEGOCIO = "negocio"


class StockStatus(str, Enum):
    OK = "OK"
    LOW = "LOW"
    EMPTY = "EMPTY"


DIFFICULTIES = ("simple", "intermedio", "complejo")
STOCK_UNITS = ("kg", "g", "L", "ml", "unidad")
STOCK_REASONS = ("compra", "merma", "ajuste", "pedido", "anulacion")


@dataclass(frozen=True)
class User:

    email: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: UserRole = UserRole.CUSTOMER
    google_id: Optional[str] = None


@dataclass
class BusinessSettings:

    hourly_rate: Decimal
    margin_pct: Decimal
    round_step: Decimal
    include_labor: bool = True
    include_gas: bool = False
    gas_pct: Decimal = Decimal("0")
    include_waste: bool = False
    waste_pct: Decimal = Decimal("0")
    urgent_surcharge_pct: Decimal = Decimal("0")
    consumer_markup_pct: Decimal = Decimal("40")
    default_prep_minutes: int = 30
    default_servings: int = 6
    default_difficulty: str = "simple"
    business_name: str = ""
    footer_text: str = ""

    def __post_init__(self):
        if not Decimal("0.01") <= self.hourly_rate <= Decimal("100000"):
            raise ValueError(
                f"hourly_rate fuera de rango 0.01-100000: {self.hourly_rate}"
            )
        if not Decimal("0") <= self.margin_pct <= Decimal("100"):
            raise ValueError(f"margin_pct fuera de rango 0-100: {self.margin_pct}")
        if len(self.business_name) > 120:
            raise ValueError("El nombre del negocio debe tener 120 caracteres o menos")
        if len(self.footer_text) > 280:
            raise ValueError("El pie de página debe tener 280 caracteres o menos")
        if not Decimal("0.01") <= self.round_step <= Decimal("1000"):
            raise ValueError(f"round_step fuera de rango 0.01-1000: {self.round_step}")
        if not Decimal("0") <= self.gas_pct <= Decimal("100"):
            raise ValueError(f"gas_pct fuera de rango 0-100: {self.gas_pct}")
        if not Decimal("0") <= self.waste_pct <= Decimal("100"):
            raise ValueError(f"waste_pct fuera de rango 0-100: {self.waste_pct}")
        if not Decimal("0") <= self.urgent_surcharge_pct <= Decimal("100"):
            raise ValueError(
                f"urgent_surcharge_pct fuera de rango 0-100: {self.urgent_surcharge_pct}"
            )
        if not Decimal("0") <= self.consumer_markup_pct <= Decimal("100"):
            raise ValueError(
                f"consumer_markup_pct fuera de rango 0-100: {self.consumer_markup_pct}"
            )
        if not self.include_gas and self.gas_pct != Decimal("0"):
            raise ValueError("gas_pct debe ser 0 si include_gas esta desactivado")
        if not self.include_waste and self.waste_pct != Decimal("0"):
            raise ValueError("waste_pct debe ser 0 si include_waste esta desactivado")
        if not 0 <= self.default_prep_minutes <= 1440:
            raise ValueError(
                f"default_prep_minutes fuera de rango 0-1440: {self.default_prep_minutes}"
            )
        if not 1 <= self.default_servings <= 999:
            raise ValueError(f"default_servings fuera de rango 1-999: {self.default_servings}")
        if self.default_difficulty not in DIFFICULTIES:
            raise ValueError(f"default_difficulty invalido: {self.default_difficulty!r}")

    def to_pricing(self) -> PricingSettings:
        return PricingSettings(
            hourly_rate=self.hourly_rate,
            margin_pct=self.margin_pct,
            round_step=self.round_step,
            include_labor=self.include_labor,
            include_gas=self.include_gas,
            gas_pct=self.gas_pct,
            include_waste=self.include_waste,
            waste_pct=self.waste_pct,
        )


DEFAULT_BUSINESS_SETTINGS = BusinessSettings(
    hourly_rate=Decimal("3000"),
    margin_pct=Decimal("30"),
    round_step=Decimal("100"),
    include_labor=True,
    include_gas=True,
    gas_pct=Decimal("3"),
    include_waste=True,
    waste_pct=Decimal("3"),
    urgent_surcharge_pct=Decimal("20"),
    consumer_markup_pct=Decimal("40"),
)


@dataclass(frozen=True)
class Ingredient:

    name: str
    unit: str
    price_per_unit: Decimal
    stock_qty: Decimal = Decimal("0")
    low_stock_threshold: Decimal = Decimal("0")
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deleted_at: Optional[datetime.datetime] = None

    def __post_init__(self):
        name = self.name.strip()
        if not name:
            raise ValueError("nombre requerido")
        if len(name) > 120:
            raise ValueError("nombre demasiado largo (max 120)")
        if self.unit not in STOCK_UNITS:
            raise ValueError(
                f"unidad invalida: {self.unit!r} (esperado: {'/'.join(STOCK_UNITS)})"
            )
        if self.price_per_unit < 0:
            raise ValueError("price_per_unit no puede ser negativo")
        if self.stock_qty < 0:
            raise ValueError("stock_qty no puede ser negativo")
        if self.low_stock_threshold < 0:
            raise ValueError("low_stock_threshold no puede ser negativo")


@dataclass(frozen=True)
class StockMovement:

    qty_delta: Decimal
    reason: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ingredient_id: Optional[str] = None
    ref: Optional[str] = None
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


@dataclass(frozen=True)
class RecipeItem:

    ingredient_id: str
    qty: Decimal
    unit: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if self.qty <= 0:
            raise ValueError(f"qty de receta debe ser positivo: {self.qty}")
        if self.unit not in STOCK_UNITS:
            raise ValueError(f"unidad de receta invalida: {self.unit!r}")


MAX_RECIPE_LINES = 30


@dataclass(frozen=True)
class Product:

    name: str
    category: str
    recipe: Tuple[RecipeItem, ...]
    description: str = ""
    prep_time_min: int = 0
    servings: int = 1
    difficulty: str = "simple"
    available: bool = False
    image_url: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deleted_at: Optional[datetime.datetime] = None

    def __post_init__(self):
        name = self.name.strip()
        if len(name) < 2:
            raise ValueError("nombre de producto requiere al menos 2 caracteres")
        if len(name) > 120:
            raise ValueError("nombre de producto demasiado largo (max 120)")
        category = self.category.strip()
        if not category:
            raise ValueError("la categoria es obligatoria")
        if len(category) > 60:
            raise ValueError("categoria demasiado larga (max 60)")
        if len(self.description) > 500:
            raise ValueError("descripcion demasiado larga (max 500)")
        if not 0 <= self.prep_time_min <= 1440:
            raise ValueError(f"prep_time_min fuera de rango 0-1440: {self.prep_time_min}")
        if not 1 <= self.servings <= 999:
            raise ValueError(f"servings fuera de rango 1-999: {self.servings}")
        if self.difficulty not in DIFFICULTIES:
            raise ValueError(f"dificultad invalida: {self.difficulty!r}")
        if len(self.recipe) == 0:
            raise ValueError("la receta requiere al menos un insumo")
        if len(self.recipe) > MAX_RECIPE_LINES:
            raise ValueError(f"la receta admite como maximo {MAX_RECIPE_LINES} lineas")
        seen = set()
        for item in self.recipe:
            if item.ingredient_id in seen:
                raise ValueError(f"insumo duplicado en la receta: {item.ingredient_id}")
            seen.add(item.ingredient_id)
