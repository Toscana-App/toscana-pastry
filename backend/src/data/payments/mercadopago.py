"""Mercado Pago adapter (Checkout Pro) for the CheckoutProvider contract.

Talks to the Mercado Pago REST API with async httpx (no SDK: the official
Python SDK is synchronous).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx

from domain.checkout_provider import (
    PaymentProviderError,
    PaymentResult,
    PaymentStatusResult,
)

MP_API_URL = "https://api.mercadopago.com"
_HTTP_TIMEOUT_SECONDS = 10.0
_ITEM_TITLE = "Toscana Pastry order"

# Mercado Pago payment status -> CheckoutProvider status.
_STATUS_MAP = {
    "approved": "approved",
    "pending": "pending",
    "in_process": "pending",
    "authorized": "pending",
    "in_mediation": "pending",
    "rejected": "rejected",
    "cancelled": "failed",
    "refunded": "failed",
    "charged_back": "failed",
}


class MercadoPagoCheckoutProvider:
    """CheckoutProvider backed by Mercado Pago Checkout Pro."""

    def __init__(
        self,
        access_token: str,
        webhook_secret: str,
        notification_url: str | None = None,
        back_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._access_token = access_token
        self._webhook_secret = webhook_secret
        self._notification_url = notification_url
        self._back_url = back_url
        self._transport = transport

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=MP_API_URL,
                timeout=_HTTP_TIMEOUT_SECONDS,
                transport=self._transport,
                headers={"Authorization": f"Bearer {self._access_token}"},
            ) as client:
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as err:
            raise PaymentProviderError(f"Mercado Pago {method} {path} failed") from err

    async def create_payment(self, order_id: str, amount: float, currency: str) -> PaymentResult:
        body: dict[str, Any] = {
            "items": [
                {
                    "id": order_id,
                    "title": _ITEM_TITLE,
                    "quantity": 1,
                    "unit_price": amount,
                    "currency_id": currency,
                }
            ],
            "external_reference": order_id,
        }
        if self._notification_url:
            body["notification_url"] = self._notification_url
        if self._back_url:
            body["back_urls"] = {
                "success": self._back_url,
                "pending": self._back_url,
                "failure": self._back_url,
            }
            body["auto_return"] = "approved"
        data = await self._request("POST", "/checkout/preferences", json=body)
        # ponytail: TEST- tokens only work on the sandbox checkout; APP_USR-
        # tokens (prod or test-user) use init_point.
        if self._access_token.startswith("TEST-"):
            checkout_url = data.get("sandbox_init_point") or data["init_point"]
        else:
            checkout_url = data["init_point"]
        return PaymentResult(reference=str(data["id"]), checkout_url=checkout_url)

    async def get_payment(self, reference: str) -> PaymentStatusResult:
        data = await self._request("GET", f"/v1/payments/{reference}")
        # Unknown statuses stay non-terminal: they can never mark an order paid.
        status = _STATUS_MAP.get(str(data.get("status")), "pending")
        order_id = data.get("external_reference") or None
        return PaymentStatusResult(status=status, order_id=order_id)

    def verify_webhook(
        self, payload: bytes, signature: str | None, request_id: str | None
    ) -> bytes | None:
        try:
            data_id = str(json.loads(payload)["data"]["id"])
        except (ValueError, KeyError, TypeError):
            return None
        if verify_mp_signature(self._webhook_secret, data_id, request_id, signature):
            return payload
        return None


def verify_mp_signature(
    secret: str,
    data_id: str,
    request_id: str | None,
    x_signature: str | None,
) -> bool:
    """Validate the ``x-signature`` header of a Mercado Pago webhook.

    ``x-signature`` is ``ts=<ts>,v1=<hex>`` where ``v1`` is the HMAC-SHA256
    of ``id:<data.id>;request-id:<x-request-id>;ts:<ts>;`` keyed with the
    webhook secret.
    """
    if not secret or not data_id or not request_id or not x_signature:
        return False
    parts: dict[str, str] = {}
    for chunk in x_signature.split(","):
        key, sep, value = chunk.partition("=")
        if sep:
            parts[key.strip()] = value.strip()
    ts = parts.get("ts")
    v1 = parts.get("v1")
    if not ts or not v1:
        return False
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    # Compare bytes: compare_digest raises TypeError on non-ASCII str.
    return hmac.compare_digest(expected.encode(), v1.encode("utf-8", "surrogateescape"))
