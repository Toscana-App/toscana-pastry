import asyncio
import csv as csv_module
import logging
from dataclasses import replace as replace_domain
from decimal import Decimal
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse

from api.v1.dependencies import (
    get_current_user,
    require_admin,
    require_admin_or_audience,
    require_role,
)
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.money import money_str
from api.v1.pdf.dependencies import get_pdf_client
from api.v1.pricing.schemas import Audience
from data.accent import accent_fold, validate_search_term
from data.pdf.client import PdfClient
from api.v1.products.dependencies import (
    get_media_root,
    get_product_repository,
)
from api.v1.products.image_service import (
    ImageValidationError,
    validate_image,
)
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
    derive_audience_price,
    resolve_audience,
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
    ProductPublishBlockedError,
    ProductValidationError,
    UpdateProduct,
)

router = APIRouter(prefix="/products", tags=["products"])
logger = logging.getLogger(__name__)

_LIST_PAGE_SIZE = 500
_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 500
_FORMULA_PREFIXES = ("=", "+", "-", "@", "	")


def _csv_safe(value: str) -> str:
    if value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


async def _list_all_products(product_repo: ProductRepository) -> list:
    products: list = []
    page = 1
    while True:
        batch, total = await product_repo.list(
            q=None, category=None, page=page, page_size=_LIST_PAGE_SIZE
        )
        products.extend(batch)
        if not batch or len(products) >= total:
            return products
        page += 1


def _resolve_or_403(user: User, audience: str) -> str:
    try:
        return resolve_audience(user.role, audience)
    except AudienceForbiddenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


async def _build_store_rows(
    product_repo: ProductRepository,
    ingredient_repo: IngredientRepository,
    settings_repo: SettingsRepository,
    resolved: str,
    q: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> tuple[list[tuple], int, list[str]]:
    settings = await GetSettings(settings_repo).execute()
    products = await _list_all_products(product_repo)
    ingredients_by_id = await _load_ingredients(ingredient_repo, products)
    priced: list[tuple] = []
    for product in products:
        price = derive_product_price(product, ingredients_by_id, settings)
        if not product.available or not price.complete or price.breakdown is None:
            continue
        priced.append(
            (
                product,
                derive_audience_price(
                    price.breakdown.rounded,
                    settings.consumer_markup_pct,
                    resolved,
                ),
                price,
            )
        )
    if q is not None:
        folded = accent_fold(validate_search_term(q))
        priced = [
            (product, audience_price, price)
            for product, audience_price, price in priced
            if folded in accent_fold(product.name)
        ]
    total = len(priced)
    categories = sorted({product.category for product, _, _ in priced})
    if page is not None or page_size is not None:
        size = page_size or _DEFAULT_PAGE_SIZE
        start = ((page or 1) - 1) * size
        priced = priced[start : start + size]
    return priced, total, categories


async def _load_ingredients(
    repo: IngredientRepository, products: Iterable[Product]
) -> Dict[str, Ingredient]:
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
        available=product.available,
        image_url=product.image_url,
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
        available=product.available,
        image_url=product.image_url,
        price=_breakdown_response(price.breakdown if price.complete else None),
        price_per_serving=price.per_serving,
        recipe=[
            _recipe_item_response(item, ingredients_by_id)
            for item in product.recipe
        ],
    )


def _build_csv(rows: list[dict[str, str]]) -> str:
    output = StringIO()
    header = list(rows[0].keys()) if rows else ["name", "category", "price"]
    writer = csv_module.writer(output, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_csv_safe(row[h]) for h in header])
    return output.getvalue()


@router.get("")
async def list_products(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    category: Optional[str] = Query(default=None, min_length=1, max_length=60),
    page: Optional[int] = Query(default=None, ge=1, description="Pagina (opcional)"),
    page_size: Optional[int] = Query(
        default=None, ge=1, le=_MAX_PAGE_SIZE, description="Tamano de pagina (opcional)"
    ),
    audience: Optional[Audience] = Query(
        default=None, description="Audiencia de precios (S3)"
    ),
    repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    current_user: User = Depends(require_admin_or_audience),
):
    if audience is not None:
        resolved = _resolve_or_403(current_user, audience)
        priced, total, categories = await _build_store_rows(
            repo, ingredient_repo, settings_repo, resolved, q=q,
            page=page, page_size=page_size,
        )
        return {
            "audience": resolved,
            "products": [
                {
                    "id": product.id,
                    "name": product.name,
                    "category": product.category,
                    "description": product.description,
                    "image_url": product.image_url,
                    "price": money_str(audience_price),
                    "price_per_serving": money_str(price.per_serving),
                    "complete": True,
                }
                for product, audience_price, price in priced
            ],
            "total": total,
            "categories": categories,
        }
    page = page or 1
    page_size = page_size or 20
    if page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size must be <= 100",
        )
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


