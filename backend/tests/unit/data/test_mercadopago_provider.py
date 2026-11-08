
from __future__ import annotations

import hashlib
import hmac
import json
import time

import httpx
import pytest

from domain.checkout_provider import CheckoutProvider, PaymentProviderError
from data.payments.mercadopago import MercadoPagoCheckoutProvider

TOKEN = "APP_USR-test-token"
SECRET = "webhook-secret"


def _provider(handler, **kwargs) -> MercadoPagoCheckoutProvider:
    return MercadoPagoCheckoutProvider(
        access_token=kwargs.pop("access_token", TOKEN),
        webhook_secret=SECRET,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def test_implements_checkout_provider_contract() -> None:
    assert isinstance(_provider(lambda r: httpx.Response(200)), CheckoutProvider)




async def test_create_payment_creates_checkout_pro_preference() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            201,
            json={
                "id": "pref-123",
                "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref-123",
                "sandbox_init_point": "https://sandbox.mercadopago.com.ar/checkout/v1/redirect?pref_id=pref-123",
            },
        )

    provider = _provider(
        handler,
        notification_url="https://api.example.com/api/v1/webhooks/mercadopago",
        back_url="https://shop.example.com/checkout/result",
    )
    result = await provider.create_payment("order-1", 1500.5, "ARS")

    assert result.reference == "pref-123"
    assert result.checkout_url.startswith("https://www.mercadopago.com.ar/")
    request = seen[0]
    assert request.method == "POST"
    assert request.url == "https://api.mercadopago.com/checkout/preferences"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    body = json.loads(request.content)
    assert body["external_reference"] == "order-1"
    assert body["items"] == [
        {
            "id": "order-1",
            "title": "Toscana Pastry order",
            "quantity": 1,
            "unit_price": 1500.5,
            "currency_id": "ARS",
        }
    ]
    assert body["notification_url"] == "https://api.example.com/api/v1/webhooks/mercadopago"
    assert body["back_urls"] == {
        "success": "https://shop.example.com/checkout/result",
        "pending": "https://shop.example.com/checkout/result",
        "failure": "https://shop.example.com/checkout/result",
    }
    assert body["auto_return"] == "approved"


async def test_create_payment_omits_optional_urls_when_not_configured() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(201, json={"id": "p", "init_point": "https://x"})

    await _provider(handler).create_payment("order-1", 10.0, "ARS")

    assert "notification_url" not in seen[0]
    assert "back_urls" not in seen[0]
    assert "auto_return" not in seen[0]


async def test_test_token_uses_sandbox_checkout_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={"id": "p", "init_point": "https://prod", "sandbox_init_point": "https://sandbox"},
        )

    result = await _provider(handler, access_token="TEST-123").create_payment("o", 1.0, "ARS")

    assert result.checkout_url == "https://sandbox"


async def test_create_payment_http_error_raises_provider_error() -> None:
    provider = _provider(lambda r: httpx.Response(401, json={"message": "invalid token"}))

    with pytest.raises(PaymentProviderError):
        await provider.create_payment("order-1", 10.0, "ARS")




@pytest.mark.parametrize(
    ("mp_status", "expected"),
    [
        ("approved", "approved"),
        ("pending", "pending"),
        ("in_process", "pending"),
        ("authorized", "pending"),
        ("in_mediation", "pending"),
        ("rejected", "rejected"),
        ("cancelled", "failed"),
        ("refunded", "failed"),
        ("charged_back", "failed"),
    ],
)
async def test_get_payment_maps_status_and_order(mp_status: str, expected: str) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"id": 987, "status": mp_status, "external_reference": "order-1"}
        )

    result = await _provider(handler).get_payment("987")

    assert result.status == expected
    assert result.order_id == "order-1"
    assert seen[0].url == "https://api.mercadopago.com/v1/payments/987"
    assert seen[0].headers["Authorization"] == f"Bearer {TOKEN}"


async def test_get_payment_http_error_raises_provider_error() -> None:
    provider = _provider(lambda r: httpx.Response(404, json={"message": "not found"}))

    with pytest.raises(PaymentProviderError):
        await provider.get_payment("987")


async def test_network_error_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(PaymentProviderError):
        await _provider(handler).get_payment("987")




def _signed(data_id: str, request_id: str, ts: str | None = None) -> str:
    ts = ts or str(int(time.time()))
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def test_verify_webhook_returns_payload_for_valid_signature() -> None:
    payload = json.dumps({"type": "payment", "data": {"id": "987"}}).encode()
    provider = _provider(lambda r: httpx.Response(200))

    assert provider.verify_webhook(payload, _signed("987", "req-1"), "req-1") == payload


def test_verify_webhook_rejects_bad_signature_or_body() -> None:
    provider = _provider(lambda r: httpx.Response(200))
    good = json.dumps({"type": "payment", "data": {"id": "987"}}).encode()

    assert provider.verify_webhook(good, _signed("111", "req-1"), "req-1") is None
    assert provider.verify_webhook(good, None, "req-1") is None
    assert provider.verify_webhook(b"not json", _signed("987", "req-1"), "req-1") is None
    assert provider.verify_webhook(b"{}", _signed("987", "req-1"), "req-1") is None
