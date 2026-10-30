"""Mercado Pago adapter (Checkout Pro) for the CheckoutProvider contract.

Talks to the Mercado Pago REST API with async httpx (no SDK: the official
Python SDK is synchronous).
"""

from __future__ import annotations

import hashlib
import hmac


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
    return hmac.compare_digest(expected, v1)
