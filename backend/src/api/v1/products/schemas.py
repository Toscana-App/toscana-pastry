"""Schemas Pydantic de la API de productos (Fase 5, P3/P4).

Reglas del contrato (mismas que ingredientes):
- Money viaja en centavos (long, int); Qty viaja como str en responses y
  number en requests (money.py: coercion explicita, nunca float).
- El precio NUNCA se persiste: las responses llevan la derivacion con los
  insumos y settings actuales (RF-P3-04). `complete=false` = la receta
  tiene insumos sin precio (0, borrado o inexistente) → price null y
  missing_ingredients poblado.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from api.v1.money import Money, Qty, Pct

ProductDifficulty = Literal["simple", "intermedio", "complejo"]
RecipeUnit = Literal["kg", "g", "L", "ml", "unidad"]


class RecipeItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: str = Field(min_length=1, max_length=36)
    qty: Qty = Field(gt=0)
    unit: RecipeUnit


class ProductCreate(BaseModel):
    """POST /products. prep_time_min / servings / difficulty omitidos se
    rellenan con los default de settings (RF-P4-01)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=500)
    prep_time_min: Optional[int] = Field(default=None, ge=0, le=1440)
    servings: Optional[int] = Field(default=None, ge=1, le=999)
    difficulty: Optional[ProductDifficulty] = None
    recipe: List[RecipeItemInput] = Field(min_length=1, max_length=30)


class ProductUpdate(BaseModel):
    """PATCH /products/{id}: parcial (extra=forbid). `recipe` reemplaza la
    receta completa cuando se envía."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    category: Optional[str] = Field(default=None, min_length=1, max_length=60)
    description: Optional[str] = Field(default=None, max_length=500)
    prep_time_min: Optional[int] = Field(default=None, ge=0, le=1440)
    servings: Optional[int] = Field(default=None, ge=1, le=999)
    difficulty: Optional[ProductDifficulty] = None
    recipe: Optional[List[RecipeItemInput]] = Field(
        default=None, min_length=1, max_length=30
    )
    available: Optional[bool] = None


class ProductListItem(BaseModel):
    """Item del listado P3. price_final es el precio comercial (redondeado
    al paso por el motor); null cuando el producto es incompleto."""

    id: str
    name: str
    category: str
    price_final: Optional[Money] = None
    price_per_serving: Optional[Money] = None
    complete: bool
    available: bool
    image_url: Optional[str] = None


class ProductListResponse(BaseModel):
    items: List[ProductListItem]
    total: int
    page: int
    page_size: int
    # Categorías derivadas de los productos activos (chips del P3).
    categories: List[str]


class PriceBreakdownResponse(BaseModel):
    """Desglose completo del motor de precios (tab Costos del P4)."""

    materials: Money
    waste: Money
    materials_con_merma: Money
    labor: Money
    gas: Money
    base: Money
    margin_pct: Pct
    final: Money
    rounded: Money


class RecipeItemResponse(BaseModel):
    """Linea de receta con datos del insumo (tab Ingredientes del P4).
    Con missing=true: el insumo no existe, está borrado o no tiene
    precio → line_cost null, purchase_unit/price_per_unit pueden ser null."""

    ingredient_id: str
    ingredient_name: str
    qty: Qty
    unit: str
    purchase_unit: Optional[str] = None
    price_per_unit: Optional[Money] = None
    line_cost: Optional[Money] = None
    missing: bool = False


class ProductDetailResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str
    prep_time_min: int
    servings: int
    difficulty: str
    complete: bool
    missing_ingredients: List[str]
    available: bool
    image_url: Optional[str] = None
    price: Optional[PriceBreakdownResponse] = None
    price_per_serving: Optional[Money] = None
    recipe: List[RecipeItemResponse]
