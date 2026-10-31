"""Router del ABM de cupones (RF-P11-14, C3).

Todos los endpoints son admin-only (spec: ABM admin).
Namespace: /api/v1/coupons.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.v1.coupons.dependencies import get_coupon_repository
from api.v1.coupons.schemas import (
    CouponCreate,
    CouponEnvelope,
    CouponListResponse,
    CouponResponse,
    CouponUpdate,
)
from api.v1.dependencies import require_admin
from data.repositories.sql_coupon_repository import SQLCouponRepository
from domain.coupon import Coupon
from domain.models import User

router = APIRouter(prefix="/coupons", tags=["coupons"])

PAGINATION_MAX = 100

# Campos que un PATCH puede volver a None explicitamente.
NULLABLE_UPDATE_FIELDS = {"valid_from", "valid_until", "max_uses"}


def _response(coupon: Coupon) -> CouponResponse:
    return CouponResponse(
        id=coupon.id,
        code=coupon.code,
        type=coupon.type,
        value=coupon.value,
        valid_from=coupon.valid_from,
        valid_until=coupon.valid_until,
        max_uses=coupon.max_uses,
        uses=coupon.uses,
        status=coupon.status,
        created_at=coupon.created_at,
        updated_at=coupon.updated_at,
    )


@router.get("", response_model=CouponListResponse)
async def list_coupons(
    q: str | None = Query(default=None, min_length=1, max_length=120),
    status: Literal["active", "paused"] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=PAGINATION_MAX),
    repo: SQLCouponRepository = Depends(get_coupon_repository),
    _admin: User = Depends(require_admin),
):
    """GET /coupons: listado admin con ?q (code, case/accent-insensitive) y ?status."""
    items, total = await repo.list(q, status, page, page_size)
    return CouponListResponse(
        items=[_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "", response_model=CouponEnvelope, status_code=status.HTTP_201_CREATED
)
async def create_coupon(
    payload: CouponCreate,
    repo: SQLCouponRepository = Depends(get_coupon_repository),
    _admin: User = Depends(require_admin),
):
    """POST /coupons: crea un cupon (code unico case-insensitive → 409)."""
    existing = await repo.get_by_code(payload.code)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un cupon con el codigo {payload.code!r}",
        )
    try:
        coupon = Coupon(
            code=payload.code,
            type=payload.type,
            value=payload.value,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            max_uses=payload.max_uses,
            status=payload.status,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from err
    created = await repo.create(coupon)
    return CouponEnvelope(coupon=_response(created))


@router.patch("/{coupon_id}", response_model=CouponEnvelope)
async def update_coupon(
    coupon_id: str,
    payload: CouponUpdate,
    repo: SQLCouponRepository = Depends(get_coupon_repository),
    _admin: User = Depends(require_admin),
):
    """PATCH /coupons/{id}: edita campos / pausa-reactiva (RF-P11-14).

    El estado mergeado se revalida contra el dominio (percent 0-100,
    ventana de vigencia, max_uses → 422). Cambiar `code` a uno ya
    existente (cualquier case) → 409.
    """
    existing = await repo.get(coupon_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cupon no encontrado",
        )

    updates = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None or key in NULLABLE_UPDATE_FIELDS
    }
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="al menos un campo para actualizar",
        )

    new_code = updates.get("code")
    if new_code is not None and new_code != existing.code:
        duplicate = await repo.get_by_code(new_code)
        if duplicate is not None and duplicate.id != existing.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un cupon con el codigo {new_code!r}",
            )

    try:
        updated = Coupon(
            code=updates.get("code", existing.code),
            type=updates.get("type", existing.type),
            value=updates.get("value", existing.value),
            valid_from=updates.get("valid_from", existing.valid_from),
            valid_until=updates.get("valid_until", existing.valid_until),
            max_uses=updates.get("max_uses", existing.max_uses),
            status=updates.get("status", existing.status),
            uses=existing.uses,
            id=existing.id,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from err

    saved = await repo.update(updated)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cupon no encontrado",
        )
    return CouponEnvelope(coupon=_response(saved))


@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coupon(
    coupon_id: str,
    repo: SQLCouponRepository = Depends(get_coupon_repository),
    _admin: User = Depends(require_admin),
):
    """DELETE /coupons/{id}: usado en pedidos → 409 y se pausa en su lugar.

    Sin usos se borra (204). El "uso" se refleja en `uses` (C4 lo
    incrementa al confirmar pedidos).
    """
    existing = await repo.get(coupon_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cupon no encontrado",
        )

    if existing.uses > 0:
        await repo.set_status(coupon_id, "paused")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El cupon fue usado en pedidos: se pauso en su lugar",
        )

    await repo.delete(coupon_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
