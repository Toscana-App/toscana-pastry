from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from api.v1.dependencies import get_current_user, require_admin
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.ingredients.schemas import (
    ImportRequest,
    ImportResponse,
    IngredientCreate,
    IngredientDetailResponse,
    IngredientListResponse,
    IngredientResponse,
    IngredientUpdate,
    MovementListResponse,
    StockAdjustment,
    StockAdjustmentResponse,
    StockMovementResponse,
)
from domain.ingredients_import import ImportLineError, parse_import_line
from domain.models import Ingredient, StockMovement, StockStatus, User
from domain.repositories import IngredientRepository
from domain.stock import InsufficientStockError, apply_movement, stock_status

router = APIRouter(prefix="/ingredients", tags=["ingredients"])

_MOVEMENTS_IN_DETAIL_LIMIT = 50


def _to_response(ingredient: Ingredient) -> IngredientResponse:
    return IngredientResponse(
        id=ingredient.id,
        name=ingredient.name,
        unit=ingredient.unit,
        price_per_unit=ingredient.price_per_unit,
        stock_qty=ingredient.stock_qty,
        low_stock_threshold=ingredient.low_stock_threshold,
        status=stock_status(ingredient.stock_qty, ingredient.low_stock_threshold).value,
    )


def _movement_response(movement: StockMovement) -> StockMovementResponse:
    return StockMovementResponse(
        id=movement.id,
        qty_delta=movement.qty_delta,
        reason=movement.reason,
        ref=movement.ref,
        created_at=movement.created_at,
    )


@router.get("", response_model=IngredientListResponse)
async def list_ingredients(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    status_: Optional[StockStatus] = Query(default=None, alias="status"),
    repo: IngredientRepository = Depends(get_ingredient_repository),
    current_user: User = Depends(get_current_user),
):
    """Lista con búsqueda insensible a acentos/case (RF-P2-02) y filtro
    por estado de stock (RF-P2-03)."""
    items, total = await repo.list(q, status_, page, page_size)
    return IngredientListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=IngredientResponse, status_code=status.HTTP_201_CREATED)
async def create_ingredient(
    payload: IngredientCreate,
    repo: IngredientRepository = Depends(get_ingredient_repository),
    # Alta de insumos: funcion de administracion (RBAC de Fase 3).
    _admin: User = Depends(require_admin),
):
    try:
        ingredient = Ingredient(**payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    initial_movement = None
    if ingredient.stock_qty > 0:
        # La cantidad inicial deja huella en el historial (RF-P2-04).
        initial_movement = StockMovement(
            qty_delta=ingredient.stock_qty,
            reason="compra",
            ref="inicial",
            ingredient_id=ingredient.id,
        )
    await repo.create(ingredient, initial_movement)
    return _to_response(ingredient)


@router.post("/import", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
async def import_ingredients(
    payload: ImportRequest,
    repo: IngredientRepository = Depends(get_ingredient_repository),
    _admin: User = Depends(require_admin),
):
    """Carga inicial por lista (RF-P2-07): parsing tolerante por línea;
    las líneas en error se reportan, no abortan el lote."""
    created = 0
    errors = []
    for index, line in enumerate(payload.lines, start=1):
        try:
            parsed = parse_import_line(line)
        except ImportLineError as e:
            errors.append({"line": index, "message": str(e)})
            continue
        ingredient = Ingredient(
            name=parsed.name,
            unit=parsed.unit,
            price_per_unit=parsed.price_per_unit,
            stock_qty=parsed.qty,
        )
        initial_movement = None
        if parsed.qty > 0:
            initial_movement = StockMovement(
                qty_delta=parsed.qty,
                reason="compra",
                ref="inicial",
                ingredient_id=ingredient.id,
            )
        await repo.create(ingredient, initial_movement)
        created += 1
    return ImportResponse(created=created, errors=errors)


@router.get("/{ingredient_id}", response_model=IngredientDetailResponse)
async def get_ingredient(
    ingredient_id: str,
    include_movements: bool = Query(default=False),
    repo: IngredientRepository = Depends(get_ingredient_repository),
    current_user: User = Depends(get_current_user),
):
    ingredient = await repo.get(ingredient_id)
    if ingredient is None:
        # 404 anti-sondeo (security #7): borrado suave incluido.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente no encontrado")
    movements = None
    if include_movements:
        movement_items, _ = await repo.list_movements(
            ingredient_id, 1, _MOVEMENTS_IN_DETAIL_LIMIT
        )
        movements = [_movement_response(m) for m in movement_items]
    return IngredientDetailResponse(
        ingredient=_to_response(ingredient), movements=movements
    )


@router.patch("/{ingredient_id}", response_model=IngredientResponse)
async def update_ingredient(
    ingredient_id: str,
    payload: IngredientUpdate,
    repo: IngredientRepository = Depends(get_ingredient_repository),
    _admin: User = Depends(require_admin),
):
    existing = await repo.get(ingredient_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente no encontrado")
    updates = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    try:
        updated = Ingredient(
            name=updates.get("name", existing.name),
            unit=updates.get("unit", existing.unit),
            price_per_unit=updates.get("price_per_unit", existing.price_per_unit),
            stock_qty=existing.stock_qty,
            low_stock_threshold=updates.get("low_stock_threshold", existing.low_stock_threshold),
            id=existing.id,
            deleted_at=existing.deleted_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    saved = await repo.update(updated)
    if saved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente no encontrado")
    return _to_response(saved)


@router.delete("/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ingredient(
    ingredient_id: str,
    repo: IngredientRepository = Depends(get_ingredient_repository),
    _admin: User = Depends(require_admin),
):
    """UC-05: si participa en recetas activas → 409 con el impacto.
    Si no → borrado suave (el frontend ofrece undo re-creando)."""
    impacted = await repo.count_active_recipes(ingredient_id)
    if impacted > 0:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"impacted_recipes": impacted},
        )
    deleted = await repo.soft_delete(ingredient_id)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente no encontrado")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{ingredient_id}/stock", response_model=StockAdjustmentResponse)
async def adjust_stock(
    ingredient_id: str,
    payload: StockAdjustment,
    repo: IngredientRepository = Depends(get_ingredient_repository),
    _admin: User = Depends(require_admin),
):
    ingredient = await repo.get(ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente no encontrado")
    try:
        updated, movement = apply_movement(
            ingredient, payload.delta, payload.reason, payload.ref
        )
    except (InsufficientStockError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    saved = await repo.add_movement(ingredient_id, movement, updated.stock_qty)
    if saved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente no encontrado")
    return StockAdjustmentResponse(
        stock_qty=updated.stock_qty, movement=_movement_response(saved)
    )


@router.get("/{ingredient_id}/movements", response_model=MovementListResponse)
async def list_movements(
    ingredient_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    repo: IngredientRepository = Depends(get_ingredient_repository),
    current_user: User = Depends(get_current_user),
):
    ingredient = await repo.get(ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingrediente no encontrado")
    items, total = await repo.list_movements(ingredient_id, page, page_size)
    return MovementListResponse(
        items=[_movement_response(m) for m in items],
        total=total,
        page=page,
        page_size=page_size,
    )
