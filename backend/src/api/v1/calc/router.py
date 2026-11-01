"""Router para los endpoints de la calculadora de costos (FASE CC).

Todos los endpoints son admin-only (RF-P5CC-08).
Namespace: /api/v1/calc.
"""
import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from api.v1.dependencies import get_current_user, require_admin
from api.v1.money import cents_to_decimal
from domain.models import User
from api.v1.calc.dependencies import (
    get_calc_settings_repository,
    get_calc_material_category_repository,
    get_calc_product_category_repository,
    get_calc_supplier_repository,
    get_calc_default_cost_repository,
    get_calc_material_repository,
    get_calc_product_repository,
)
from api.v1.calc.schemas import (
    CalcSettingsRequest,
    CalcSettingsResponse,
    CategoryCreate,
    CategoryUpdate,
    CategoryListResponse,
    CategoryResponse,
    SupplierCreate,
    SupplierUpdate,
    SupplierListResponse,
    SupplierResponse,
    DefaultCostCreate,
    DefaultCostUpdate,
    DefaultCostListResponse,
    DefaultCostResponse,
    MaterialCreate,
    MaterialUpdate,
    MaterialListResponse,
    MaterialResponse,
    CostHistoryResponse,
    CostHistoryListResponse,
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
    ProductCostsResponse,
    ProductLinesOut,
    ProductLineMaterialOut,
    ProductLineLaborOut,
    ProductLineExtraCostOut,
    ProductWithLinesResponse,
    ProductVersionResponse,
    ProductVersionListResponse,
)
from data.repositories.calc.sql_calc_settings_repository import SQLCalcSettingsRepository
from data.repositories.calc.sql_calc_material_category_repository import (
    SQLCalcMaterialCategoryRepository,
)
from data.repositories.calc.sql_calc_product_category_repository import (
    SQLCalcProductCategoryRepository,
)
from data.repositories.calc.sql_calc_supplier_repository import SQLCalcSupplierRepository
from data.repositories.calc.sql_calc_default_cost_repository import SQLCalcDefaultCostRepository
from data.repositories.calc.sql_calc_material_repository import SQLCalcMaterialRepository
from data.repositories.calc.sql_calc_product_repository import SQLCalcProductRepository
from domain.calc_settings import (
    CalcSettings,
    CalcMaterialCategory,
    CalcProductCategory,
    CalcSupplier,
    CalcDefaultCost,
    DEFAULT_MARGIN_PERCENT,
    DEFAULT_DISCOUNT_PERCENT,
    DEFAULT_TAX_PERCENT,
    DEFAULT_ROUNDING_MODE,
)
from domain.calc_product import (
    CalcProduct,
    CalcProductCosts,
    CalcProductMaterialLine,
    CalcProductLaborLine,
    CalcProductExtraCostLine,
    calc_material_line_cost,
    calc_labor_line_cost,
    calc_extra_line_cost,
    compute_costs,
    recalculate_product as recalculate_product_domain,
    resolve_material_line,
)
from domain.calc_material import CalcMaterial

router = APIRouter(prefix="/calc", tags=["calc"])


# ─── Helpers ────────────────────────────────────────────────────────────

def _category_response(cat) -> CategoryResponse:
    return CategoryResponse(
        id=cat.id,
        name=cat.name,
        description=cat.description,
        created_at=cat.created_at,
        updated_at=cat.updated_at,
    )


def _supplier_response(sup: CalcSupplier) -> SupplierResponse:
    return SupplierResponse(
        id=sup.id,
        name=sup.name,
        contact_name=sup.contact_name,
        phone=sup.phone,
        email=sup.email,
        notes=sup.notes,
        created_at=sup.created_at,
        updated_at=sup.updated_at,
    )


def _default_cost_response(cost: CalcDefaultCost) -> DefaultCostResponse:
    return DefaultCostResponse(
        id=cost.id,
        name=cost.name,
        type=cost.type,
        default_unit_cost_or_rate=cost.default_unit_cost_or_rate,
        default_quantity_or_minutes=cost.default_quantity_or_minutes,
        status=cost.status,
        created_at=cost.created_at,
        updated_at=cost.updated_at,
    )


def _material_response(material: CalcMaterial) -> MaterialResponse:
    return MaterialResponse(
        id=material.id,
        name=material.name,
        internal_code=material.internal_code,
        category_id=material.category_id,
        supplier_id=material.supplier_id,
        unit_of_measure=material.unit_of_measure,
        purchase_total_price=material.purchase_total_price,
        package_quantity=material.package_quantity,
        unit_cost=material.unit_cost,
        notes=material.notes,
        status=material.status,
        created_at=material.created_at,
        updated_at=material.updated_at,
    )


# ─── Settings (singleton: GET/PUT) ──────────────────────────────────────

PAGINATION_MAX = 100


