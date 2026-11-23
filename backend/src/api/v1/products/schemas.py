from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from api.v1.money import Money, Qty, Pct

ProductDifficulty = Literal["simple", "intermedio", "complejo"]
RecipeUnit = Literal["kg", "g", "L", "ml", "unidad"]
ProductTag = Annotated[
    str, StringConstraints(min_length=1, max_length=30, strip_whitespace=True)
]


class RecipeItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: str = Field(min_length=1, max_length=36)
    qty: Qty = Field(gt=0)
    unit: RecipeUnit


class ProductCreate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=500)
    prep_time_min: Optional[int] = Field(default=None, ge=0, le=1440)
    servings: Optional[int] = Field(default=None, ge=1, le=999)
    difficulty: Optional[ProductDifficulty] = None
    tags: List[ProductTag] = Field(default_factory=list, max_length=10)
    recipe: List[RecipeItemInput] = Field(min_length=1, max_length=30)


class ProductUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    category: Optional[str] = Field(default=None, min_length=1, max_length=60)
    description: Optional[str] = Field(default=None, max_length=500)
    prep_time_min: Optional[int] = Field(default=None, ge=0, le=1440)
    servings: Optional[int] = Field(default=None, ge=1, le=999)
    difficulty: Optional[ProductDifficulty] = None
    tags: Optional[List[ProductTag]] = Field(default=None, max_length=10)
    recipe: Optional[List[RecipeItemInput]] = Field(
        default=None, min_length=1, max_length=30
    )
    available: Optional[bool] = None


class ProductListItem(BaseModel):

    id: str
    name: str
    category: str
    price_final: Optional[Money] = None
    price_per_serving: Optional[Money] = None
    complete: bool
    available: bool
    image_url: Optional[str] = None
    tags: List[str] = []


class ProductListResponse(BaseModel):
    items: List[ProductListItem]
    total: int
    page: int
    page_size: int
    categories: List[str]


class PriceBreakdownResponse(BaseModel):

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
    tags: List[str] = []
    price: Optional[PriceBreakdownResponse] = None
    price_per_serving: Optional[Money] = None
    recipe: List[RecipeItemResponse]


class ProductTagCount(BaseModel):
    name: str
    count: int


class ProductTagsResponse(BaseModel):
    tags: List[ProductTagCount]


class ProductCategoryCount(BaseModel):
    name: str
    count: int


class ProductCategoriesResponse(BaseModel):
    categories: List[ProductCategoryCount]
