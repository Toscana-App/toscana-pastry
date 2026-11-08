
from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
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
SIGNATURE_TOLERANCE_SECONDS = 5 * 60

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

    def __init__(
        self,
        access_token: str,
        webhook_secret: str,
        notification_url: str | None = None,
        back_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._clock = clock
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
        if self._access_token.startswith("TEST-"):
            checkout_url = data.get("sandbox_init_point") or data["init_point"]
        else:
            checkout_url = data["init_point"]
        return PaymentResult(reference=str(data["id"]), checkout_url=checkout_url)

    async def get_payment(self, reference: str) -> PaymentStatusResult:
        data = await self._request("GET", f"/v1/payments/{reference}")
        status = _STATUS_MAP.get(str(data.get("status")), "pending")
        order_id = data.get("external_reference") or None
        return PaymentStatusResult(
            status=status,
            order_id=order_id,
            amount=_parse_amount(data.get("transaction_amount")),
            currency=data.get("currency_id") or None,
        )

    def verify_webhook(
        self, payload: bytes, signature: str | None, request_id: str | None
    ) -> bytes | None:
        try:
            data_id = str(json.loads(payload)["data"]["id"])
        except (ValueError, KeyError, TypeError):
            return None
        if verify_mp_signature(
            self._webhook_secret, data_id, request_id, signature, now=self._clock()
        ):
            return payload
        return None


def _parse_amount(raw: Any) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def verify_mp_signature(
    secret: str,
    data_id: str,
    request_id: str | None,
    x_signature: str | None,
    now: float | None = None,
) -> bool:
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
    if not hmac.compare_digest(expected.encode(), v1.encode("utf-8", "surrogateescape")):
        return False
    try:
        signed_at = float(ts)
    except ValueError:
        return False
    if signed_at > 1e11:
        signed_at /= 1000
    current = time.time() if now is None else now
    return abs(current - signed_at) <= SIGNATURE_TOLERANCE_SECONDS