@router.get("/settings", response_model=CalcSettingsResponse)
async def get_calc_settings(
    repo: SQLCalcSettingsRepository = Depends(get_calc_settings_repository),
    current_user: User = Depends(get_current_user),
):
    """GET /calc/settings: devuelve la fila persistida o defaults (RF-P5CC-02)."""
    settings = await repo.get()
    # repo.get() nunca devuelve None: si no hay fila, retorna DEFAULT_CALC_SETTINGS.
    assert settings is not None
    return CalcSettingsResponse(
        business_name=settings.business_name,
        main_currency_name=settings.main_currency_name,
        main_currency_symbol=settings.main_currency_symbol,
        default_margin_percent=settings.default_margin_percent,
        default_discount_percent=settings.default_discount_percent,
        default_tax_percent=settings.default_tax_percent,
        rounding_mode=settings.rounding_mode,
    )


@router.put("/settings", response_model=CalcSettingsResponse)
async def update_calc_settings(
    payload: CalcSettingsRequest,
    repo: SQLCalcSettingsRepository = Depends(get_calc_settings_repository),
    _admin: User = Depends(require_admin),
):
    """PUT /calc/settings: reemplazo completo atomico (RF-P5CC-02)."""
    try:
        settings = CalcSettings(
            business_name=payload.business_name,
            main_currency_name=payload.main_currency_name,
            main_currency_symbol=payload.main_currency_symbol,
            default_margin_percent=payload.default_margin_percent,
            default_discount_percent=payload.default_discount_percent,
            default_tax_percent=payload.default_tax_percent,
            rounding_mode=payload.rounding_mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    saved = await repo.save(settings)
    return CalcSettingsResponse(
        business_name=saved.business_name,
        main_currency_name=saved.main_currency_name,
        main_currency_symbol=saved.main_currency_symbol,
        default_margin_percent=saved.default_margin_percent,
        default_discount_percent=saved.default_discount_percent,
        default_tax_percent=saved.default_tax_percent,
        rounding_mode=saved.rounding_mode,
    )


# ─── Material Categories ────────────────────────────────────────────────

@router.get(
    "/material-categories",
    response_model=CategoryListResponse,
)
async def list_material_categories(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=PAGINATION_MAX),
    repo: SQLCalcMaterialCategoryRepository = Depends(get_calc_material_category_repository),
    current_user: User = Depends(get_current_user),
):
    """GET /calc/material-categories: lista con busqueda + paginacion (RF-P5CC-07)."""
    items, total = await repo.list(q, page, page_size)
    return CategoryListResponse(
        items=[_category_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/material-categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_material_category(
    payload: CategoryCreate,
    repo: SQLCalcMaterialCategoryRepository = Depends(get_calc_material_category_repository),
    _admin: User = Depends(require_admin),
):
    """POST /calc/material-categories: crea categoria (RF-P5CC-03)."""
    # Check duplicate name (case-insensitive)
    existing = await repo.get_by_name(payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una categoria con ese nombre: {payload.name}",
        )
    try:
        category = CalcMaterialCategory(name=payload.name, description=payload.description)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    saved = await repo.create(category)
    return _category_response(saved)


@router.patch(
    "/material-categories/{category_id}",
    response_model=CategoryResponse,
)
async def update_material_category(
    category_id: str,
    payload: CategoryUpdate,
    repo: SQLCalcMaterialCategoryRepository = Depends(get_calc_material_category_repository),
    _admin: User = Depends(require_admin),
):
    """PATCH /calc/material-categories/{id}: edita (RF-P5CC-03)."""
    existing = await repo.get(category_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria no encontrada",
        )
    # Check empty body (422)
    updates = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="al menos un campo para actualizar",
        )
    try:
        updated = CalcMaterialCategory(
            id=existing.id,
            name=updates.get("name", existing.name),
            description=updates.get("description", existing.description),
            created_at=existing.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    saved = await repo.update(updated)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria no encontrada",
        )
    return _category_response(saved)


@router.delete(
    "/material-categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_material_category(
    category_id: str,
    repo: SQLCalcMaterialCategoryRepository = Depends(get_calc_material_category_repository),
    _admin: User = Depends(require_admin),
):
    """DELETE /calc/material-categories/{id}: elimina (RF-P5CC-03)."""
    existing = await repo.get(category_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria no encontrada",
        )
    # Check if in use (stub: returns 0 for now, B8 wires it)
    in_use = await repo.count_in_use(category_id)
    if in_use > 0:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"in_use_by": in_use},
        )
    deleted = await repo.delete(category_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria no encontrada",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Product Categories ─────────────────────────────────────────────────

@router.get(
    "/product-categories",
    response_model=CategoryListResponse,
)
async def list_product_categories(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=PAGINATION_MAX),
    repo: SQLCalcProductCategoryRepository = Depends(get_calc_product_category_repository),
    current_user: User = Depends(get_current_user),
):
    """GET /calc/product-categories: lista con busqueda + paginacion (RF-P5CC-07)."""
    items, total = await repo.list(q, page, page_size)
    return CategoryListResponse(
        items=[_category_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/product-categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_category(
    payload: CategoryCreate,
    repo: SQLCalcProductCategoryRepository = Depends(get_calc_product_category_repository),
    _admin: User = Depends(require_admin),
):
    """POST /calc/product-categories: crea categoria (RF-P5CC-04)."""
    existing = await repo.get_by_name(payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una categoria con ese nombre: {payload.name}",
        )
    try:
        category = CalcProductCategory(name=payload.name, description=payload.description)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    saved = await repo.create(category)
    return _category_response(saved)


@router.patch(
    "/product-categories/{category_id}",
    response_model=CategoryResponse,
)
async def update_product_category(
    category_id: str,
    payload: CategoryUpdate,
    repo: SQLCalcProductCategoryRepository = Depends(get_calc_product_category_repository),
    _admin: User = Depends(require_admin),
):
    """PATCH /calc/product-categories/{id}: edita (RF-P5CC-04)."""
    existing = await repo.get(category_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria no encontrada",
        )
    updates = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="al menos un campo para actualizar",
        )
    try:
        updated = CalcProductCategory(
            id=existing.id,
            name=updates.get("name", existing.name),
            description=updates.get("description", existing.description),
            created_at=existing.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    saved = await repo.update(updated)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria no encontrada",
        )
    return _category_response(saved)


@router.delete(
    "/product-categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product_category(
    category_id: str,
    repo: SQLCalcProductCategoryRepository = Depends(get_calc_product_category_repository),
    _admin: User = Depends(require_admin),
):
    """DELETE /calc/product-categories/{id}: elimina (RF-P5CC-04)."""
    existing = await repo.get(category_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria no encontrada",
        )
    in_use = await repo.count_in_use(category_id)
    if in_use > 0:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"in_use_by": in_use},
        )
    deleted = await repo.delete(category_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria no encontrada",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Suppliers ──────────────────────────────────────────────────────────

@router.get(
    "/suppliers",
    response_model=SupplierListResponse,
)
async def list_suppliers(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=PAGINATION_MAX),
    repo: SQLCalcSupplierRepository = Depends(get_calc_supplier_repository),
    current_user: User = Depends(get_current_user),
):
    """GET /calc/suppliers: lista con busqueda + paginacion (RF-P5CC-07)."""
    items, total = await repo.list(q, page, page_size)
    return SupplierListResponse(
        items=[_supplier_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_supplier(
    payload: SupplierCreate,
    repo: SQLCalcSupplierRepository = Depends(get_calc_supplier_repository),
    _admin: User = Depends(require_admin),
):
    """POST /calc/suppliers: crea proveedor (RF-P5CC-05)."""
    try:
        supplier = CalcSupplier(
            name=payload.name,
            contact_name=payload.contact_name,
            phone=payload.phone,
            email=payload.email,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    saved = await repo.create(supplier)
    return _supplier_response(saved)


@router.patch(
    "/suppliers/{supplier_id}",
    response_model=SupplierResponse,
)
async def update_supplier(
    supplier_id: str,
    payload: SupplierUpdate,
    repo: SQLCalcSupplierRepository = Depends(get_calc_supplier_repository),
    _admin: User = Depends(require_admin),
):
    """PATCH /calc/suppliers/{id}: edita (RF-P5CC-05)."""
    existing = await repo.get(supplier_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado",
        )
    updates = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="al menos un campo para actualizar",
        )
    try:
        updated = CalcSupplier(
            id=existing.id,
            name=updates.get("name", existing.name),
            contact_name=updates.get("contact_name", existing.contact_name),
            phone=updates.get("phone", existing.phone),
            email=updates.get("email", existing.email),
            notes=updates.get("notes", existing.notes),
            created_at=existing.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    saved = await repo.update(updated)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado",
        )
    return _supplier_response(saved)


@router.delete(
    "/suppliers/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_supplier(
    supplier_id: str,
    repo: SQLCalcSupplierRepository = Depends(get_calc_supplier_repository),
    _admin: User = Depends(require_admin),
):
    """DELETE /calc/suppliers/{id}: elimina (RF-P5CC-05)."""
    existing = await repo.get(supplier_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado",
        )
    in_use = await repo.count_in_use(supplier_id)
    if in_use > 0:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"in_use_by": in_use},
        )
    deleted = await repo.delete(supplier_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Default Costs ──────────────────────────────────────────────────────

@router.get(
    "/default-costs",
    response_model=DefaultCostListResponse,
)
async def list_default_costs(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    type_filter: Optional[str] = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=PAGINATION_MAX),
    repo: SQLCalcDefaultCostRepository = Depends(get_calc_default_cost_repository),
    current_user: User = Depends(get_current_user),
):
    """GET /calc/default-costs: lista con busqueda + filtro type + paginacion (RF-P5CC-07)."""
    items, total = await repo.list(q, type_filter, page, page_size)
    return DefaultCostListResponse(
        items=[_default_cost_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/default-costs",
    response_model=DefaultCostResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_default_cost(
    payload: DefaultCostCreate,
    repo: SQLCalcDefaultCostRepository = Depends(get_calc_default_cost_repository),
    _admin: User = Depends(require_admin),
):
    """POST /calc/default-costs: crea costo por defecto (RF-P5CC-06)."""
    try:
        cost = CalcDefaultCost(
            name=payload.name,
            type=payload.type,
            default_unit_cost_or_rate=cents_to_decimal(
                payload.default_unit_cost_or_rate
            ),
            default_quantity_or_minutes=payload.default_quantity_or_minutes,
            status=payload.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    saved = await repo.create(cost)
    return _default_cost_response(saved)


@router.patch(
    "/default-costs/{cost_id}",
    response_model=DefaultCostResponse,
)
async def update_default_cost(
    cost_id: str,
    payload: DefaultCostUpdate,
    repo: SQLCalcDefaultCostRepository = Depends(get_calc_default_cost_repository),
    _admin: User = Depends(require_admin),
):
    """PATCH /calc/default-costs/{id}: edita (RF-P5CC-06)."""
    existing = await repo.get(cost_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Costo por defecto no encontrado",
        )
    updates = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="al menos un campo para actualizar",
        )
    try:
        updated = CalcDefaultCost(
            id=existing.id,
            name=updates.get("name", existing.name),
            type=updates.get("type", existing.type),
            default_unit_cost_or_rate=(
                cents_to_decimal(updates["default_unit_cost_or_rate"])
                if "default_unit_cost_or_rate" in updates
                else existing.default_unit_cost_or_rate
            ),
            default_quantity_or_minutes=updates.get(
                "default_quantity_or_minutes", existing.default_quantity_or_minutes
            ),
            status=updates.get("status", existing.status),
            created_at=existing.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    saved = await repo.update(updated)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Costo por defecto no encontrado",
        )
    return _default_cost_response(saved)


@router.delete(
    "/default-costs/{cost_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_default_cost(
    cost_id: str,
    repo: SQLCalcDefaultCostRepository = Depends(get_calc_default_cost_repository),
    _admin: User = Depends(require_admin),
):
    """DELETE /calc/default-costs/{id}: elimina (RF-P5CC-06)."""
    existing = await repo.get(cost_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Costo por defecto no encontrado",
        )
    deleted = await repo.delete(cost_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Costo por defecto no encontrado",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Materials (RF-P2CC-01..05) ─────────────────────────────────────────

@router.post(
    "/materials",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_material(
    payload: MaterialCreate,
    repo: SQLCalcMaterialRepository = Depends(get_calc_material_repository),
    category_repo: SQLCalcMaterialCategoryRepository = Depends(
        get_calc_material_category_repository
    ),
    supplier_repo: SQLCalcSupplierRepository = Depends(get_calc_supplier_repository),
    _admin: User = Depends(require_admin),
):
    """POST /calc/materials: crea material (RF-P2CC-01).

    unit_cost y status son derivados del servidor (RF-P2CC-02/03);
    FK invalida -> 404; rangos -> 422.
    """
    if payload.category_id is not None:
        category = await category_repo.get(payload.category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria no encontrada",
            )
    if payload.supplier_id is not None:
        supplier = await supplier_repo.get(payload.supplier_id)
        if supplier is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proveedor no encontrado",
            )
    try:
        material = CalcMaterial(
            name=payload.name,
            internal_code=payload.internal_code,
            category_id=payload.category_id,
            supplier_id=payload.supplier_id,
            unit_of_measure=payload.unit_of_measure,
            purchase_total_price=(
                cents_to_decimal(payload.purchase_total_price)
                if payload.purchase_total_price is not None
                else None
            ),
            package_quantity=payload.package_quantity,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    saved = await repo.create(material)
    return _material_response(saved)


@router.get(
    "/materials",
    response_model=MaterialListResponse,
)
async def list_materials(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    category_id: Optional[str] = Query(default=None),
    supplier_id: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=PAGINATION_MAX),
    repo: SQLCalcMaterialRepository = Depends(get_calc_material_repository),
    current_user: User = Depends(get_current_user),
):
    """GET /calc/materials: lista con busqueda (nombre y codigo), filtros
    por categoria/proveedor/status y paginacion (RF-P2CC-05)."""
    items, total = await repo.list(q, category_id, supplier_id, status_filter, page, page_size)
    return MaterialListResponse(
        items=[_material_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/materials/{material_id}",
    response_model=MaterialResponse,
)
async def get_material(
    material_id: str,
    repo: SQLCalcMaterialRepository = Depends(get_calc_material_repository),
    current_user: User = Depends(get_current_user),
):
    """GET /calc/materials/{id}: detalle (RF-P2CC-01)."""
    material = await repo.get(material_id)
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material no encontrado",
        )
    return _material_response(material)


@router.patch(
    "/materials/{material_id}",
    response_model=MaterialResponse,
)
async def update_material(
    material_id: str,
    payload: MaterialUpdate,
    repo: SQLCalcMaterialRepository = Depends(get_calc_material_repository),
    category_repo: SQLCalcMaterialCategoryRepository = Depends(
        get_calc_material_category_repository
    ),
    supplier_repo: SQLCalcSupplierRepository = Depends(get_calc_supplier_repository),
    _admin: User = Depends(require_admin),
):
    """PATCH /calc/materials/{id}: edita (RF-P2CC-01).

    A diferencia de B4-B7, un null explicito EN un campo de precio o
    cantidad lo elimina (unit_cost -> None, status -> incomplete, y se
    registra en el historial si cambio, RF-P2CC-04).
    """
    existing = await repo.get(material_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material no encontrado",
        )
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="al menos un campo para actualizar",
        )
    if updates.get("category_id") is not None:
        category = await category_repo.get(updates["category_id"])
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria no encontrada",
            )
    if updates.get("supplier_id") is not None:
        supplier = await supplier_repo.get(updates["supplier_id"])
        if supplier is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proveedor no encontrado",
            )
    try:
        updated = CalcMaterial(
            id=existing.id,
            name=updates.get("name", existing.name),
            internal_code=updates.get("internal_code", existing.internal_code),
            category_id=updates.get("category_id", existing.category_id),
            supplier_id=updates.get("supplier_id", existing.supplier_id),
            unit_of_measure=updates.get("unit_of_measure", existing.unit_of_measure),
            purchase_total_price=(
                (
                    cents_to_decimal(updates["purchase_total_price"])
                    if updates["purchase_total_price"] is not None
                    else None
                )
                if "purchase_total_price" in updates
                else existing.purchase_total_price
            ),
            package_quantity=updates.get("package_quantity", existing.package_quantity),
            notes=updates.get("notes", existing.notes),
            created_at=existing.created_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    saved = await repo.update(updated)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material no encontrado",
        )
    return _material_response(saved)