@router.get("/{product_id}")
async def get_product(
    product_id: str,
    audience: Optional[Audience] = Query(
        default=None, description="Audiencia de precios (S3)"
    ),
    repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    current_user: User = Depends(require_admin_or_audience),
):
    product = await repo.get(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado"
        )
    settings = await GetSettings(settings_repo).execute()
    ingredients_by_id = await _load_ingredients(ingredient_repo, [product])
    price = derive_product_price(product, ingredients_by_id, settings)
    if audience is not None:
        resolved = _resolve_or_403(current_user, audience)
        if not product.available or not price.complete or price.breakdown is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado"
            )
        return {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "description": product.description,
            "image_url": product.image_url,
            "price": money_str(
                derive_audience_price(
                    price.breakdown.rounded, settings.consumer_markup_pct, resolved
                )
            ),
            "servings": product.servings,
            "prep_time_min": product.prep_time_min,
        }
    return _detail_response(product, price, ingredients_by_id)


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
            available=provided.get("available"),
        )
    except ProductValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ProductPublishBlockedError as e:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(e), "missing_ingredients": e.missing},
        )
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


def _stored_image_path(media_root: Path, image_url: str) -> Path:
    name = PurePosixPath(image_url).name
    return media_root / "products" / name


@router.post(
    "/{product_id}/image", status_code=status.HTTP_201_CREATED
)
async def upload_product_image(
    product_id: str,
    file: UploadFile = File(...),
    repo: ProductRepository = Depends(get_product_repository),
    media_root: Path = Depends(get_media_root),
    _admin: User = Depends(require_admin),
):
    product = await repo.get(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado"
        )
    data = await file.read()
    try:
        image_type = validate_image(data)
    except ImageValidationError as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"code": e.code, "detail": e.detail},
        )
    products_dir = media_root / "products"
    products_dir.mkdir(parents=True, exist_ok=True)
    if product.image_url is not None:
        _stored_image_path(media_root, product.image_url).unlink(missing_ok=True)
    target = products_dir / f"{product_id}.{image_type}"
    target.write_bytes(data)
    saved = replace_domain(
        product, image_url=f"/media/products/{product_id}.{image_type}"
    )
    await repo.update(saved)
    return {"image_url": saved.image_url}


@router.delete("/{product_id}/image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_image(
    product_id: str,
    repo: ProductRepository = Depends(get_product_repository),
    media_root: Path = Depends(get_media_root),
    _admin: User = Depends(require_admin),
):
    product = await repo.get(product_id)
    if product is None or product.image_url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El producto no tiene imagen",
        )
    _stored_image_path(media_root, product.image_url).unlink(missing_ok=True)
    await repo.update(replace_domain(product, image_url=None))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/pricelist/csv")
async def pricelist_csv(
    audience: Audience = Query(..., description="Audiencia de precios"),
    current_user: User = Depends(
        require_role(UserRole.ADMIN, UserRole.NEGOCIO, UserRole.CUSTOMER)
    ),
    repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
):
    resolved = _resolve_or_403(current_user, audience)
    priced, _, _ = await _build_store_rows(
        repo, ingredient_repo, settings_repo, resolved
    )

    rows = [
        {
            "name": product.name,
            "category": product.category,
            "price": f"${audience_price}",
        }
        for product, audience_price, _ in priced
    ]

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
    repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    pdf: PdfClient = Depends(get_pdf_client),
):
    resolved = _resolve_or_403(current_user, audience)
    priced, _, _ = await _build_store_rows(
        repo, ingredient_repo, settings_repo, resolved
    )

    audience_label = "Revendedores" if resolved == "revendedores" else "Consumidor final"
    rows = [
        {
            "name": product.name,
            "unit": product.category,
            "price": f"${audience_price}",
        }
        for product, audience_price, _ in priced
    ]
    pdf_bytes = await asyncio.to_thread(pdf.render_pricelist, rows, audience_label)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="pricelist_{resolved}.pdf"'
        },
    )
