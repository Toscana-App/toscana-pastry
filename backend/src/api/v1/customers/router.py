"""Router del libro de direcciones por cliente (RF-P11-09, C2).

Namespace: /api/v1/customers/me/addresses.
Roles permitidos: CUSTOMER y NEGOCIO (admin no tiene "mis direcciones" → 403).
Anti-sondeo: direcciones ajenas devuelven 404, nunca 403.
"""
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError

from api.v1.customers.dependencies import get_customer_address_repository
from api.v1.customers.schemas import (
    AddressCreate,
    AddressEnvelope,
    AddressListResponse,
    AddressResponse,
    AddressUpdate,
)
from api.v1.dependencies import require_role
from domain.customer_address import (
    CannotRemoveOnlyAddress,
    CustomerAddress,
    add_address,
    apply_changes,
    default_to_demote,
    remove_address,
)
from domain.models import User, UserRole
from domain.repositories import CustomerAddressRepository

router = APIRouter(prefix="/customers", tags=["customers"])

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
    repo: CustomerAddressRepository = Depends(get_customer_address_repository),
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
    return AddressEnvelope(address=_response(address))


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
    return AddressEnvelope(address=_response(updated))


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
