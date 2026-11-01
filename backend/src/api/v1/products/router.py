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

Exports de lista de precios por audiencia (S3 — T4):
  GET /products/pricelist/csv?audience=revendedores|consumidor_final
  GET /products/pricelist/pdf?audience=revendedores|consumidor_final

Role gate:
  - admin: ambas audiencias
  - negocio: solo revendedores (consumidor_final -> 403)
  - cliente: solo consumidor_final (revendedores -> 403)

El precio por audiencia delega en ``derive_audience_price`` /
``_resolve_audience`` de ``domain.pricing_service`` — la regla de negocio
tiene un unico hogar.
"""
import csv as csv_module
from decimal import Decimal
from html import escape
from io import StringIO
from typing import Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from api.v1.dependencies import get_current_user, require_admin, require_role
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.pricing.schemas import Audience
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
    Ingredient,
    Product,
    RecipeItem,
    User,
    UserRole,
)
from domain.pricing import CostBreakdown
from domain.pricing_service import (
    AudienceForbiddenError,
    _resolve_audience,
    derive_audience_price,
)
from domain.product_price import ProductPrice, derive_product_price, line_cost_of_item
from domain.repositories import (
    IngredientRepository,
    ProductRepository,
    SettingsRepository,
)
from domain.use_cases import (
    CreateProduct,
    GetSettings,
    ProductValidationError,
    UpdateProduct,
)

router = APIRouter(prefix="/products", tags=["products"])


async def _load_ingredients(
    repo: IngredientRepository, products: Iterable[Product]
) -> Dict[str, Ingredient]:
    """Solo los insumos usados por las recetas de `products` (una consulta)."""
    ids = {item.ingredient_id for product in products for item in product.recipe}
    return {ingredient.id: ingredient for ingredient in await repo.get_many(list(ids))}


def _to_recipe_items(inputs: List[RecipeItemInput]) -> List[RecipeItem]:
    return [
        RecipeItem(ingredient_id=entry.ingredient_id, qty=entry.qty, unit=entry.unit)
        for entry in inputs
    ]


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


def _build_csv(rows: list[dict[str, str]]) -> str:
    """Construye un CSV usando ``csv.writer`` para escapar correctamente
    comas, comillas y saltos de línea en los valores.
    """
    output = StringIO()
    header = list(rows[0].keys())
    writer = csv_module.writer(output, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([row[h] for h in header])
    return output.getvalue()


def _build_pdf_html(product_rows: list[dict[str, str]]) -> str:
    """Construye HTML para renderizar como PDF con WeasyPrint.

    Escapa ``name`` y ``unit`` con ``html.escape`` para prevenir
    inyección de markup. El ``audience_label`` es controlado por
    la aplicación y no necesita escapado.
    """
    rows_html = ""
    for row in product_rows:
        name = escape(row["name"])
        unit = escape(row["unit"])
        rows_html += (
            f"<tr><td>{name}</td>"
            f"<td>{unit}</td>"
            f"<td>{escape(row['price'])}</td></tr>\n"
        )

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: sans-serif; margin: 2em; }}
        h1 {{ color: #333; border-bottom: 2px solid #e8d5b7; padding-bottom: 0.5em; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
        th {{ background: #f5ebe0; padding: 0.5em; text-align: left; border-bottom: 2px solid #ddd; }}
        td {{ padding: 0.5em; border-bottom: 1px solid #eee; }}
        .audience {{ color: #666; font-style: italic; }}
    </style>
</head>
<body>
    <h1>Lista de Precios</h1>
    <p class="audience">Audiencia: {product_rows[0].get('audience_label', 'revendedores')}</p>
    <table>
        <thead>
            <tr><th>Producto</th><th>Unidad</th><th>Precio</th></tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</body>
</html>"""


def _stock_status(stock_qty: Decimal, low_stock_threshold: Decimal) -> str:
    """Deriva el status de stock desde los campos del ingrediente.

    - ``EMPTY``: stock_qty == 0
    - ``LOW``: 0 < stock_qty <= low_stock_threshold
    - ``OK``: stock_qty > low_stock_threshold
    """
    if stock_qty == 0:
        return "EMPTY"
    if stock_qty <= low_stock_threshold:
        return "LOW"
    return "OK"


