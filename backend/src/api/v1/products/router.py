"""Router de productos (Fase 5, P3/P4).

Contrato:
- Lectura (list/get): cualquier usuario autenticado. Mutaciones: admin.
- El precio es derivado en cada lectura con los insumos y settings
  actuales (RF-P3-04): nunca se persiste.
- Producto incompleto (insumos sin precio/borrados): 200 con
  complete=false, price null y missing_ingredients (no es error).
- Validaciones de receta (insumo inexistente, unidades incompatibles,
  duplicados) → 400, como POST /pricing/preview.
- Borrado: UC-07 / RF-P4-08. Soft delete SIEMPRE: el producto sale del
  catálogo pero los pedidos históricos quedan intactos. Con pedidos, la
  response informa `impacted_orders` (200); sin pedidos, 204. A diferencia
  de los insumos en recetas activas, no se bloquea con 409.
"""
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from api.v1.dependencies import get_current_user, require_admin
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.products.dependencies import get_product_repository
from api.v1.products.schemas import (
    PriceBreakdownResponse,
    ProductCreate,
    ProductDetailResponse,
    ProductListItem,
    ProductListResponse,
    ProductUpdate,
    RecipeItemInput,
    RecipeItemResponse,
)
from api.v1.settings.dependencies import get_settings_repository
from domain.models import (
    BusinessSettings,
    Ingredient,
    Product,
    RecipeItem,
    User,
)
from domain.pricing import CostBreakdown, calculate_price
from domain.product_price import ProductPrice, derive_product_price, line_cost_of_item
from domain.repositories import (
    IngredientRepository,
    ProductRepository,
    SettingsRepository,
)
from domain.use_cases import GetSettings

router = APIRouter(prefix="/products", tags=["products"])

_ALL_INGREDIENTS_PAGE_SIZE = 100


async def _load_ingredients(repo: IngredientRepository) -> Dict[str, Ingredient]:
    """Todos los insumos activos (app single-tenant: el catalogo es chico)."""
    by_id: Dict[str, Ingredient] = {}
    page = 1
    while True:
        items, total = await repo.list(None, None, page, _ALL_INGREDIENTS_PAGE_SIZE)
        for item in items:
            by_id[item.id] = item
        if not items or len(by_id) >= total:
            break
        page += 1
    return by_id


def _breakdown_response(
    breakdown: Optional[CostBreakdown],
) -> Optional[PriceBreakdownResponse]:
    if breakdown is None:
        return None
    return PriceBreakdownResponse(
        materials=breakdown.materials,
        waste=breakdown.waste,
        materials_con_merma=breakdown.materials_con_merma,
        labor=breakdown.labor,
        gas=breakdown.gas,
        base=breakdown.base,
        margin_pct=breakdown.margin_pct,
        final=breakdown.final,
        rounded=breakdown.rounded,
    )


def _recipe_item_response(
    item: RecipeItem, ingredients_by_id: Dict[str, Ingredient]
) -> RecipeItemResponse:
    ingredient = ingredients_by_id.get(item.ingredient_id)
    missing = (
        ingredient is None
        or ingredient.deleted_at is not None
        or ingredient.price_per_unit == 0
    )
    return RecipeItemResponse(
        ingredient_id=item.ingredient_id,
        ingredient_name=(
            ingredient.name if ingredient is not None else "Insumo desconocido"
        ),
        qty=item.qty,
        unit=item.unit,
        purchase_unit=ingredient.unit if ingredient is not None else None,
        price_per_unit=ingredient.price_per_unit if ingredient is not None else None,
        line_cost=None if missing else line_cost_of_item(item, ingredients_by_id),
        missing=missing,
    )


def _list_item(product: Product, price: ProductPrice) -> ProductListItem:
    return ProductListItem(
        id=product.id,
        name=product.name,
        category=product.category,
        price_final=price.breakdown.rounded if price.complete else None,
        price_per_serving=price.per_serving,
        complete=price.complete,
    )


def _detail_response(
    product: Product,
    price: ProductPrice,
    ingredients_by_id: Dict[str, Ingredient],
) -> ProductDetailResponse:
    return ProductDetailResponse(
        id=product.id,
        name=product.name,
        category=product.category,
        description=product.description,
        prep_time_min=product.prep_time_min,
        servings=product.servings,
        difficulty=product.difficulty,
        complete=price.complete,
        missing_ingredients=list(price.missing),
        price=_breakdown_response(price.breakdown if price.complete else None),
        price_per_serving=price.per_serving,
        recipe=[
            _recipe_item_response(item, ingredients_by_id)
            for item in product.recipe
        ],
    )


