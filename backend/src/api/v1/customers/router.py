"""Clientes: CRUD de pedidos (Fase 6, P6) + libro de direcciones por
cliente (RF-P11-09, C2).

- /customers (P6): lectura cualquier autenticado; alta admin. Sin edicion
  ni borrado: el historial de pedidos no se rompe.
- /customers/me/addresses (C2): roles CUSTOMER y NEGOCIO (admin no tiene
  "mis direcciones" -> 403). Anti-sondeo: direcciones ajenas devuelven 404,
  nunca 403.
"""
from contextlib import contextmanager
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError

from api.v1.dependencies import get_current_user, require_admin, require_role
from api.v1.customers.dependencies import (
    get_customer_address_repository,
    get_customer_repository,
)
from api.v1.customers.schemas import (
    AddressCreate,
    AddressEnvelope,
    AddressListResponse,
    AddressResponse,
    AddressUpdate,
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
)
from domain.customer_address import (
    CannotRemoveOnlyAddress,
    CustomerAddress,
    add_address,
    apply_changes,
    default_to_demote,
    remove_address,
)
from domain.models import User, UserRole
from domain.orders import Customer
from domain.repositories import CustomerAddressRepository, CustomerRepository


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


_ADDRESS_GUARD = require_role(UserRole.CUSTOMER, UserRole.NEGOCIO)
_NON_NULLABLE_FIELDS = {"street_line_1", "is_default"}


@contextmanager
def _default_conflict_as_409():
    """Map a violation of the one-default-per-user unique index to 409."""
    try:
        yield
    except IntegrityError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflicto: ya existe una direccion por defecto",
        ) from err


def _address_response(address: CustomerAddress) -> AddressResponse:
    return AddressResponse(
        id=address.id,
        street_line_1=address.street_line_1,
        street_line_2=address.street_line_2,
        city=address.city,
        postal_code=address.postal_code,
        province=address.province,
        phone=address.phone,
        is_default=address.is_default,
        created_at=address.created_at,
        updated_at=address.updated_at,
    )


@router.get("/me/addresses", response_model=AddressListResponse)
async def list_my_addresses(
    repo: CustomerAddressRepository = Depends(get_customer_address_repository),
    current_user: User = Depends(_ADDRESS_GUARD),
):
    """GET /customers/me/addresses: lista el libro del usuario."""
    items = await repo.list_by_user(current_user.id)
    return AddressListResponse(items=[_address_response(item) for item in items])


@router.post(
    "/me/addresses",
    response_model=AddressEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_address(
    payload: AddressCreate,
    repo: CustomerAddressRepository = Depends(get_customer_address_repository),
    current_user: User = Depends(_ADDRESS_GUARD),
):
    """POST /customers/me/addresses: crea una direccion (max 5, RF-P11-09).

    La primera creada pasa a default (exactly-one-default).
    """
    await repo.lock_book(current_user.id)
    existing = await repo.list_by_user(current_user.id)
    try:
        address = add_address(
            existing,
            CustomerAddress(
                street_line_1=payload.street_line_1,
                street_line_2=payload.street_line_2,
                city=payload.city,
                postal_code=payload.postal_code,
                province=payload.province,
                phone=payload.phone,
            ),
        )
    except ValueError as err:  # includes AddressLimitExceeded
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from err
    with _default_conflict_as_409():
        await repo.insert(address, current_user.id)
        await repo.commit()
    return AddressEnvelope(address=_address_response(address))


@router.patch(
    "/me/addresses/{address_id}",
    response_model=AddressEnvelope,
)
async def update_my_address(
    address_id: str,
    payload: AddressUpdate,
    repo: CustomerAddressRepository = Depends(get_customer_address_repository),
    current_user: User = Depends(_ADDRESS_GUARD),
):
    """PATCH /customers/me/addresses/{id}: edita (anti-sondeo: 404 si ajena).

    `is_default=true` demueve la default anterior en la misma transaccion.
    `is_default=false` sobre la default vigente rompe el invariant
    exactly-one-default → 422.
    """
    await repo.lock_book(current_user.id)
    existing = await repo.get_for_user(address_id, current_user.id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Direccion no encontrada",
        )

    # exclude_unset distingue "ausente" de null explicito: los opcionales
    # aceptan null para limpiarse; street_line_1 e is_default no.
    updates = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None or key not in _NON_NULLABLE_FIELDS
    }
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="al menos un campo para actualizar",
        )

    new_default: bool | None = updates.pop("is_default", None)
    try:
        updated = apply_changes(existing, updates, set_default=new_default)
    except ValueError as err:  # includes CannotUnsetDefault
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from err

    with _default_conflict_as_409():
        if new_default is True and not existing.is_default:
            addresses = await repo.list_by_user(current_user.id)
            for demoted_id in default_to_demote(addresses, existing.id):
                await repo.set_default_flag(
                    demoted_id, current_user.id, is_default=False
                )
        await repo.set_fields(updated, current_user.id)
        await repo.commit()
    return AddressEnvelope(address=_address_response(updated))


@router.delete(
    "/me/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_my_address(
    address_id: str,
    repo: CustomerAddressRepository = Depends(get_customer_address_repository),
    current_user: User = Depends(_ADDRESS_GUARD),
):
    """DELETE /customers/me/addresses/{id}: elimina (anti-sondeo: 404 si ajena).

    Borrar la unica direccion → 409. Al borrar la default, la mas antigua
    restante (por created_at) hereda el default en la misma transaccion.
    """
    existing = await repo.get_for_user(address_id, current_user.id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Direccion no encontrada",
        )

    await repo.lock_book(current_user.id)
    addresses = await repo.list_by_user(current_user.id)
    try:
        heir_id = remove_address(addresses, address_id)
    except CannotRemoveOnlyAddress as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err

    with _default_conflict_as_409():
        await repo.remove(address_id, current_user.id)
        if heir_id is not None:
            await repo.set_default_flag(
                heir_id, current_user.id, is_default=True
            )
        await repo.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