@router.get("")
async def list_products(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    category: Optional[str] = Query(default=None, min_length=1, max_length=60),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    audience: Optional[Audience] = Query(
        default=None, description="Audiencia de precios (S3)"
    ),
    repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    current_user: User = Depends(get_current_user),
):
    """Dos contratos (integracion P3 + S3):

    - Sin `audience`: listado P3 (busqueda insensible a acentos RF-P3-01,
      filtro por categoria y categorias derivadas) con PriceBreakdown de
      cada producto.
    - Con `audience`: catalogo S3 para el portal — insumos con precio
      derivado para la audiencia del rol. Guard: admin ambas audiencias,
      negocio solo revendedores, cliente solo consumidor_final (403 si no).
    """
    if audience is not None:
        try:
            resolved = _resolve_audience(current_user.role, audience)
        except AudienceForbiddenError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e
        settings = await GetSettings(settings_repo).execute()
        ingredients, _ = await ingredient_repo.list(
            q=None, status=None, page=1, page_size=1000
        )
        product_rows = []
        for ingredient in ingredients:
            price = derive_audience_price(
                ingredient.price_per_unit, settings.consumer_markup_pct, resolved
            )
            product_rows.append(
                {
                    "id": ingredient.id,
                    "name": ingredient.name,
                    "unit": ingredient.unit,
                    "price_per_unit": str(price),
                    "status": _stock_status(
                        ingredient.stock_qty, ingredient.low_stock_threshold
                    ),
                }
            )
        return {
            "audience": resolved,
            "products": product_rows,
            "total": len(product_rows),
        }
    settings = await GetSettings(settings_repo).execute()
    items, total = await repo.list(q, category, page, page_size)
    categories = await repo.distinct_categories()
    ingredients_by_id = await _load_ingredients(ingredient_repo, items)
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
    ingredients_by_id = await _load_ingredients(ingredient_repo, [product])
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
    try:
        product = await CreateProduct(repo, ingredient_repo, settings_repo).execute(
            name=payload.name,
            category=payload.category,
            description=payload.description,
            prep_time_min=payload.prep_time_min,
            servings=payload.servings,
            difficulty=payload.difficulty,
            recipe=_to_recipe_items(payload.recipe),
        )
    except ProductValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    settings = await GetSettings(settings_repo).execute()
    ingredients_by_id = await _load_ingredients(ingredient_repo, [product])
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
    provided = payload.model_dump(exclude_unset=True)
    try:
        saved = await UpdateProduct(repo, ingredient_repo, settings_repo).execute(
            product_id,
            name=provided.get("name"),
            category=provided.get("category"),
            description=provided.get("description"),
            prep_time_min=provided.get("prep_time_min"),
            servings=provided.get("servings"),
            difficulty=provided.get("difficulty"),
            recipe=(
                _to_recipe_items(payload.recipe) if "recipe" in provided else None
            ),
        )
    except ProductValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado"
        )
    settings = await GetSettings(settings_repo).execute()
    ingredients_by_id = await _load_ingredients(ingredient_repo, [saved])
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


@router.get("/pricelist/csv")
async def pricelist_csv(
    audience: Audience = Query(..., description="Audiencia de precios"),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.NEGOCIO, UserRole.CUSTOMER)
    ),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
):
    """Exporta la lista de precios en CSV para la audiencia del rol.

    - admin: ambas audiencias.
    - negocio: solo revendedores.
    - cliente: solo consumidor_final.
    """
    # Resolve audience via domain service (S3 — T4)
    try:
        resolved = _resolve_audience(current_user.role, audience)
    except AudienceForbiddenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    settings = await GetSettings(settings_repo).execute()

    # Get all products (ingredients)
    products, _ = await ingredient_repo.list(q=None, status=None, page=1, page_size=1000)

    # Build CSV rows using domain price computation
    rows = []
    for product in products:
        price = derive_audience_price(
            product.price_per_unit,
            settings.consumer_markup_pct,
            resolved,
        )
        rows.append({
            "name": product.name,
            "unit": product.unit,
            "price": f"${price}",
        })

    csv_content = _build_csv(rows)
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="pricelist_{resolved}.csv"'
        },
    )


@router.get("/pricelist/pdf")
async def pricelist_pdf(
    audience: Audience = Query(..., description="Audiencia de precios"),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.NEGOCIO, UserRole.CUSTOMER)
    ),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
):
    """Exporta la lista de precios en PDF para la audiencia del rol.

    - admin: ambas audiencias.
    - negocio: solo revendedores.
    - cliente: solo consumidor_final.

    Renderiza con WeasyPrint (requiere Pango en Windows).
    """
    # Resolve audience via domain service (S3 — T4)
    try:
        resolved = _resolve_audience(current_user.role, audience)
    except AudienceForbiddenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    settings = await GetSettings(settings_repo).execute()

    # Get all products (ingredients)
    products, _ = await ingredient_repo.list(q=None, status=None, page=1, page_size=1000)

    # Build PDF rows using domain price computation
    audience_label = "Revendedores" if resolved == "revendedores" else "Consumidor final"
    product_rows = []
    for product in products:
        price = derive_audience_price(
            product.price_per_unit,
            settings.consumer_markup_pct,
            resolved,
        )
        product_rows.append({
            "name": product.name,
            "unit": product.unit,
            "price": f"${price}",
            "audience_label": audience_label,
        })

    html_content = _build_pdf_html(product_rows)
    # Lazy import: WeasyPrint requires Pango/GObject on Windows.
    # If unavailable, the error surfaces here with the exact OS message.
    try:
        from weasyprint import HTML
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"WeasyPrint no puede renderizar: {e}",
        ) from e

    pdf_bytes = HTML(string=html_content).render().write_pdf()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="pricelist_{resolved}.pdf"'
        },
    )
