"""Router del carrito server-side (RF-P11-03/14, C4).

Namespace: /api/v1/cart.
Roles: CUSTOMER y NEGOCIO (self-service del portal; admin → 403).
El precio se deriva en cada lectura via ``derive_audience_price``
(RNF-P11-03): nunca se persiste como fuente.
"""
import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.cart.dependencies import get_cart_repository
from api.v1.cart.schemas import (
    CartCouponOut,
    CartItemCreate,
    CartItemOut,
    CartResponse,
    CouponApply,
)
from api.v1.coupons.dependencies import get_coupon_repository
from api.v1.dependencies import require_role
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.settings.dependencies import get_settings_repository
from data.repositories.sql_cart_repository import SQLCartRepository
from data.repositories.sql_coupon_repository import SQLCouponRepository
from domain.cart import (
    MAX_CART_LINES,
    CartLine,
    cart_totals,
    validate_coupon_for_cart,
)
from domain.coupon import Coupon
from domain.models import User, UserRole
from domain.pricing_service import _resolve_audience, derive_audience_price
from domain.repositories import IngredientRepository
from domain.use_cases import GetSettings

router = APIRouter(prefix="/cart", tags=["cart"])

_CART_GUARD = require_role(UserRole.CUSTOMER, UserRole.NEGOCIO)


def _coupon_out(coupon: Coupon) -> CartCouponOut:
    return CartCouponOut(
        code=coupon.code,
        type=coupon.type,
        value=str(coupon.value),
    )


async def _build_cart(
    cart_repo: SQLCartRepository,
    ingredient_repo: IngredientRepository,
    settings_repo,
    coupon_repo: SQLCouponRepository,
    user: User,
) -> CartResponse:
    """Snapshotea el carrito con los precios derivados de la audiencia."""
    audience = _resolve_audience(user.role, None)
    settings = await GetSettings(settings_repo).execute()
    lines_state, coupon_code = await cart_repo.get_state(user.id)

    items: list[CartItemOut] = []
    cart_lines: list[CartLine] = []
    for product_id, qty in lines_state:
        product = await ingredient_repo.get(product_id)
        if product is None:
            # Producto borrado: la linea deja de contribuir al total.
            continue
        unit_price = derive_audience_price(
            product.price_per_unit,
            settings.consumer_markup_pct,
            audience,
        )
        line = CartLine(
            product_id=product_id,
            product_name=product.name,
            unit_price=unit_price,
            qty=qty,
        )
        cart_lines.append(line)
        items.append(
            CartItemOut(
                product_id=product_id,
                name=product.name,
                unit_price=str(unit_price),
                qty=qty,
                total=str(line.total),
            )
        )

    coupon: Coupon | None = None
    if coupon_code is not None:
        coupon = await coupon_repo.get_by_code(coupon_code)
        if coupon is None:
            # Cupon borrado/pausado a posteriori: sin efecto.
            coupon = None

    totals = cart_totals(cart_lines, coupon, settings.round_step)

    return CartResponse(
        audience=audience,
        items=items,
        subtotal=str(totals.subtotal),
        total=str(totals.final),
        discount_amount=str(totals.discount_amount),
        coupon=_coupon_out(coupon) if coupon is not None else None,
    )


@router.get("", response_model=CartResponse)
async def get_cart(
    cart_repo: SQLCartRepository = Depends(get_cart_repository),
    ingredient_repo: IngredientRepository = Depends(
        get_ingredient_repository
    ),
    settings_repo = Depends(get_settings_repository),
    coupon_repo: SQLCouponRepository = Depends(get_coupon_repository),
    current_user: User = Depends(_CART_GUARD),
):
    """GET /cart: carrito del usuario con precios de su audiencia."""
    return await _build_cart(
        cart_repo, ingredient_repo, settings_repo, coupon_repo, current_user
    )


