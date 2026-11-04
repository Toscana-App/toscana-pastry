"""Order window router (RF-P5-07 / RF-P6-09): corte de pedidos.

El admin abre o cierra la ventana de pedidos del portal. Cerrada, el
portal rechaza los pedidos nuevos con 409 y muestra el mensaje; al
reabrir, `reopens_at` se limpia.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.dependencies import require_admin
from data.db import get_db
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.order_window import OrderWindow
from domain.models import User

from .schemas import OrderWindowResponse, OrderWindowUpdate

router = APIRouter(prefix="/tenant", tags=["order-window"])


def get_order_repository(db: AsyncSession = Depends(get_db)) -> SQLOrderRepository:
    return SQLOrderRepository(db)


def _response(window: OrderWindow) -> OrderWindowResponse:
    return OrderWindowResponse(
        open=window.open,
        reopens_at=window.reopens_at,
        message=window.message,
    )


@router.get("/order-window", response_model=OrderWindowResponse)
async def get_order_window(
    repo: SQLOrderRepository = Depends(get_order_repository),
    _user: User = Depends(require_admin),
):
    """Estado de la ventana de pedidos (RF-P6-09).

    Sin configuración previa devuelve la ventana por defecto: abierta.
    """
    window = await repo.get_order_window()
    return _response(window)


@router.patch("/order-window", response_model=OrderWindowResponse)
async def update_order_window(
    payload: OrderWindowUpdate,
    repo: SQLOrderRepository = Depends(get_order_repository),
    _user: User = Depends(require_admin),
):
    """Abre o cierra la ventana de pedidos (RF-P5-07).

    - Cerrar sin `reopens_at` → 422 con sugerencia de fijar la hora.
    - `message` > 200 caracteres → 422 (validación del schema).
    - Al abrir, `reopens_at` se limpia (siempre nulo).
    """
    reopens_at = None if payload.open else payload.reopens_at
    try:
        window = OrderWindow(
            open=payload.open,
            reopens_at=reopens_at,
            message=payload.message,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    await repo.update_order_window(window)
    current = await repo.get_order_window()
    return _response(current)
