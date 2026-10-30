"""Products router (Fase 5, P3/P4) + dual-pricing exports (S3 — T4).

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

Exports de lista de precios por audiencia:
  GET /products/pricelist/csv?audience=revendedores|consumidor_final
  GET /products/pricelist/pdf?audience=revendedores|consumidor_final

Role gate:
  - admin: both audiences
  - negocio: revendedores only (consumidor_final → 403)
  - cliente: consumidor_final only (revendedores → 403)

El precio por audiencia delega en ``derive_audience_price`` /
``_resolve_audience`` de ``domain.pricing_service`` — la regla de negocio
tiene un único hogar.
"""

import csv as csv_module
from decimal import Decimal
from html import escape
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from api.v1.dependencies import get_current_user, require_admin
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.money import decimal_to_cents
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
    BusinessSettings,
    Ingredient,
    Product,
    RecipeItem,
    User,
)
from domain.pricing import CostBreakdown, calculate_price
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
from domain.use_cases import GetSettings

router = APIRouter(prefix="/products", tags=["products"])

_ALL_INGREDIENTS_PAGE_SIZE = 100


async def _load_ingredients(repo: IngredientRepository) -> dict[str, Ingredient]:
    """Todos los insumos activos (app single-tenant: el catalogo es chico)."""
    by_id: dict[str, Ingredient] = {}
    page = 1
    while True:
        items, total = await repo.list(None, None, page, _ALL_INGREDIENTS_PAGE_SIZE)
        for item in items:
            by_id[item.id] = item
        if not items or len(by_id) >= total:
            break
        page += 1
    return by_id


async def _list_all_products(repo: ProductRepository) -> list[Product]:
    """Todos los productos activos paginados (el catalogo es chico)."""
    products: list[Product] = []
    page = 1
    page_size = 100
    while True:
        items, total = await repo.list(None, None, page, page_size)
        products.extend(items)
        if not items or len(products) >= total:
            break
        page += 1
    return products


def _money_or_none(value: Decimal | None) -> int | None:
    return None if value is None else decimal_to_cents(value)


def _breakdown_response(
    breakdown: CostBreakdown | None,
) -> PriceBreakdownResponse | None:
    if breakdown is None:
        return None
    return PriceBreakdownResponse(
        materials=decimal_to_cents(breakdown.materials),
        waste=decimal_to_cents(breakdown.waste),
        materials_con_merma=decimal_to_cents(breakdown.materials_con_merma),
        labor=decimal_to_cents(breakdown.labor),
        gas=decimal_to_cents(breakdown.gas),
        base=decimal_to_cents(breakdown.base),
        margin_pct=breakdown.margin_pct,
        final=decimal_to_cents(breakdown.final),
        rounded=decimal_to_cents(breakdown.rounded),
    )


def _recipe_item_response(
    item: RecipeItem, ingredients_by_id: dict[str, Ingredient]
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
        price_per_unit=(
            decimal_to_cents(ingredient.price_per_unit)
            if ingredient is not None
            else None
        ),
        line_cost=(
            None
            if missing
            else _money_or_none(line_cost_of_item(item, ingredients_by_id))
        ),
        missing=missing,
    )


def _list_item(product: Product, price: ProductPrice) -> ProductListItem:
    breakdown = price.breakdown if price.complete else None
    return ProductListItem(
        id=product.id,
        name=product.name,
        category=product.category,
        price_final=decimal_to_cents(breakdown.rounded) if breakdown else None,
        price_per_serving=(
            decimal_to_cents(price.per_serving) if price.per_serving is not None else None
        ),
        complete=price.complete,
    )


def _detail_response(
    product: Product,
    price: ProductPrice,
    ingredients_by_id: dict[str, Ingredient],
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
        price_per_serving=(
            decimal_to_cents(price.per_serving) if price.per_serving is not None else None
        ),
        recipe=[
            _recipe_item_response(item, ingredients_by_id)
            for item in product.recipe
        ],
    )


