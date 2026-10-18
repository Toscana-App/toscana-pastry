"""Clientes (Fase 6, P6). Lectura: cualquier autenticado. Alta: admin.
Sin edicion ni borrado: el historial de pedidos no se rompe."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.v1.dependencies import get_current_user, require_admin
from api.v1.customers.dependencies import get_customer_repository
from api.v1.customers.schemas import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
)
from domain.models import User
from domain.orders import Customer
from domain.repositories import CustomerRepository


def _iso(dt) -> str:
    return dt.isoformat() if dt is not None else ""


def _response(customer: Customer) -> CustomerResponse:
    return CustomerResponse(
        id=customer.id or "",
        name=customer.name,
        phone=customer.phone,
        created_at=_iso(customer.created_at),
    )


router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: CustomerRepository = Depends(get_customer_repository),
    current_user: User = Depends(get_current_user),
):
    """Listado con busqueda por nombre (sin acentos) o subcadena de
    telefono (RF-P6-08)."""
    items, total = await repo.list(q, page, page_size)
    return CustomerListResponse(
        items=[_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    repo: CustomerRepository = Depends(get_customer_repository),
    _admin: User = Depends(require_admin),
):
    """Crea o reutiliza (dedup nombre+telefono). Duplicado: 409 con el
    cliente existente (RF-P6-08)."""
    try:
        customer = Customer(name=payload.name, phone=payload.phone)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    existing, created = await repo.get_or_create(customer)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cliente duplicado (mismo nombre y telefono)",
            headers={"X-Customer-Id": existing.id or ""},
        )
    return _response(existing)