def _assemble_product(
    name: Optional[str],
    category: Optional[str],
    description: Optional[str],
    prep_time_min: Optional[int],
    servings: Optional[int],
    difficulty: Optional[str],
    recipe_inputs: Optional[List[RecipeItemInput]],
    existing: Optional[Product],
    settings: BusinessSettings,
    ingredients_by_id: Dict[str, Ingredient],
) -> Tuple[Optional[Product], Optional[str]]:
    """Arma el Product de dominio y valida la receta contra los insumos
    corrientes. En create, los campos omitidos vienen de los default de
    settings (RF-P4-01). Devuelve (product, error)."""
    if existing is None:
        name = name or ""
        category = category or ""
        description = description or ""
        prep_time_min = (
            settings.default_prep_minutes if prep_time_min is None else prep_time_min
        )
        servings = settings.default_servings if servings is None else servings
        difficulty = settings.default_difficulty if difficulty is None else difficulty
    else:
        name = name if name is not None else existing.name
        category = category if category is not None else existing.category
        description = description if description is not None else existing.description
        prep_time_min = (
            prep_time_min if prep_time_min is not None else existing.prep_time_min
        )
        servings = servings if servings is not None else existing.servings
        difficulty = (
            difficulty if difficulty is not None else existing.difficulty
        )

    if recipe_inputs is not None:
        recipe_items: List[RecipeItem] = []
        line_items: List[tuple] = []
        for entry in recipe_inputs:
            ingredient = ingredients_by_id.get(entry.ingredient_id)
            if ingredient is None:
                return None, f"Insumo desconocido en la receta: {entry.ingredient_id}"
            recipe_items.append(
                RecipeItem(
                    ingredient_id=entry.ingredient_id,
                    qty=entry.qty,
                    unit=entry.unit,
                )
            )
            line_items.append(
                (entry.qty, entry.unit, ingredient.price_per_unit, ingredient.unit)
            )
    else:
        # Receta sin cambios: se conserva. Lineas cuyo insumo fue borrado
        # no bloquean el guardado (el producto queda "incompleto" en
        # lectura; el detalle lo muestra).
        recipe_items = list(existing.recipe) if existing is not None else []
        line_items = [
            (
                item.qty,
                item.unit,
                ingredients_by_id[item.ingredient_id].price_per_unit,
                ingredients_by_id[item.ingredient_id].unit,
            )
            for item in recipe_items
            if item.ingredient_id in ingredients_by_id
        ]

    try:
        product = Product(
            name=name,
            category=category,
            recipe=tuple(recipe_items),
            description=description,
            prep_time_min=prep_time_min,
            servings=servings,
            difficulty=difficulty,
            **({"id": existing.id, "deleted_at": existing.deleted_at} if existing else {}),
        )
    except ValueError as e:
        return None, str(e)
    # Validacion de unidades con el mismo codigo que /pricing/preview
    # (UnitConversionError hereda de ValueError).
    try:
        calculate_price(line_items, product.prep_time_min, settings.to_pricing())
    except ValueError as e:
        return None, str(e)
    return product, None


@router.get("", response_model=ProductListResponse)
async def list_products(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    category: Optional[str] = Query(default=None, min_length=1, max_length=60),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    current_user: User = Depends(get_current_user),
):
    """Listado P3: busqueda insensible a acentos (RF-P3-01), filtro por
    categoria y categorias derivadas de los productos activos."""
    settings = await GetSettings(settings_repo).execute()
    items, total = await repo.list(q, category, page, page_size)
    categories = await repo.distinct_categories()
    ingredients_by_id = await _load_ingredients(ingredient_repo)
    return ProductListResponse(
        items=[
            _list_item(item, derive_product_price(item, ingredients_by_id, settings))
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        categories=categories,
    )


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product(
    product_id: str,
    repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    current_user: User = Depends(get_current_user),
):
    """Detalle P4: informacion + receta con costo por linea + desglose
    completo del motor (o missing_ingredients si es incompleto)."""
    product = await repo.get(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado"
        )
    settings = await GetSettings(settings_repo).execute()
    ingredients_by_id = await _load_ingredients(ingredient_repo)
    return _detail_response(
        product, derive_product_price(product, ingredients_by_id, settings),
        ingredients_by_id,
    )


@router.post(
    "", response_model=ProductDetailResponse, status_code=status.HTTP_201_CREATED
)
async def create_product(
    payload: ProductCreate,
    repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    settings = await GetSettings(settings_repo).execute()
    ingredients_by_id = await _load_ingredients(ingredient_repo)
    product, error = _assemble_product(
        name=payload.name,
        category=payload.category,
        description=payload.description,
        prep_time_min=payload.prep_time_min,
        servings=payload.servings,
        difficulty=payload.difficulty,
        recipe_inputs=payload.recipe,
        existing=None,
        settings=settings,
        ingredients_by_id=ingredients_by_id,
    )
    if error is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    await repo.create(product)
    return _detail_response(
        product, derive_product_price(product, ingredients_by_id, settings),
        ingredients_by_id,
    )


@router.patch("/{product_id}", response_model=ProductDetailResponse)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    """Parcial; `recipe` reemplaza la receta completa cuando se envia."""
    existing = await repo.get(product_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado"
        )
    provided = payload.model_dump(exclude_unset=True)
    settings = await GetSettings(settings_repo).execute()
    ingredients_by_id = await _load_ingredients(ingredient_repo)
    product, error = _assemble_product(
        name=provided.get("name"),
        category=provided.get("category"),
        description=provided.get("description"),
        prep_time_min=provided.get("prep_time_min"),
        servings=provided.get("servings"),
        difficulty=provided.get("difficulty"),
        recipe_inputs=payload.recipe if "recipe" in provided else None,
        existing=existing,
        settings=settings,
        ingredients_by_id=ingredients_by_id,
    )
    if error is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    saved = await repo.update(product)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado"
        )
    return _detail_response(
        saved, derive_product_price(saved, ingredients_by_id, settings),
        ingredients_by_id,
    )


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: str,
    repo: ProductRepository = Depends(get_product_repository),
    _admin: User = Depends(require_admin),
):
    """UC-07 / RF-P4-08: soft delete SIEMPRE (el producto sale del catálogo,
    los pedidos históricos no se tocan). Si tiene pedidos históricos, la
    response es 200 con `impacted_orders`; si no, 204. El bloqueo con 409
    NO aplica a productos (a diferencia de insumos en recetas activas)."""
    existing = await repo.get(product_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado"
        )
    impacted = await repo.count_orders(product_id)
    await repo.soft_delete(product_id)
    if impacted > 0:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"impacted_orders": impacted},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