@router.post("/items", response_model=CartResponse)
async def add_cart_item(
    payload: CartItemCreate,
    cart_repo: SQLCartRepository = Depends(get_cart_repository),
    ingredient_repo: IngredientRepository = Depends(
        get_ingredient_repository
    ),
    settings_repo = Depends(get_settings_repository),
    coupon_repo: SQLCouponRepository = Depends(get_coupon_repository),
    current_user: User = Depends(_CART_GUARD),
):
    """POST /cart/items: agrega o altera la cantidad de una linea.

    404 si el producto no existe; 422 si se superan las 50 lineas
    (solo al agregar una nueva; alterar cantidad no cuenta).
    """
    product = await ingredient_repo.get(payload.product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )

    if not await cart_repo.item_exists(current_user.id, payload.product_id):
        count = await cart_repo.count_items(current_user.id)
        if count >= MAX_CART_LINES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Maximo {MAX_CART_LINES} lineas en el carrito",
            )

    await cart_repo.upsert_item(
        current_user.id, payload.product_id, payload.qty
    )
    await cart_repo.commit()
    return await _build_cart(
        cart_repo, ingredient_repo, settings_repo, coupon_repo, current_user
    )


@router.delete("/items/{product_id}", response_model=CartResponse)
async def remove_cart_item(
    product_id: str,
    cart_repo: SQLCartRepository = Depends(get_cart_repository),
    ingredient_repo: IngredientRepository = Depends(
        get_ingredient_repository
    ),
    settings_repo = Depends(get_settings_repository),
    coupon_repo: SQLCouponRepository = Depends(get_coupon_repository),
    current_user: User = Depends(_CART_GUARD),
):
    """DELETE /cart/items/{product_id}: quita la linea (404 si no existe)."""
    removed = await cart_repo.remove_item(current_user.id, product_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linea no encontrada en el carrito",
        )
    await cart_repo.commit()
    return await _build_cart(
        cart_repo, ingredient_repo, settings_repo, coupon_repo, current_user
    )


@router.post("/coupon", response_model=CartResponse)
async def apply_coupon(
    payload: CouponApply,
    cart_repo: SQLCartRepository = Depends(get_cart_repository),
    ingredient_repo: IngredientRepository = Depends(
        get_ingredient_repository
    ),
    settings_repo = Depends(get_settings_repository),
    coupon_repo: SQLCouponRepository = Depends(get_coupon_repository),
    current_user: User = Depends(_CART_GUARD),
):
    """POST /cart/coupon: aplica un cupon (max 1 por carrito).

    422 con razon explícita: coupon_not_found / coupon_inactive /
    coupon_expired / coupon_limit_reached. Aplicar otro cupon reemplaza
    al vigente (nunca se incrementa ``uses`` aqui: es al confirmar el
    pedido, RF-P11-14).
    """
    coupon = await coupon_repo.get_by_code(payload.code)
    if coupon is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="coupon_not_found",
        )
    error_code = validate_coupon_for_cart(
        coupon, datetime.datetime.now(datetime.UTC)
    )
    if error_code is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_code,
        )
    await cart_repo.set_coupon_code(current_user.id, coupon.code)
    await cart_repo.commit()
    return await _build_cart(
        cart_repo, ingredient_repo, settings_repo, coupon_repo, current_user
    )


@router.delete("/coupon", response_model=CartResponse)
async def remove_coupon(
    cart_repo: SQLCartRepository = Depends(get_cart_repository),
    ingredient_repo: IngredientRepository = Depends(
        get_ingredient_repository
    ),
    settings_repo = Depends(get_settings_repository),
    coupon_repo: SQLCouponRepository = Depends(get_coupon_repository),
    current_user: User = Depends(_CART_GUARD),
):
    """DELETE /cart/coupon: quita el cupon aplicado (no-op si no hay)."""
    await cart_repo.clear_coupon(current_user.id)
    await cart_repo.commit()
    return await _build_cart(
        cart_repo, ingredient_repo, settings_repo, coupon_repo, current_user
    )
