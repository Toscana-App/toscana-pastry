"""Casos de prueba e2e GIVEN-WHEN-THEN.

Secciones autoritativas:
- A/B/C: ODD e2e-order-lifecycle (creacion, maquina de pedido, pagos).
- D: ODD payment-methods (cash/transfer/MP en la maquina de pagos).
- R: ODD transfer_receipt_verification S8 (comprobante de transferencia).

Cada caso: GIVEN (precondicion) / WHEN (accion HTTP) / THEN (asercion exacta).
El harness solo hace HTTP y asierta: cero logica de negocio (ODD S4). La unica
lectura fuera de HTTP es la auditoria de `payment_events` (ODD S6).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

import httpx
from sqlalchemy import func, select

from data.db import AsyncSessionLocal
from data.models import OrderORM, PaymentEventORM

WEBHOOK_SECRET = "e2e-webhook-secret"
WEBHOOK_PATH = "/api/v1/webhooks/mercadopago"
CASH = "cash"
MP = "mercadopago"
TRANSFER = "transfer"


class E2EFailure(AssertionError):
    """Fallo de un caso e2e (mensaje = lo que no se cumplio del THEN)."""


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise E2EFailure(msg)


# --------------------------------------------------------------------------
# helpers de transporte (no son logica de negocio)
# --------------------------------------------------------------------------


async def make_client(base_url: str, email: str, google_id: str) -> httpx.AsyncClient:
    raw = httpx.AsyncClient(base_url=base_url, timeout=15)
    try:
        resp = await raw.post(
            "/api/v1/auth/login", json={"email": email, "google_id": google_id}
        )
    finally:
        await raw.aclose()
    check(resp.status_code == 200, f"login {email}: {resp.status_code} {resp.text[:200]}")
    # La cookie auth_token se setea con secure=True (correcto en prod/TLS); la
    # suite corre sobre http://, asi que se replaya el valor con un jar sin el
    # flag secure (adaptacion del harness, no del producto).
    token = resp.cookies.get("auth_token")
    if token is None:
        raise E2EFailure(f"login {email}: sin cookie auth_token")
    return httpx.AsyncClient(base_url=base_url, cookies={"auth_token": token}, timeout=15)


def _order_body(product_id: str, qty: int, payment_method: str) -> dict[str, Any]:
    return {
        "items": [{"product_id": product_id, "quantity": qty}],
        "date": (dt.date.today() + dt.timedelta(days=1)).isoformat(),
        "delivery_mode": "delivery",
        "delivery_address": "Calle 14 450, Rio Tercero",
        "payment_method": payment_method,
    }


async def create_order(
    client: httpx.AsyncClient,
    product_id: str,
    qty: int = 1,
    payment_method: str = CASH,
    idempotency_key: str | None = None,
) -> httpx.Response:
    return await client.post(
        "/api/v1/orders/",
        json=_order_body(product_id, qty, payment_method),
        headers={"Idempotency-Key": idempotency_key or str(uuid.uuid4())},
    )


async def patch_status(client: httpx.AsyncClient, order_id: str, target: str) -> httpx.Response:
    return await client.patch(f"/api/v1/orders/{order_id}/status", json={"status": target})


async def get_order(client: httpx.AsyncClient, order_id: str) -> dict[str, Any]:
    resp = await client.get(f"/api/v1/orders/{order_id}")
    check(resp.status_code == 200, f"GET /orders/{order_id}: {resp.status_code} {resp.text[:200]}")
    return cast("dict[str, Any]", resp.json())


async def get_payment(client: httpx.AsyncClient, order_id: str) -> dict[str, Any]:
    # Estado de pago vive en su propio endpoint (el detalle admin no lo expone).
    resp = await client.get(f"/api/v1/orders/{order_id}/payment")
    check(resp.status_code == 200, f"GET /orders/{order_id}/payment: {resp.status_code} {resp.text[:200]}")
    return cast("dict[str, Any]", resp.json())


async def order_total_pesos(client: httpx.AsyncClient, order_id: str) -> Decimal:
    # El detalle admin expone total en centavos (Money); el webhook valida en pesos.
    body = await get_order(client, order_id)
    return Decimal(str(body["total"])) / 100


def signed_webhook(
    payment_id: str,
    *,
    signature: str | None = None,
    request_id: str | None = None,
    ts: str | None = None,
    data_id: str | None = None,
) -> tuple[bytes, dict[str, str]]:
    request_id = request_id or f"req-{uuid.uuid4()}"
    ts = ts or str(round(dt.datetime.now(dt.UTC).timestamp()))
    data_id = data_id or payment_id
    if signature is None:
        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        v1 = hmac.new(WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        signature = f"ts={ts},v1={v1}"
    payload = json.dumps({"type": "payment", "data": {"id": data_id}}).encode()
    headers = {
        "Content-Type": "application/json",
        "x-signature": signature,
        "x-request-id": request_id,
    }
    return payload, headers


async def send_webhook(client: httpx.AsyncClient, **kwargs: Any) -> httpx.Response:
    payload, headers = signed_webhook(kwargs.pop("payment_id"), **kwargs)
    return await client.post(WEBHOOK_PATH, content=payload, headers=headers)


async def register_payment(
    mock_base: str,
    payment_id: str,
    order_id: str,
    status: str,
    amount: str,
    currency: str = "ARS",
) -> None:
    resp = await httpx.AsyncClient().post(
        f"{mock_base}/__admin/payments",
        json={
            "id": payment_id,
            "order_id": order_id,
            "status": status,
            "amount": amount,
            "currency": currency,
        },
    )
    check(resp.status_code == 200, f"mock MP register {payment_id}: {resp.status_code}")


async def payment_events_count(order_id: str) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(PaymentEventORM)
            .where(PaymentEventORM.order_id == order_id)
        )
        return int(result.scalar_one())


async def order_paid_at(order_id: str) -> dt.datetime | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OrderORM.paid_at).where(OrderORM.id == order_id)
        )
        return cast("dt.datetime | None", result.scalar_one())


async def catalog_price(
    client: httpx.AsyncClient, product_id: str
) -> Decimal:
    resp = await client.get("/api/v1/products", params={"audience": "consumidor_final"})
    check(resp.status_code == 200, f"GET /products: {resp.status_code} {resp.text[:200]}")
    for item in resp.json()["products"]:
        if item["id"] == product_id:
            check(item.get("price") is not None, f"producto {product_id} sin precio en catalogo")
            return Decimal(str(item["price"]))
    raise E2EFailure(f"producto {product_id} no aparece en el catalogo")


# --------------------------------------------------------------------------
# contexto
# --------------------------------------------------------------------------


@dataclass
class Ctx:
    base_url: str
    mock_base: str
    admin: httpx.AsyncClient
    cust_a: httpx.AsyncClient
    cust_b: httpx.AsyncClient
    product_id: str
    catalog_price: Decimal
    public: httpx.AsyncClient  # sin cookies (el webhook no requiere auth)


async def build_ctx(base_url: str, mock_base: str, product_id: str) -> Ctx:
    from e2e.seed import (
        ADMIN_EMAIL,
        ADMIN_GOOGLE_ID,
        CUSTOMER_A_EMAIL,
        CUSTOMER_A_GOOGLE_ID,
        CUSTOMER_B_EMAIL,
        CUSTOMER_B_GOOGLE_ID,
    )

    admin = await make_client(base_url, ADMIN_EMAIL, ADMIN_GOOGLE_ID)
    cust_a = await make_client(base_url, CUSTOMER_A_EMAIL, CUSTOMER_A_GOOGLE_ID)
    cust_b = await make_client(base_url, CUSTOMER_B_EMAIL, CUSTOMER_B_GOOGLE_ID)
    public = httpx.AsyncClient(base_url=base_url, timeout=15)
    price = await catalog_price(cust_a, product_id)
    return Ctx(
        base_url=base_url,
        mock_base=mock_base,
        admin=admin,
        cust_a=cust_a,
        cust_b=cust_b,
        product_id=product_id,
        catalog_price=price,
        public=public,
    )


async def close_ctx(ctx: Ctx) -> None:
    for client in (ctx.admin, ctx.cust_a, ctx.cust_b, ctx.public):
        await client.aclose()


# --------------------------------------------------------------------------
# A — creacion de pedido (cliente)
# --------------------------------------------------------------------------


async def case_a1(ctx: Ctx) -> None:
    # GIVEN cliente autenticado, producto disponible, window abierto
    # WHEN crea pedido cash de 2 unidades
    resp = await create_order(ctx.cust_a, ctx.product_id, qty=2)
    # THEN 200, new, payment_status=pending (offline), paid False, total = 2 x precio
    check(resp.status_code in (200, 201), f"A1: creacion {resp.status_code} {resp.text[:200]}")
    body = resp.json()
    check(body["status"] == "new", f"A1: status {body['status']!r} != 'new'")
    check(body["payment_status"] == "pending", f"A1: payment_status {body['payment_status']!r} != 'pending'")
    check(body["paid"] is False, "A1: paid debe ser False")
    expected = (ctx.catalog_price * 2).quantize(Decimal("0.01"))
    check(Decimal(str(body["total"])) == expected, f"A1: total {body['total']} != 2 x {ctx.catalog_price} = {expected}")
    unit = Decimal(str(body["items"][0]["unit_price"]))
    check(unit == ctx.catalog_price, f"A1: unit_price {unit} != precio catalogo {ctx.catalog_price}")


async def case_a2(ctx: Ctx) -> None:
    # GIVEN order window cerrado
    reopens_at = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=1)).isoformat()
    closed = await ctx.admin.patch(
        "/api/v1/tenant/order-window",
        json={"open": False, "reopens_at": reopens_at, "message": "e2e"},
    )
    check(closed.status_code == 200, f"A2: cerrar window {closed.status_code} {closed.text[:200]}")
    try:
        # WHEN intenta crear pedido
        resp = await create_order(ctx.cust_a, ctx.product_id)
        # THEN 409 order_window_closed
        check(resp.status_code == 409, f"A2: {resp.status_code} != 409 {resp.text[:200]}")
        check(resp.json().get("detail") == "order_window_closed", f"A2: detail {resp.json().get('detail')!r}")
    finally:
        reopened = await ctx.admin.patch("/api/v1/tenant/order-window", json={"open": True})
        check(reopened.status_code == 200, f"A2: reabrir window {reopened.status_code}")


async def case_a3(ctx: Ctx) -> None:
    # GIVEN pedido ya creado con key K y body B
    key = str(uuid.uuid4())
    first = await create_order(ctx.cust_a, ctx.product_id, idempotency_key=key)
    check(first.status_code in (200, 201), f"A3: creacion {first.status_code}")
    first_id = first.json()["id"]
    # WHEN reintento con la misma key y el mismo body
    again = await create_order(ctx.cust_a, ctx.product_id, idempotency_key=key)
    # THEN mismo pedido, sin duplicado
    check(again.status_code in (200, 201), f"A3: reintento {again.status_code} {again.text[:200]}")
    check(again.json()["id"] == first_id, f"A3: reintento creo {again.json()['id']} != {first_id}")


async def case_a4(ctx: Ctx) -> None:
    # GIVEN pedido ya creado con key K y body B
    key = str(uuid.uuid4())
    first = await create_order(ctx.cust_a, ctx.product_id, qty=1, idempotency_key=key)
    check(first.status_code in (200, 201), f"A4: creacion {first.status_code}")
    # WHEN misma key, body distinto (qty 3)
    resp = await create_order(ctx.cust_a, ctx.product_id, qty=3, idempotency_key=key)
    # THEN 422 idempotency_key_mismatch
    check(resp.status_code == 422, f"A4: {resp.status_code} != 422 {resp.text[:200]}")
    check(resp.json().get("detail") == "idempotency_key_mismatch", f"A4: detail {resp.json().get('detail')!r}")


async def case_a5(ctx: Ctx) -> None:
    # GIVEN cliente es dueño de un pedido
    created = await create_order(ctx.cust_a, ctx.product_id)
    check(created.status_code in (200, 201), f"A5: creacion {created.status_code}")
    order_id = created.json()["id"]
    # WHEN el cliente intenta transicionar su propio pedido
    resp = await patch_status(ctx.cust_a, order_id, "confirmed")
    # THEN 403
    check(resp.status_code == 403, f"A5: {resp.status_code} != 403 {resp.text[:200]}")


async def case_a6(ctx: Ctx) -> None:
    # GIVEN cliente B tiene un pedido
    created_b = await create_order(ctx.cust_b, ctx.product_id)
    check(created_b.status_code in (200, 201), f"A6: creacion B {created_b.status_code}")
    code_b = created_b.json()["code"]
    # WHEN cliente A lee el pedido de B por codigo
    resp = await ctx.cust_a.get(f"/api/v1/orders/mine/{code_b}")
    # THEN 404 (anti-sondeo)
    check(resp.status_code == 404, f"A6: {resp.status_code} != 404 {resp.text[:200]}")


# --------------------------------------------------------------------------
# B — maquina de estados del pedido (admin)
# --------------------------------------------------------------------------


async def _new_order(ctx: Ctx, payment_method: str = CASH) -> str:
    created = await create_order(ctx.cust_a, ctx.product_id, payment_method=payment_method)
    check(created.status_code in (200, 201), f"precondicion creacion: {created.status_code} {created.text[:200]}")
    return cast(str, created.json()["id"])


async def _expect_invalid(ctx: Ctx, order_id: str, current: str, target: str, case: str) -> None:
    resp = await patch_status(ctx.admin, order_id, target)
    check(resp.status_code == 400, f"{case}: {resp.status_code} != 400 {resp.text[:200]}")
    check(
        resp.json().get("detail") == f"Transicion invalida: {current} -> {target}",
        f"{case}: detail {resp.json().get('detail')!r}",
    )
    body = await get_order(ctx.admin, order_id)
    check(body["status"] == current, f"{case}: estado {body['status']!r} != {current!r} (debe no haber cambiado)")


async def case_b1(ctx: Ctx) -> None:
    # GIVEN pedido new
    order_id = await _new_order(ctx)
    # WHEN admin recorre new->confirmed->preparing->pending_delivery->delivered
    for target in ("confirmed", "preparing", "pending_delivery", "delivered"):
        resp = await patch_status(ctx.admin, order_id, target)
        check(resp.status_code == 200, f"B1: -> {target}: {resp.status_code} {resp.text[:200]}")
    # THEN estado final delivered
    body = await get_order(ctx.admin, order_id)
    check(body["status"] == "delivered", f"B1: final {body['status']!r}")


async def case_b2(ctx: Ctx) -> None:
    # GIVEN pedido new
    order_id = await _new_order(ctx)
    # WHEN admin intenta el salto new -> delivered
    await _expect_invalid(ctx, order_id, "new", "delivered", "B2")


async def case_b3(ctx: Ctx) -> None:
    # GIVEN pedido confirmed
    order_id = await _new_order(ctx)
    check((await patch_status(ctx.admin, order_id, "confirmed")).status_code == 200, "B3: precondition")
    # WHEN admin cancela
    resp = await patch_status(ctx.admin, order_id, "cancelled")
    # THEN 200 cancelled
    check(resp.status_code == 200, f"B3: {resp.status_code} {resp.text[:200]}")
    body = await get_order(ctx.admin, order_id)
    check(body["status"] == "cancelled", f"B3: {body['status']!r}")


async def case_b4(ctx: Ctx) -> None:
    # GIVEN pedido preparing
    order_id = await _new_order(ctx)
    await patch_status(ctx.admin, order_id, "confirmed")
    check((await patch_status(ctx.admin, order_id, "preparing")).status_code == 200, "B4: precondition")
    # WHEN admin cancela
    resp = await patch_status(ctx.admin, order_id, "cancelled")
    check(resp.status_code == 200, f"B4: {resp.status_code} {resp.text[:200]}")
    body = await get_order(ctx.admin, order_id)
    check(body["status"] == "cancelled", f"B4: {body['status']!r}")


async def case_b5(ctx: Ctx) -> None:
    # GIVEN pedido new
    order_id = await _new_order(ctx)
    # WHEN admin cancela directamente
    # (O5/S4 habilito new -> cancelled para el flujo de rechazo de
    # comprobante; el ODD historico la tenia como invalida)
    resp = await patch_status(ctx.admin, order_id, "cancelled")
    # THEN 200 cancelled (sin efecto de stock: nunca se dedujo)
    check(resp.status_code == 200, f"B5: {resp.status_code} {resp.text[:200]}")
    body = await get_order(ctx.admin, order_id)
    check(body["status"] == "cancelled", f"B5: {body['status']!r} != cancelled")


async def case_b6(ctx: Ctx) -> None:
    # GIVEN pedido delivered
    order_id = await _new_order(ctx)
    for target in ("confirmed", "preparing", "pending_delivery"):
        check((await patch_status(ctx.admin, order_id, target)).status_code == 200, "B6: precondition")
    check((await patch_status(ctx.admin, order_id, "delivered")).status_code == 200, "B6: precondition")
    # WHEN admin intenta salir de delivered
    await _expect_invalid(ctx, order_id, "delivered", "confirmed", "B6")


async def case_b7(ctx: Ctx) -> None:
    # GIVEN pedido cancelled
    order_id = await _new_order(ctx)
    check((await patch_status(ctx.admin, order_id, "confirmed")).status_code == 200, "B7: precondition")
    check((await patch_status(ctx.admin, order_id, "cancelled")).status_code == 200, "B7: precondition")
    # WHEN admin intenta salir de cancelled
    await _expect_invalid(ctx, order_id, "cancelled", "confirmed", "B7")


# --------------------------------------------------------------------------
# C — maquina de estados de pago
# --------------------------------------------------------------------------


async def case_c1(ctx: Ctx) -> None:
    # GIVEN pedido sin payment_status; mock MP con pago aprobado (monto correcto, ARS)
    order_id = await _new_order(ctx, payment_method=MP)
    total = await order_total_pesos(ctx.admin, order_id)
    pid = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, pid, order_id, "approved", str(total))
    # WHEN webhook MP aprobado con firma valida
    resp = await send_webhook(ctx.public, payment_id=pid)
    check(resp.status_code == 200, f"C1: webhook {resp.status_code} {resp.text[:200]}")
    # THEN approved + paid + paid_at
    after = await get_payment(ctx.admin, order_id)
    check(after["status"] == "approved", f"C1: status {after['status']!r} != approved")
    check(after["paid"] is True, "C1: paid debe ser True")
    check(await order_paid_at(order_id) is not None, "C1: paid_at debe estar set en DB")


async def case_c2(ctx: Ctx) -> None:
    # GIVEN pedido sin payment_status
    order_id = await _new_order(ctx, payment_method=MP)
    total = str(await order_total_pesos(ctx.admin, order_id))
    p1 = f"mp-{uuid.uuid4().hex[:8]}"
    p2 = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, p1, order_id, "pending", total)
    # WHEN webhook pending y luego webhook approved
    check((await send_webhook(ctx.public, payment_id=p1)).status_code == 200, "C2: webhook pending")
    mid = await get_payment(ctx.admin, order_id)
    check(mid["status"] == "pending", f"C2: intermedio {mid['status']!r} != pending")
    await register_payment(ctx.mock_base, p2, order_id, "approved", total)
    check((await send_webhook(ctx.public, payment_id=p2)).status_code == 200, "C2: webhook approved")
    # THEN final approved
    after = await get_payment(ctx.admin, order_id)
    check(after["status"] == "approved", f"C2: final {after['status']!r} != approved")
    check(after["paid"] is True, "C2: paid debe ser True")


async def case_c3(ctx: Ctx) -> None:
    # GIVEN pedido con payment_status rejected
    order_id = await _new_order(ctx, payment_method=MP)
    total = str(await order_total_pesos(ctx.admin, order_id))
    p1 = f"mp-{uuid.uuid4().hex[:8]}"
    p2 = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, p1, order_id, "rejected", total)
    check((await send_webhook(ctx.public, payment_id=p1)).status_code == 200, "C3: webhook rejected")
    mid = await get_payment(ctx.admin, order_id)
    check(mid["status"] == "rejected", f"C3: {mid['status']!r} != rejected")
    # WHEN webhook approved (pago tardio, desbloqueo)
    await register_payment(ctx.mock_base, p2, order_id, "approved", total)
    check((await send_webhook(ctx.public, payment_id=p2)).status_code == 200, "C3: webhook approved")
    # THEN approved
    after = await get_payment(ctx.admin, order_id)
    check(after["status"] == "approved", f"C3: final {after['status']!r} != approved")


async def case_c4(ctx: Ctx) -> None:
    # GIVEN pedido approved por webhook previo
    order_id = await _new_order(ctx, payment_method=MP)
    total = str(await order_total_pesos(ctx.admin, order_id))
    p1 = f"mp-{uuid.uuid4().hex[:8]}"
    p2 = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, p1, order_id, "approved", total)
    check((await send_webhook(ctx.public, payment_id=p1)).status_code == 200, "C4: webhook approved")
    # WHEN webhook rejected tardio (event nuevo)
    await register_payment(ctx.mock_base, p2, order_id, "rejected", total)
    resp = await send_webhook(ctx.public, payment_id=p2)
    check(resp.status_code == 200, f"C4: webhook tardio {resp.status_code} {resp.text[:200]}")
    # THEN estado sigue approved; evento auditado (2 filas)
    after = await get_payment(ctx.admin, order_id)
    check(after["status"] == "approved", f"C4: {after['status']!r} != approved (approved es terminal)")
    check(await payment_events_count(order_id) == 2, f"C4: payment_events = {await payment_events_count(order_id)} != 2")


async def case_c5(ctx: Ctx) -> None:
    # GIVEN webhook approved ya procesado (event E)
    order_id = await _new_order(ctx, payment_method=MP)
    total = str(await order_total_pesos(ctx.admin, order_id))
    pid = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, pid, order_id, "approved", total)
    req_id = f"req-{uuid.uuid4()}"
    ts = str(round(dt.datetime.now(dt.UTC).timestamp()))
    check((await send_webhook(ctx.public, payment_id=pid, request_id=req_id, ts=ts)).status_code == 200, "C5: webhook")
    count_after_first = await payment_events_count(order_id)
    check(count_after_first == 1, f"C5: eventos {count_after_first} != 1 tras primer webhook")
    # WHEN replay del mismo webhook (misma firma, mismo data.id)
    resp = await send_webhook(ctx.public, payment_id=pid, request_id=req_id, ts=ts)
    check(resp.status_code == 200, f"C5: replay {resp.status_code} {resp.text[:200]}")
    # THEN sin cambio de estado y sin fila duplicada
    after = await get_payment(ctx.admin, order_id)
    check(after["status"] == "approved" and after["paid"] is True, "C5: estado/paid cambiaron en el replay")
    check(await payment_events_count(order_id) == 1, f"C5: eventos {await payment_events_count(order_id)} != 1 (duplicado)")


async def case_c6(ctx: Ctx) -> None:
    # GIVEN webhook con firma invalida
    order_id = await _new_order(ctx, payment_method=MP)
    pid = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, pid, order_id, "approved", "100")
    # WHEN POST con x-signature corrupta
    resp = await send_webhook(ctx.public, payment_id=pid, signature="ts=1,v1=deadbeef")
    # THEN 401 Invalid signature
    check(resp.status_code == 401, f"C6: {resp.status_code} != 401 {resp.text[:200]}")
    check(resp.json().get("detail") == "Invalid signature", f"C6: detail {resp.json().get('detail')!r}")
    after = await get_payment(ctx.admin, order_id)
    check(after["status"] is None, f"C6: status {after['status']!r} (debe seguir None)")


async def case_c7(ctx: Ctx) -> None:
    # GIVEN pedido sin pago; webhook approved con monto incorrecto
    order_id = await _new_order(ctx, payment_method=MP)
    total = await order_total_pesos(ctx.admin, order_id)
    pid = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, pid, order_id, "approved", str(total + Decimal(100)))
    # WHEN webhook approved (monto != total)
    resp = await send_webhook(ctx.public, payment_id=pid)
    check(resp.status_code == 200, f"C7: webhook {resp.status_code} {resp.text[:200]}")
    # THEN 200, sin cambio de estado, sin pago, sin evento
    after = await get_payment(ctx.admin, order_id)
    check(after["paid"] is False, "C7: paid debe seguir False (discrepancia de monto)")
    check(after["status"] is None, f"C7: status {after['status']!r} (debe seguir None)")
    check(await payment_events_count(order_id) == 0, f"C7: eventos {await payment_events_count(order_id)} != 0")


async def case_c8(ctx: Ctx) -> None:
    # GIVEN webhook cuyo data.id apunta a un pedido inexistente
    pid = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, pid, "order-que-no-existe", "approved", "100")
    # WHEN POST del webhook
    resp = await send_webhook(ctx.public, payment_id=pid)
    # THEN 200 (no 500)
    check(resp.status_code == 200, f"C8: {resp.status_code} != 200 {resp.text[:200]}")


async def case_c9(ctx: Ctx) -> None:
    # GIVEN pedido cash (payment_status pending)
    order_id = await _new_order(ctx)
    # WHEN admin marca pago manual (se pago al retirar)
    resp = await ctx.admin.patch(f"/api/v1/orders/{order_id}/paid")
    check(resp.status_code == 200, f"C9: {resp.status_code} {resp.text[:200]}")
    # THEN paid=True, status=approved, reference=manual, paid_at en DB
    after = await get_payment(ctx.admin, order_id)
    check(after["paid"] is True, "C9: paid debe ser True")
    check(after["status"] == "approved", f"C9: status {after['status']!r} != approved")
    check(after.get("payment_reference") == "manual", f"C9: payment_reference {after.get('payment_reference')!r} != manual")
    check(await order_paid_at(order_id) is not None, "C9: paid_at debe estar set en DB")


async def case_c10(ctx: Ctx) -> None:
    # GIVEN pedido ya paid
    order_id = await _new_order(ctx)
    check((await ctx.admin.patch(f"/api/v1/orders/{order_id}/paid")).status_code == 200, "C10: precondition")
    # WHEN admin marca pago de nuevo
    resp = await ctx.admin.patch(f"/api/v1/orders/{order_id}/paid")
    # THEN 409 order_already_paid
    check(resp.status_code == 409, f"C10: {resp.status_code} != 409 {resp.text[:200]}")
    check(resp.json().get("detail") == "order_already_paid", f"C10: detail {resp.json().get('detail')!r}")


async def case_c11(ctx: Ctx) -> None:
    # GIVEN pedido MP con payment_status pending
    order_id = await _new_order(ctx, payment_method=MP)
    total = str(await order_total_pesos(ctx.admin, order_id))
    pid = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, pid, order_id, "pending", total)
    check((await send_webhook(ctx.public, payment_id=pid)).status_code == 200, "C11: webhook pending")
    # WHEN admin confirma pago manual
    resp = await ctx.admin.patch(f"/api/v1/orders/{order_id}/paid")
    check(resp.status_code == 200, f"C11: {resp.status_code} {resp.text[:200]}")
    # THEN paid + approved
    after = await get_payment(ctx.admin, order_id)
    check(after["paid"] is True, "C11: paid debe ser True")
    check(after["status"] == "approved", f"C11: status {after['status']!r} != approved")


async def case_c12(ctx: Ctx) -> None:
    # GIVEN pedido MP con payment_status rejected
    order_id = await _new_order(ctx, payment_method=MP)
    total = str((await get_order(ctx.admin, order_id))["total"])
    pid = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, pid, order_id, "rejected", total)
    check((await send_webhook(ctx.public, payment_id=pid)).status_code == 200, "C12: webhook rejected")
    # WHEN admin intenta marcar pago manual
    resp = await ctx.admin.patch(f"/api/v1/orders/{order_id}/paid")
    # THEN 409 payment_in_progress
    check(resp.status_code == 409, f"C12: {resp.status_code} != 409 {resp.text[:200]}")
    check(resp.json().get("detail") == "payment_in_progress", f"C12: detail {resp.json().get('detail')!r}")


async def case_c13(ctx: Ctx) -> None:
    # GIVEN pedido CASH (pending); webhook MP valido que lo referencia (anomalia de datos)
    order_id = await _new_order(ctx)
    total = str(await order_total_pesos(ctx.admin, order_id))
    pid = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, pid, order_id, "approved", total)
    # WHEN webhook MP aprobado con firma valida
    resp = await send_webhook(ctx.public, payment_id=pid)
    check(resp.status_code == 200, f"C13: webhook {resp.status_code} {resp.text[:200]}")
    # THEN auditado, sin cambio de estado ni paid (el pasaje cash es manual)
    after = await get_payment(ctx.admin, order_id)
    check(after["status"] == "pending", f"C13: status {after['status']!r} (debe seguir pending)")
    check(after["paid"] is False, "C13: paid debe seguir False")
    check(
        await payment_events_count(order_id) == 1,
        f"C13: eventos {await payment_events_count(order_id)} != 1 (debe auditar)",
    )


# --------------------------------------------------------------------------
# D — pagos por metodo (cash + transfer entran a la maquina; ODD payment-methods)
# --------------------------------------------------------------------------


async def case_d3(ctx: Ctx) -> None:
    # GIVEN cliente autenticado, window abierto
    # WHEN crea pedido por transferencia
    resp = await create_order(ctx.cust_a, ctx.product_id, payment_method=TRANSFER)
    # THEN 200, new, payment_status=pending, paid=False
    check(resp.status_code in (200, 201), f"D3: creacion {resp.status_code} {resp.text[:200]}")
    body = resp.json()
    check(body["status"] == "new", f"D3: status {body['status']!r} != 'new'")
    check(body["payment_status"] == "pending", f"D3: payment_status {body['payment_status']!r} != 'pending'")
    check(body["paid"] is False, "D3: paid debe ser False")


async def case_d4(ctx: Ctx) -> None:
    # GIVEN pedido transferencia (payment_status pending) con comprobante cargado
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    check((await upload_receipt(ctx.cust_a, order_id, RECEIPT_JPEG)).status_code == 201,
          "D4: precondition upload")
    # WHEN admin marca pago manual (recibio la transferencia)
    resp = await ctx.admin.patch(f"/api/v1/orders/{order_id}/paid")
    check(resp.status_code == 200, f"D4: {resp.status_code} {resp.text[:200]}")
    # THEN paid=True, status=approved, reference=manual, paid_at en DB
    # (el endpoint delega en ConfirmReceipt desde O5/S5)
    after = await get_payment(ctx.admin, order_id)
    check(after["paid"] is True, "D4: paid debe ser True")
    check(after["status"] == "approved", f"D4: status {after['status']!r} != approved")
    check(after.get("payment_reference") == "manual", f"D4: payment_reference {after.get('payment_reference')!r} != manual")
    check(await order_paid_at(order_id) is not None, "D4: paid_at debe estar set en DB")


async def case_d7(ctx: Ctx) -> None:
    # GIVEN pedido MP sin eventos (payment_status None)
    order_id = await _new_order(ctx, payment_method=MP)
    # WHEN admin marca pago manual
    resp = await ctx.admin.patch(f"/api/v1/orders/{order_id}/paid")
    check(resp.status_code == 200, f"D7: {resp.status_code} {resp.text[:200]}")
    # THEN paid=True, status=approved (None -> approved via confirm_payment)
    after = await get_payment(ctx.admin, order_id)
    check(after["paid"] is True, "D7: paid debe ser True")
    check(after["status"] == "approved", f"D7: status {after['status']!r} != approved")
    check(after.get("payment_reference") == "manual", f"D7: payment_reference {after.get('payment_reference')!r} != manual")


async def case_d5(ctx: Ctx) -> None:
    # GIVEN pedido transfer (pending); webhook MP valido que lo referencia
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    total = str(await order_total_pesos(ctx.admin, order_id))
    pid = f"mp-{uuid.uuid4().hex[:8]}"
    await register_payment(ctx.mock_base, pid, order_id, "approved", total)
    # WHEN webhook MP aprobado con firma valida
    resp = await send_webhook(ctx.public, payment_id=pid)
    check(resp.status_code == 200, f"D5: webhook {resp.status_code} {resp.text[:200]}")
    # THEN auditado, sin cambio de estado ni paid (transfer no entra por webhook)
    after = await get_payment(ctx.admin, order_id)
    check(after["status"] == "pending", f"D5: status {after['status']!r} (debe seguir pending)")
    check(after["paid"] is False, "D5: paid debe seguir False")
    check(
        await payment_events_count(order_id) == 1,
        f"D5: eventos {await payment_events_count(order_id)} != 1 (debe auditar)",
    )


# --------------------------------------------------------------------------
# R — comprobante de transferencia (ODD transfer_receipt_verification, S8)
# --------------------------------------------------------------------------

# Fixtures de archivo: la validacion del backend es por magic bytes (O5/S3),
# no por extension ni por el Content-Type del multipart.
RECEIPT_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * (1_000_000 - 4)  # JPEG valido, ~1 MB
GIF_FILE = b"GIF89a" + b"\x00" * 100  # GIF: no aceptado
OVERSIZED_FILE = b"%PDF-1.7\n" + b"\x00" * (6 * 1024 * 1024 - 8)  # ~6 MB


async def upload_receipt(
    client: httpx.AsyncClient,
    order_id: str,
    data: bytes,
    *,
    filename: str = "receipt.jpg",
    mime: str = "image/jpeg",
) -> httpx.Response:
    return await client.post(
        f"/api/v1/orders/{order_id}/receipt",
        files={"file": (filename, data, mime)},
    )


async def download_receipt(client: httpx.AsyncClient, order_id: str) -> httpx.Response:
    return await client.get(f"/api/v1/orders/{order_id}/receipt")


async def case_r1(ctx: Ctx) -> None:
    # GIVEN cliente autenticado, window abierto
    # WHEN crea pedido por transferencia
    resp = await create_order(ctx.cust_a, ctx.product_id, payment_method=TRANSFER)
    # THEN 201, payment_status=pending, sin comprobante
    check(resp.status_code in (200, 201), f"R1: creacion {resp.status_code} {resp.text[:200]}")
    body = resp.json()
    check(body["payment_status"] == "pending", f"R1: payment_status {body['payment_status']!r} != 'pending'")
    check(body["receipt_uploaded"] is False, "R1: receipt_uploaded debe ser False")
    check(body["receipt_uploaded_at"] is None, "R1: receipt_uploaded_at debe ser None")


async def case_r2(ctx: Ctx) -> None:
    # GIVEN pedido transferencia sin comprobante
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    # WHEN el cliente sube un JPEG valido (~1 MB)
    resp = await upload_receipt(ctx.cust_a, order_id, RECEIPT_JPEG)
    # THEN 201; comprobante persistido, uploaded_at set; el pago sigue pending
    check(resp.status_code == 201, f"R2: {resp.status_code} {resp.text[:200]}")
    body = resp.json()
    check(body["receipt_uploaded"] is True, "R2: receipt_uploaded debe ser True")
    check(body["receipt_content_type"] == "image/jpeg", f"R2: content_type {body['receipt_content_type']!r} != image/jpeg")
    check(body["receipt_uploaded_at"] is not None, "R2: uploaded_at debe estar set")
    check(body["payment_status"] == "pending", f"R2: pago {body['payment_status']!r} (debe seguir pending)")


async def case_r3(ctx: Ctx) -> None:
    # GIVEN pedido con comprobante
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    check((await upload_receipt(ctx.cust_a, order_id, RECEIPT_JPEG)).status_code == 201, "R3: precondition")
    # WHEN el cliente hace POST de nuevo (cualquier archivo)
    resp = await upload_receipt(ctx.cust_a, order_id, GIF_FILE, filename="otro.jpg")
    # THEN 409 receipt_already_uploaded; el archivo original se conserva
    check(resp.status_code == 409, f"R3: {resp.status_code} != 409 {resp.text[:200]}")
    check(resp.json().get("detail") == "receipt_already_uploaded", f"R3: detail {resp.json().get('detail')!r}")
    dl = await download_receipt(ctx.cust_a, order_id)
    check(dl.status_code == 200, f"R3: download {dl.status_code} (el original debe seguir disponible)")
    check(dl.content == RECEIPT_JPEG, "R3: el comprobante original debe conservarse byte a byte")


async def case_r4(ctx: Ctx) -> None:
    # GIVEN pedido cash
    order_id = await _new_order(ctx, payment_method=CASH)
    # WHEN el cliente intenta subir un comprobante
    resp = await upload_receipt(ctx.cust_a, order_id, RECEIPT_JPEG)
    # THEN 409 receipt_method_not_transfer
    check(resp.status_code == 409, f"R4: {resp.status_code} != 409 {resp.text[:200]}")
    check(resp.json().get("detail") == "receipt_method_not_transfer", f"R4: detail {resp.json().get('detail')!r}")


async def case_r5(ctx: Ctx) -> None:
    # GIVEN pedido transfer sin comprobante
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    # WHEN el cliente sube un GIF con Content-Type: image/jpeg (mentira)
    resp = await upload_receipt(ctx.cust_a, order_id, GIF_FILE, filename="comprobante.jpg")
    # THEN 422 receipt_invalid_type (la validacion es por magic bytes, no por header)
    check(resp.status_code == 422, f"R5: {resp.status_code} != 422 {resp.text[:200]}")
    check(resp.json().get("code") == "receipt_invalid_type", f"R5: code {resp.json().get('code')!r}")


async def case_r6(ctx: Ctx) -> None:
    # GIVEN pedido transfer sin comprobante
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    # WHEN el cliente sube un archivo de ~6 MB
    resp = await upload_receipt(ctx.cust_a, order_id, OVERSIZED_FILE, filename="gigante.pdf", mime="application/pdf")
    # THEN 422 receipt_too_large
    check(resp.status_code == 422, f"R6: {resp.status_code} != 422 {resp.text[:200]}")
    check(resp.json().get("code") == "receipt_too_large", f"R6: code {resp.json().get('code')!r}")


async def case_r7(ctx: Ctx) -> None:
    # GIVEN pedido de otro cliente con comprobante
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    check((await upload_receipt(ctx.cust_a, order_id, RECEIPT_JPEG)).status_code == 201, "R7: precondition")
    # WHEN el cliente B hace POST o GET sobre el comprobante
    post = await upload_receipt(ctx.cust_b, order_id, GIF_FILE)
    get = await download_receipt(ctx.cust_b, order_id)
    # THEN 404 en ambos (anti-sondeo)
    check(post.status_code == 404, f"R7: POST {post.status_code} != 404 {post.text[:200]}")
    check(get.status_code == 404, f"R7: GET {get.status_code} != 404 {get.text[:200]}")


async def case_r8(ctx: Ctx) -> None:
    # GIVEN pedido transfer `new` con comprobante
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    check((await upload_receipt(ctx.cust_a, order_id, RECEIPT_JPEG)).status_code == 201, "R8: precondition")
    # WHEN el admin confirma el comprobante
    resp = await ctx.admin.post(f"/api/v1/orders/{order_id}/receipt/confirm")
    # THEN 200; pago approved, paid=true, paid_at set; pedido preparing
    check(resp.status_code == 200, f"R8: {resp.status_code} {resp.text[:200]}")
    body = resp.json()
    check(body["paid"] is True, "R8: paid debe ser True")
    check(body["status"] == "preparing", f"R8: status {body['status']!r} != preparing")
    check(body["payment_method"] == "transfer", f"R8: payment_method {body['payment_method']!r} != transfer")
    pay = await get_payment(ctx.admin, order_id)
    check(pay["status"] == "approved", f"R8: pago {pay['status']!r} != approved")
    check(await order_paid_at(order_id) is not None, "R8: paid_at debe estar set en DB")


async def case_r9(ctx: Ctx) -> None:
    # GIVEN pedido transfer `new` con comprobante
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    check((await upload_receipt(ctx.cust_a, order_id, RECEIPT_JPEG)).status_code == 201, "R9: precondition")
    # WHEN el admin rechaza el comprobante
    resp = await ctx.admin.post(f"/api/v1/orders/{order_id}/receipt/reject")
    # THEN 200; pago rejected; pedido cancelled
    check(resp.status_code == 200, f"R9: {resp.status_code} {resp.text[:200]}")
    body = resp.json()
    check(body["status"] == "cancelled", f"R9: status {body['status']!r} != cancelled")
    pay = await get_payment(ctx.admin, order_id)
    check(pay["status"] == "rejected", f"R9: pago {pay['status']!r} != rejected")
    check(pay["paid"] is False, "R9: paid debe seguir False (el rechazo nunca paga)")


async def case_r10(ctx: Ctx) -> None:
    # GIVEN pedido con comprobante, ya cancelled (rechazado previamente)
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    check((await upload_receipt(ctx.cust_a, order_id, RECEIPT_JPEG)).status_code == 201, "R10: precondition")
    check((await ctx.admin.post(f"/api/v1/orders/{order_id}/receipt/reject")).status_code == 200, "R10: precondition")
    # WHEN el admin intenta confirmar
    resp = await ctx.admin.post(f"/api/v1/orders/{order_id}/receipt/confirm")
    # THEN 409 (el check de pago precede al de estado de pedido: el pago ya
    # fue rechazado, asi que el error observable es receipt_payment_not_pending)
    check(resp.status_code == 409, f"R10: {resp.status_code} != 409 {resp.text[:200]}")
    check(resp.json().get("detail") == "receipt_payment_not_pending", f"R10: detail {resp.json().get('detail')!r}")


async def case_r11(ctx: Ctx) -> None:
    # GIVEN pedido transfer sin comprobante
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    # WHEN el admin marca pago manual
    resp = await ctx.admin.patch(f"/api/v1/orders/{order_id}/paid")
    # THEN 409 receipt_required
    check(resp.status_code == 409, f"R11: {resp.status_code} != 409 {resp.text[:200]}")
    check(resp.json().get("detail") == "receipt_required", f"R11: detail {resp.json().get('detail')!r}")


async def case_r12(ctx: Ctx) -> None:
    # GIVEN pedido `delivered` con comprobante (confirmado y entregado)
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    check((await upload_receipt(ctx.cust_a, order_id, RECEIPT_JPEG)).status_code == 201, "R12: precondition")
    check((await ctx.admin.post(f"/api/v1/orders/{order_id}/receipt/confirm")).status_code == 200, "R12: precondition")
    check((await patch_status(ctx.admin, order_id, "pending_delivery")).status_code == 200, "R12: precondition")
    check((await patch_status(ctx.admin, order_id, "delivered")).status_code == 200, "R12: precondition")
    # WHEN el admin borra el comprobante
    resp = await ctx.admin.delete(f"/api/v1/orders/{order_id}/receipt")
    # THEN 204; archivo borrado (download 404), payment_method=transfer intacto,
    # entradas en payment_events (uploaded + approved + deleted = 3 eventos)
    check(resp.status_code == 204, f"R12: {resp.status_code} != 204 {resp.text[:200]}")
    dl = await download_receipt(ctx.cust_a, order_id)
    check(dl.status_code == 404, f"R12: post-borrado download {dl.status_code} != 404")
    body = await get_order(ctx.admin, order_id)
    check(body["receipt_uploaded"] is False, "R12: el detalle debe seguir sin comprobante")
    check(body["payment_method"] == "transfer", f"R12: payment_method {body['payment_method']!r} (debe quedar intacto)")
    check(await payment_events_count(order_id) == 3, f"R12: payment_events {await payment_events_count(order_id)} != 3 (uploaded + approved + deleted)")


async def case_r13(ctx: Ctx) -> None:
    # GIVEN pedido `preparing` con comprobante
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    check((await upload_receipt(ctx.cust_a, order_id, RECEIPT_JPEG)).status_code == 201, "R13: precondition")
    check((await patch_status(ctx.admin, order_id, "confirmed")).status_code == 200, "R13: precondition")
    check((await patch_status(ctx.admin, order_id, "preparing")).status_code == 200, "R13: precondition")
    # WHEN el admin intenta borrar el comprobante
    resp = await ctx.admin.delete(f"/api/v1/orders/{order_id}/receipt")
    # THEN 409 receipt_not_deletable
    check(resp.status_code == 409, f"R13: {resp.status_code} != 409 {resp.text[:200]}")
    check(resp.json().get("detail") == "receipt_not_deletable", f"R13: detail {resp.json().get('detail')!r}")


async def case_r14(ctx: Ctx) -> None:
    # GIVEN pedido sin comprobante
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    # WHEN el admin intenta descargar el comprobante
    resp = await download_receipt(ctx.admin, order_id)
    # THEN 404 receipt_not_found
    check(resp.status_code == 404, f"R14: {resp.status_code} != 404 {resp.text[:200]}")
    check(resp.json().get("detail") == "receipt_not_found", f"R14: detail {resp.json().get('detail')!r}")


async def case_r15(ctx: Ctx) -> None:
    # GIVEN pedido con comprobante subido por el cliente
    order_id = await _new_order(ctx, payment_method=TRANSFER)
    check((await upload_receipt(ctx.cust_a, order_id, RECEIPT_JPEG)).status_code == 201, "R15: precondition")
    # WHEN el cliente descarga su comprobante
    resp = await download_receipt(ctx.cust_a, order_id)
    # THEN 200 binario integro, Content-Type real; receipt_viewed_at NO cambia
    check(resp.status_code == 200, f"R15: {resp.status_code} != 200")
    check(resp.content == RECEIPT_JPEG, "R15: los bytes devueltos deben ser el archivo subido")
    check(resp.headers["content-type"].startswith("image/jpeg"), f"R15: content-type {resp.headers['content-type']!r}")
    body = await get_order(ctx.admin, order_id)
    check(body["receipt_viewed_at"] is None, "R15: receipt_viewed_at no debe cambiar (solo el admin lo setea)")


# --------------------------------------------------------------------------
# registro
# --------------------------------------------------------------------------

CaseFn = Callable[[Ctx], Awaitable[None]]

CASES: list[tuple[str, str, CaseFn]] = [
    ("A1", "creacion cash con precio derivado", case_a1),
    ("A2", "order window cerrado", case_a2),
    ("A3", "reintento idempotente mismo pedido", case_a3),
    ("A4", "idempotency key con body distinto", case_a4),
    ("A5", "cliente no transiciona su pedido", case_a5),
    ("A6", "anti-sondeo: pedido ajeno 404", case_a6),
    ("B1", "happy path hasta delivered", case_b1),
    ("B2", "salto new -> delivered rechazado", case_b2),
    ("B3", "confirmed -> cancelled", case_b3),
    ("B4", "preparing -> cancelled", case_b4),
    ("B5", "new -> cancelled (O5: habilitado, sin stock)", case_b5),
    ("B6", "delivered terminal", case_b6),
    ("B7", "cancelled terminal", case_b7),
    ("C1", "webhook approved desde None", case_c1),
    ("C2", "None -> pending -> approved", case_c2),
    ("C3", "rejected -> approved (desbloqueo)", case_c3),
    ("C4", "approved terminal: rejected tardio auditado", case_c4),
    ("C5", "replay de webhook idempotente", case_c5),
    ("C6", "firma invalida 401", case_c6),
    ("C7", "webhook con monto incorrecto no paga", case_c7),
    ("C8", "webhook de pedido inexistente 200", case_c8),
    ("C9", "pago manual cash (pending -> approved)", case_c9),
    ("C10", "pago manual duplicado 409", case_c10),
    ("C11", "pago manual sobre MP pending", case_c11),
    ("C12", "pago manual sobre MP rejected 409", case_c12),
    ("C13", "webhook MP sobre pedido cash: audit, sigue pending", case_c13),
    ("D3", "creacion transfer nace en pending", case_d3),
    ("D4", "pago manual transfer con comprobante (delega a ConfirmReceipt)", case_d4),
    ("D5", "webhook MP sobre pedido transfer: audit, sigue pending", case_d5),
    ("D7", "pago manual MP sin eventos (None -> approved)", case_d7),
    ("R1", "creacion transfer sin comprobante", case_r1),
    ("R2", "upload JPEG valido: 201, pago sigue pending", case_r2),
    ("R3", "doble carga: 409, archivo original intacto", case_r3),
    ("R4", "upload en pedido cash: 409 method_not_transfer", case_r4),
    ("R5", "GIF con Content-Type image/jpeg: 422 invalid_type", case_r5),
    ("R6", "archivo de ~6 MB: 422 too_large", case_r6),
    ("R7", "pedido ajeno: POST/GET 404 (anti-sondeo)", case_r7),
    ("R8", "confirm en new: approved + paid + preparing", case_r8),
    ("R9", "reject en new: rejected + cancelled", case_r9),
    ("R10", "confirm sobre cancelled: 409 not_receivable", case_r10),
    ("R11", "pago manual transfer sin comprobante: 409 receipt_required", case_r11),
    ("R12", "borrado en delivered: 204 + 404 + audit", case_r12),
    ("R13", "borrado en preparing: 409 not_deletable", case_r13),
    ("R14", "download sin comprobante: 404 not_found", case_r14),
    ("R15", "download cliente: 200 integro, viewed_at no cambia", case_r15),
]
