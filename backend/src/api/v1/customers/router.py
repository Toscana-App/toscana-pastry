"""Router de clientes: CRUD de pedidos (Fase 6, P6) + libro de
direcciones por cliente (RF-P11-09, C2).

- /customers (P6): lectura cualquier autenticado; alta admin. Sin edicion
  ni borrado: el historial de pedidos no se rompe.
- /customers/me/addresses (C2): roles CUSTOMER y NEGOCIO. Anti-sondeo:
  direcciones ajenas devuelven 404, nunca 403.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

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
from api.v1.dependencies import get_current_user, require_role
from data.repositories.sql_customer_address_repository import (
    SQLCustomerAddressRepository,
)
from domain.customer_address import (
    MAX_ADDRESSES_PER_CUSTOMER,
    CustomerAddress,
)
from domain.models import User, UserRole
from domain.orders import Customer

router = APIRouter(prefix="/customers", tags=["customers"])

_ADDRESS_GUARD = require_role(UserRole.CUSTOMER, UserRole.NEGOCIO)


def _customer_response(customer: Customer) -> CustomerResponse:
    return CustomerResponse(
        id=customer.id or "",
        name=customer.name,
        phone=customer.phone,
        created_at=customer.created_at.isoformat() if customer.created_at else "",
    )


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    q: str | None = Query(default=None, min_length=1, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo=Depends(get_customer_repository),
    current_user: User = Depends(get_current_user),
):
    """Listado P6 con busqueda por nombre (sin acentos) o subcadena de
    telefono (RF-P6-08)."""
    items, total = await repo.list(q, page, page_size)
    return CustomerListResponse(
        items=[_customer_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED
)
async def create_customer(
    payload: CustomerCreate,
    repo=Depends(get_customer_repository),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Crea o reutiliza (dedup nombre+telefono). Duplicado: 409 con el
    cliente existente (RF-P6-08)."""
    try:
        customer = Customer(name=payload.name, phone=payload.phone)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    existing, created = await repo.get_or_create(customer)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cliente duplicado (mismo nombre y telefono)",
            headers={"X-Customer-Id": existing.id or ""},
        )
    return _customer_response(existing)


def _response(address: CustomerAddress) -> AddressResponse:
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
    repo: SQLCustomerAddressRepository = Depends(get_customer_address_repository),
    current_user: User = Depends(_ADDRESS_GUARD),
):
    """GET /customers/me/addresses: lista el libro del usuario."""
    items = await repo.list_by_user(current_user.id)
    return AddressListResponse(items=[_response(item) for item in items])


@router.post(
    "/me/addresses",
    response_model=AddressEnvelope,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_address(
    payload: AddressCreate,
    repo: SQLCustomerAddressRepository = Depends(get_customer_address_repository),
    current_user: User = Depends(_ADDRESS_GUARD),
):
    """POST /customers/me/addresses: crea una direccion (max 5, RF-P11-09).

    La primera creada pasa a default (exactly-one-default).
    """
    count = await repo.count_by_user(current_user.id)
    if count >= MAX_ADDRESSES_PER_CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Maximo {MAX_ADDRESSES_PER_CUSTOMER} direcciones por cliente",
        )
    try:
        address = CustomerAddress(
            street_line_1=payload.street_line_1,
            street_line_2=payload.street_line_2,
            city=payload.city,
            postal_code=payload.postal_code,
            province=payload.province,
            phone=payload.phone,
            is_default=count == 0,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from err
    await repo.insert(address, current_user.id)
    await repo.commit()
    return AddressEnvelope(address=_response(address))


@router.patch(
    "/me/addresses/{address_id}",
    response_model=AddressEnvelope,
)
async def update_my_address(
    address_id: str,
    payload: AddressUpdate,
    repo: SQLCustomerAddressRepository = Depends(get_customer_address_repository),
    current_user: User = Depends(_ADDRESS_GUARD),
):
    """PATCH /customers/me/addresses/{id}: edita (anti-sondeo: 404 si ajena).

    `is_default=true` demueve la default anterior en la misma transaccion.
    `is_default=false` sobre la default vigente rompe el invariant
    exactly-one-default → 422.
    """
    existing = await repo.get_for_user(address_id, current_user.id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Direccion no encontrada",
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

    new_default: bool | None = updates.get("is_default")
    if new_default is False and existing.is_default:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se puede quitar el default: debe existir exactamente una",
        )

    try:
        updated = CustomerAddress(
            street_line_1=updates.get("street_line_1", existing.street_line_1),
            street_line_2=updates.get("street_line_2", existing.street_line_2),
            city=updates.get("city", existing.city),
            postal_code=updates.get("postal_code", existing.postal_code),
            province=updates.get("province", existing.province),
            phone=updates.get("phone", existing.phone),
            is_default=existing.is_default,
            id=existing.id,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from err

    await repo.set_fields(updated, current_user.id)

    if new_default is True and not existing.is_default:
        current_default = await repo.default_for_user(current_user.id)
        if (
            current_default is not None
            and current_default.id != existing.id
        ):
            await repo.set_default_flag(
                current_default.id, current_user.id, is_default=False
            )
        await repo.set_default_flag(existing.id, current_user.id, is_default=True)
        updated = CustomerAddress(
            street_line_1=updated.street_line_1,
            street_line_2=updated.street_line_2,
            city=updated.city,
            postal_code=updated.postal_code,
            province=updated.province,
            phone=updated.phone,
            is_default=True,
            id=updated.id,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )

    await repo.commit()
    return AddressEnvelope(address=_response(updated))


@router.delete(
    "/me/addresses/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_my_address(
    address_id: str,
    repo: SQLCustomerAddressRepository = Depends(get_customer_address_repository),
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

    count = await repo.count_by_user(current_user.id)
    if count <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede borrar la unica direccion del cliente",
        )

    was_default = existing.is_default
    await repo.remove(address_id, current_user.id)
    if was_default:
        remaining = await repo.list_by_user(current_user.id)
        if remaining:
            await repo.set_default_flag(
                remaining[0].id, current_user.id, is_default=True
            )
    await repo.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
