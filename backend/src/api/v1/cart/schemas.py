"""Schemas del carrito (RF-P11-03/14, C4).

Los montos viajan como str (Money): nunca float en la API (RNF-P4-02).
"""

from pydantic import BaseModel, Field


class CartItemCreate(BaseModel):
    product_id: str
    qty: int = Field(ge=1, le=999, description="Cantidad 1-999 (RF-P11-03)")


class CouponApply(BaseModel):
    code: str


class CartCouponOut(BaseModel):
    code: str
    type: str
    value: str


class CartItemOut(BaseModel):
    product_id: str
    name: str
    unit_price: str
    qty: int
    total: str


class CartResponse(BaseModel):
    audience: str
    items: list[CartItemOut]
    subtotal: str
    total: str
    discount_amount: str
    coupon: CartCouponOut | None