@router.delete(
    "/materials/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_material(
    material_id: str,
    repo: SQLCalcMaterialRepository = Depends(get_calc_material_repository),
    _admin: User = Depends(require_admin),
):
    """DELETE /calc/materials/{id}: elimina (S4).

    Usado en lineas de productos -> 409 + {impacted_products: N}.
    Con historial de costos -> 409 + {detail: "has_cost_history"}.
    """
    existing = await repo.get(material_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material no encontrado",
        )
    in_use = await repo.count_in_use(material_id)
    if in_use > 0:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"impacted_products": in_use},
        )
    # El historial de costos es append-only: no se borra ni se deja huerfano.
    if await repo.count_cost_history(material_id) > 0:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "has_cost_history"},
        )
    deleted = await repo.delete(material_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material no encontrado",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/materials/{material_id}/cost-history",
    response_model=CostHistoryListResponse,
)
async def list_material_cost_history(
    material_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=PAGINATION_MAX),
    repo: SQLCalcMaterialRepository = Depends(get_calc_material_repository),
    current_user: User = Depends(get_current_user),
):
    """GET /calc/materials/{id}/cost-history: historial paginado,
    mas recientes primero (RF-P2CC-04)."""
    material = await repo.get(material_id)
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material no encontrado",
        )
    items, total = await repo.list_cost_history(material_id, page, page_size)
    return CostHistoryListResponse(
        items=[
            CostHistoryResponse(
                previous_unit_cost=item.previous_unit_cost,
                new_unit_cost=item.new_unit_cost,
                changed_at=item.changed_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ─── Products (RF-P4CC-01..08) ─────────────────────────────────────────

def _product_response(p: CalcProduct) -> ProductResponse:
    return ProductResponse(
        id=p.id,
        name=p.name,
        sku=p.sku,
        category_id=p.category_id,
        description=p.description,
        notes=p.notes,
        margin_percent=p.margin_percent,
        discount_percent=p.discount_percent,
        tax_percent=p.tax_percent,
        status=p.status,
        last_recalculated_at=p.last_recalculated_at,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _costs_response(costs: CalcProductCosts) -> ProductCostsResponse:
    return ProductCostsResponse(
        product_total_cost=costs.product_total_cost,
        profit_amount=costs.profit_amount,
        discount_amount=costs.discount_amount,
        adjusted_profit_amount=costs.adjusted_profit_amount,
        tax_amount=costs.tax_amount,
        final_sale_price=costs.final_sale_price,
    )


def _product_lines_out(
    material_lines, labor_lines, extra_lines
) -> ProductLinesOut:
    return ProductLinesOut(
        materials=[
            ProductLineMaterialOut(
                material_id=line.material_id,
                material_name=line.material_name,
                quantity_used=line.quantity_used,
                unit_of_measure_snapshot=line.unit_of_measure_snapshot,
                unit_cost_snapshot=line.unit_cost_snapshot,
                line_total_cost=line.line_total_cost,
                sort_order=line.sort_order,
            )
            for line in material_lines
        ],
        labor=[
            ProductLineLaborOut(
                activity_name=line.activity_name,
                hourly_rate=line.hourly_rate,
                minutes_required=line.minutes_required,
                line_total_cost=line.line_total_cost,
                sort_order=line.sort_order,
            )
            for line in labor_lines
        ],
        extra_costs=[
            ProductLineExtraCostOut(
                concept_name=line.concept_name,
                unit_cost=line.unit_cost,
                quantity=line.quantity,
                line_total_cost=line.line_total_cost,
                sort_order=line.sort_order,
            )
            for line in extra_lines
        ],
    )


def _settings_defaults(
    settings: CalcSettings | None,
) -> tuple[Decimal, Decimal, Decimal, str]:
    """Defaults de percents + rounding_mode (RF-P5CC-01): sin fila de
    settings -> 30/0/19 y `none` del dominio."""
    if settings is None:
        return (
            DEFAULT_MARGIN_PERCENT,
            DEFAULT_DISCOUNT_PERCENT,
            DEFAULT_TAX_PERCENT,
            DEFAULT_ROUNDING_MODE,
        )
    return (
        settings.default_margin_percent,
        settings.default_discount_percent,
        settings.default_tax_percent,
        settings.rounding_mode,
    )


# Campos de ProductUpdate que admiten `None` en el schema pero no pueden
# quedar nulos en el producto: `null` explicito -> 422 (no 500).
_PRODUCT_NON_NULLABLE_FIELDS = frozenset(
    {"name", "margin_percent", "discount_percent", "tax_percent", "status"}
)


async def _build_material_lines(
    payload_lines, repo: SQLCalcProductRepository
) -> list[CalcProductMaterialLine]:
    """Resuelve los snapshots SIEMPRE por el servidor (RF-P4CC-02,
    security #8): material inexistente -> 404; material incomplete
    (unit_cost None) -> snapshot en 0.00 sin error (D4)."""
    lines: list[CalcProductMaterialLine] = []
    for index, line in enumerate(payload_lines):
        material = await repo.get_material(line.material_id)
        if material is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Material no encontrado",
            )
        lines.append(
            resolve_material_line(material, line.quantity_used, index)
        )
    return lines


def _build_labor_lines(payload_lines) -> list[CalcProductLaborLine]:
    lines: list[CalcProductLaborLine] = []
    for index, line in enumerate(payload_lines):
        hourly_rate = cents_to_decimal(line.hourly_rate)
        lines.append(
            CalcProductLaborLine(
                activity_name=line.activity_name,
                hourly_rate=hourly_rate,
                minutes_required=line.minutes_required,
                line_total_cost=calc_labor_line_cost(
                    hourly_rate, line.minutes_required
                ),
                sort_order=index,
            )
        )
    return lines


def _build_extra_lines(payload_lines) -> list[CalcProductExtraCostLine]:
    lines: list[CalcProductExtraCostLine] = []
    for index, line in enumerate(payload_lines):
        unit_cost = cents_to_decimal(line.unit_cost)
        lines.append(
            CalcProductExtraCostLine(
                concept_name=line.concept_name,
                unit_cost=unit_cost,
                quantity=line.quantity,
                line_total_cost=calc_extra_line_cost(
                    unit_cost, line.quantity
                ),
                sort_order=index,
            )
        )
    return lines


async def _raise_sku_conflict(
    repo: SQLCalcProductRepository,
    sku: str | None,
    exclude_product_id: str | None = None,
) -> None:
    """SKU unica entre productos no eliminados, case/acento-insensitive
    (regla 7). Duplicada -> 409 + {detail: 'SKU ya en uso'}."""
    if sku is None:
        return
    if await repo.find_sku_owner(sku, exclude_product_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="SKU ya en uso"
        )


@router.post(
    "/products",
    response_model=ProductWithLinesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    payload: ProductCreate,
    repo: SQLCalcProductRepository = Depends(get_calc_product_repository),
    product_category_repo: SQLCalcProductCategoryRepository = Depends(
        get_calc_product_category_repository
    ),
    settings_repo: SQLCalcSettingsRepository = Depends(
        get_calc_settings_repository
    ),
    _admin: User = Depends(require_admin),
):
    """POST /calc/products: crea producto con lineas (RF-P4CC-01..05).

    Snapshots, line_total_cost y costs son SIEMPRE derivados del
    servidor (security #8); percents omitidos -> defaults de
    CalcSettings; material/categoria inexistente -> 404; SKU
    duplicada -> 409; rangos -> 422.
    """
    if payload.category_id is not None:
        category = await product_category_repo.get(payload.category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria no encontrada",
            )
    await _raise_sku_conflict(repo, payload.sku)
    settings = await settings_repo.get()
    default_margin, default_discount, default_tax, rounding_mode = (
        _settings_defaults(settings)
    )
    try:
        material_lines = await _build_material_lines(payload.materials, repo)
        labor_lines = _build_labor_lines(payload.labor)
        extra_lines = _build_extra_lines(payload.extra_costs)
        product = CalcProduct(
            name=payload.name,
            sku=payload.sku,
            category_id=payload.category_id,
            description=payload.description,
            notes=payload.notes,
            margin_percent=(
                payload.margin_percent
                if payload.margin_percent is not None
                else default_margin
            ),
            discount_percent=(
                payload.discount_percent
                if payload.discount_percent is not None
                else default_discount
            ),
            tax_percent=(
                payload.tax_percent
                if payload.tax_percent is not None
                else default_tax
            ),
            status=payload.status,
        )
        costs = compute_costs(
            material_lines,
            labor_lines,
            extra_lines,
            product.margin_percent,
            product.discount_percent,
            product.tax_percent,
            rounding_mode,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    saved = await repo.create(product, material_lines, labor_lines, extra_lines)
    return ProductWithLinesResponse(
        product=_product_response(saved),
        product_lines=_product_lines_out(material_lines, labor_lines, extra_lines),
        costs=_costs_response(costs),
    )


@router.get(
    "/products",
    response_model=ProductListResponse,
)
async def list_products(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    category_id: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=PAGINATION_MAX),
    repo: SQLCalcProductRepository = Depends(get_calc_product_repository),
    current_user: User = Depends(get_current_user),
):
    """GET /calc/products: lista con busqueda por nombre Y SKU (D5),
    filtros, paginacion y orden fijo por nombre. Solo no-eliminados."""
    items, total = await repo.list(q, category_id, status_filter, page, page_size)
    return ProductListResponse(
        items=[_product_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/products/{product_id}")
async def get_product(
    product_id: str,
    include_versions: bool = Query(default=False),
    repo: SQLCalcProductRepository = Depends(get_calc_product_repository),
    settings_repo: SQLCalcSettingsRepository = Depends(
        get_calc_settings_repository
    ),
    current_user: User = Depends(get_current_user),
):
    """GET /calc/products/{id}: detalle con lineas + costs
    (RF-P4CC-05/06). `versions` solo presente con include_versions=true
    (listado completo, version_number desc)."""
    product = await repo.get(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )
    settings = await settings_repo.get()
    _, _, _, rounding_mode = _settings_defaults(settings)
    material_lines, labor_lines, extra_lines = await repo.get_lines(product_id)
    try:
        costs = compute_costs(
            material_lines,
            labor_lines,
            extra_lines,
            product.margin_percent,
            product.discount_percent,
            product.tax_percent,
            rounding_mode,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    body: dict = {
        "product": _product_response(product).model_dump(mode="json"),
        "materials": [
            ProductLineMaterialOut(
                material_id=line.material_id,
                material_name=line.material_name,
                quantity_used=line.quantity_used,
                unit_of_measure_snapshot=line.unit_of_measure_snapshot,
                unit_cost_snapshot=line.unit_cost_snapshot,
                line_total_cost=line.line_total_cost,
                sort_order=line.sort_order,
            ).model_dump(mode="json")
            for line in material_lines
        ],
        "labor": [
            ProductLineLaborOut(
                activity_name=line.activity_name,
                hourly_rate=line.hourly_rate,
                minutes_required=line.minutes_required,
                line_total_cost=line.line_total_cost,
                sort_order=line.sort_order,
            ).model_dump(mode="json")
            for line in labor_lines
        ],
        "extra_costs": [
            ProductLineExtraCostOut(
                concept_name=line.concept_name,
                unit_cost=line.unit_cost,
                quantity=line.quantity,
                line_total_cost=line.line_total_cost,
                sort_order=line.sort_order,
            ).model_dump(mode="json")
            for line in extra_lines
        ],
        "costs": _costs_response(costs).model_dump(mode="json"),
    }
    if include_versions:
        versions, _ = await repo.list_versions(product_id, 1, 10_000)
        body["versions"] = [
            ProductVersionResponse(
                version_number=v.version_number,
                product_total_cost=v.product_total_cost,
                profit_amount=v.profit_amount,
                discount_amount=v.discount_amount,
                adjusted_profit_amount=v.adjusted_profit_amount,
                tax_amount=v.tax_amount,
                final_sale_price=v.final_sale_price,
                changed_at=v.changed_at,
            ).model_dump(mode="json")
            for v in versions
        ]
    return body


@router.patch(
    "/products/{product_id}",
    response_model=ProductWithLinesResponse,
)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    repo: SQLCalcProductRepository = Depends(get_calc_product_repository),
    product_category_repo: SQLCalcProductCategoryRepository = Depends(
        get_calc_product_category_repository
    ),
    settings_repo: SQLCalcSettingsRepository = Depends(
        get_calc_settings_repository
    ),
    _admin: User = Depends(require_admin),
):
    """PATCH /calc/products/{id}: edita (RF-P4CC-01/02).

    Semantica de lineas (regla 4): clave ausente -> no cambia;
    clave [] -> vacia el set; lista -> reemplazo completo. Sin
    campos -> 422.
    """
    existing = await repo.get(product_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="al menos un campo para actualizar",
        )
    null_fields = sorted(
        k for k in _PRODUCT_NON_NULLABLE_FIELDS if k in updates and updates[k] is None
    )
    if null_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"campos no anulables: {null_fields}",
        )
    if updates.get("category_id") is not None:
        category = await product_category_repo.get(updates["category_id"])
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria no encontrada",
            )
    if "sku" in updates:
        await _raise_sku_conflict(
            repo, updates["sku"], exclude_product_id=product_id
        )
    settings = await settings_repo.get()
    _, _, _, rounding_mode = _settings_defaults(settings)
    material_lines = None
    labor_lines = None
    extra_lines = None
    try:
        # Lineas desde los campos tipados del payload (no del dump a
        # dict): los builders esperan objetos Pydantic con attributes.
        if payload.materials is not None:
            material_lines = await _build_material_lines(payload.materials, repo)
        if payload.labor is not None:
            labor_lines = _build_labor_lines(payload.labor)
        if payload.extra_costs is not None:
            extra_lines = _build_extra_lines(payload.extra_costs)
        updated = CalcProduct(
            id=existing.id,
            name=updates.get("name", existing.name),
            sku=updates.get("sku", existing.sku),
            category_id=updates.get("category_id", existing.category_id),
            description=updates.get("description", existing.description),
            notes=updates.get("notes", existing.notes),
            margin_percent=updates.get("margin_percent", existing.margin_percent),
            discount_percent=updates.get(
                "discount_percent", existing.discount_percent
            ),
            tax_percent=updates.get("tax_percent", existing.tax_percent),
            status=updates.get("status", existing.status),
            last_recalculated_at=existing.last_recalculated_at,
            created_at=existing.created_at,
            updated_at=datetime.datetime.now(datetime.UTC),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    saved = await repo.update(updated, material_lines, labor_lines, extra_lines)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )
    kept_material, kept_labor, kept_extra = await repo.get_lines(product_id)
    costs = compute_costs(
        kept_material,
        kept_labor,
        kept_extra,
        saved.margin_percent,
        saved.discount_percent,
        saved.tax_percent,
        rounding_mode,
    )
    return ProductWithLinesResponse(
        product=_product_response(saved),
        product_lines=_product_lines_out(kept_material, kept_labor, kept_extra),
        costs=_costs_response(costs),
    )


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product(
    product_id: str,
    repo: SQLCalcProductRepository = Depends(get_calc_product_repository),
    _admin: User = Depends(require_admin),
):
    """DELETE /calc/products/{id}: soft delete (regla 8); nunca borra
    la fila ni las versiones."""
    deleted = await repo.soft_delete(product_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/products/{product_id}/recalculate",
    response_model=ProductWithLinesResponse,
)
async def recalculate_product(
    product_id: str,
    repo: SQLCalcProductRepository = Depends(get_calc_product_repository),
    settings_repo: SQLCalcSettingsRepository = Depends(
        get_calc_settings_repository
    ),
    _admin: User = Depends(require_admin),
):
    """POST /calc/products/{id}/recalculate: re-resolve snapshots y
    recalcula lineas (regla 6); crea version solo si el final
    redondeado cambio (regla 5, RF-P4CC-07)."""
    product = await repo.get(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )
    settings = await settings_repo.get()
    _, _, _, rounding_mode = _settings_defaults(settings)
    material_lines, labor_lines, extra_lines = await repo.get_lines(product_id)
    materials_by_id = await repo.get_materials(
        [line.material_id for line in material_lines]
    )
    try:
        result = recalculate_product_domain(
            product,
            material_lines,
            labor_lines,
            extra_lines,
            materials_by_id,
            rounding_mode,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    saved = await repo.save_lines(
        product_id,
        result.material_lines,
        result.labor_lines,
        result.extra_lines,
        last_recalculated_at=datetime.datetime.now(datetime.UTC),
    )
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )
    try:
        if result.creates_version:
            await repo.add_version(product_id, result.new_costs)
        await repo.commit()
    except IntegrityError as e:
        # Recalculo concurrente: otro request ya tomo ese version_number
        # (uq_calc_product_versions_product_version).
        await repo.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="version_conflict"
        ) from e
    return ProductWithLinesResponse(
        product=_product_response(saved),
        product_lines=_product_lines_out(
            result.material_lines, result.labor_lines, result.extra_lines
        ),
        costs=_costs_response(result.new_costs),
    )


@router.get(
    "/products/{product_id}/versions",
    response_model=ProductVersionListResponse,
)
async def list_product_versions(
    product_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=PAGINATION_MAX),
    repo: SQLCalcProductRepository = Depends(get_calc_product_repository),
    current_user: User = Depends(get_current_user),
):
    """GET /calc/products/{id}/versions: versiones paginadas, mas
    recientes primero (RF-P4CC-07). 404 si el producto no existe."""
    product = await repo.get(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )
    items, total = await repo.list_versions(product_id, page, page_size)
    return ProductVersionListResponse(
        items=[
            ProductVersionResponse(
                version_number=item.version_number,
                product_total_cost=item.product_total_cost,
                profit_amount=item.profit_amount,
                discount_amount=item.discount_amount,
                adjusted_profit_amount=item.adjusted_profit_amount,
                tax_amount=item.tax_amount,
                final_sale_price=item.final_sale_price,
                changed_at=item.changed_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