def _assemble_product(
    name: str | None,
    category: str | None,
    description: str | None,
    prep_time_min: int | None,
    servings: int | None,
    difficulty: str | None,
    recipe_inputs: list[RecipeItemInput] | None,
    existing: Product | None,
    settings: BusinessSettings,
    ingredients_by_id: dict[str, Ingredient],
) -> tuple[Product | None, str | None]:
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
        recipe_items: list[RecipeItem] = []
        line_items: list[tuple] = []
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
    if stock_qty == 0:
        return "EMPTY"
    if stock_qty <= low_stock_threshold:
        return "LOW"
    return "OK"


@router.get("")
async def list_products(
    q: str | None = Query(default=None, min_length=1, max_length=120),
    category: str | None = Query(default=None, min_length=1, max_length=60),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    audience: Audience | None = Query(
        default=None, description="Audiencia de precios (S3)"
    ),
    repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    current_user: User = Depends(get_current_user),
):
    """Dos contratos (integracion C1+S3 con P3):

    - Sin `audience`: listado P3 (busqueda, categoria, paginacion) con
      PriceBreakdown de cada producto.
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
        items, _ = await ingredient_repo.list(
            q=None, status=None, page=1, page_size=1000
        )
        product_rows = []
        for item in items:
            price = derive_audience_price(
                item.price_per_unit, settings.consumer_markup_pct, resolved
            )
            product_rows.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "unit": item.unit,
                    "price_per_unit": str(price),
                    "status": _stock_status(
                        item.stock_qty, item.low_stock_threshold
                    ),
                }
            )
        return {"audience": resolved, "products": product_rows, "total": len(product_rows)}
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
    if error is not None or product is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error or "Invalid product")
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
    if error is not None or product is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error or "Invalid product")
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


@router.get("/pricelist/csv")
async def pricelist_csv(
    audience: Audience = Query(..., description="Audiencia de precios"),
    current_user: User = Depends(get_current_user),
    product_repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
):
    """Exporta la lista de precios en CSV para la audiencia del rol.

    - admin: ambas audiencias.
    - negocio: solo revendedores.
    - cliente: solo consumidor_final.
    """
    try:
        resolved = _resolve_audience(current_user.role, audience)
    except AudienceForbiddenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    settings = await GetSettings(settings_repo).execute()
    # Contrato S3: la lista de precios sale de los insumos con el
    # markup de audiencia aplicado (el P3 agrega el editor de productos,
    # pero el export de pricelist mantiene su origen original).
    ingredients, _ = await ingredient_repo.list(
        q=None, status=None, page=1, page_size=1000
    )

    rows = []
    for ingredient in ingredients:
        audience_price = derive_audience_price(
            ingredient.price_per_unit, settings.consumer_markup_pct, resolved
        )
        rows.append({
            "name": ingredient.name,
            "unit": ingredient.unit,
            "price": f"${audience_price}",
        })

    if not rows:
        rows = [{"name": "", "unit": "", "price": ""}]

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
    current_user: User = Depends(get_current_user),
    product_repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
):
    """Exporta la lista de precios en PDF para la audiencia del rol.

    - admin: ambas audiencias.
    - negocio: solo revendedores.
    - cliente: solo consumidor_final.

    Renderiza con WeasyPrint (requiere Pango en Windows).
    """
    try:
        resolved = _resolve_audience(current_user.role, audience)
    except AudienceForbiddenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    settings = await GetSettings(settings_repo).execute()
    # Contrato S3: la lista de precios sale de los insumos con el
    # markup de audiencia aplicado (ver pricelist_csv).
    ingredients, _ = await ingredient_repo.list(
        q=None, status=None, page=1, page_size=1000
    )

    audience_label = (
        "Revendedores" if resolved == "revendedores" else "Consumidor final"
    )
    product_rows = []
    for ingredient in ingredients:
        audience_price = derive_audience_price(
            ingredient.price_per_unit, settings.consumer_markup_pct, resolved
        )
        product_rows.append({
            "name": ingredient.name,
            "unit": ingredient.unit,
            "price": f"${audience_price}",
            "audience_label": audience_label,
        })

    if not product_rows:
        product_rows = [{"name": "", "unit": "", "price": "", "audience_label": audience_label}]

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
