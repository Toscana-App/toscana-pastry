"""Provider-agnostic contract for checkout payment flows (RF-P6-13, C1.3).

Zero SDK imports, zero external I/O. Adapters (Mercado Pago) live in the
``data`` layer, keeping the domain free of provider-specific code.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable


@runtime_checkable
class CheckoutProvider(Protocol):
    """Provider-agnostic checkout contract.

    Methods:
        create_payment: initiate a payment for an order.
        get_payment: poll the current status of a payment by reference.
        verify_webhook: validate a webhook payload signature and return the
            verified payload (or None if the signature is invalid).

    I/O failures are raised as ``PaymentProviderError``.
    """

    async def create_payment(self, order_id: str, amount: float, currency: str) -> PaymentResult:
        """Initiate a checkout payment for the given order."""
        ...  # type: ignore[misc]

    async def get_payment(self, reference: str) -> PaymentStatusResult:
        """Poll the current status of a payment by reference."""
        ...  # type: ignore[misc]

    def verify_webhook(
        self, payload: bytes, signature: str | None, request_id: str | None
    ) -> bytes | None:
        """Validate a webhook payload signature and return the verified payload."""
        ...  # type: ignore[misc]


class PaymentProviderError(Exception):
    """The payment provider could not be reached or rejected the request."""


@dataclass(frozen=True)
class PaymentResult:
    """Result of initiating a checkout payment."""

    reference: str
    checkout_url: str


@dataclass(frozen=True)
class PaymentStatusResult:
    """Status of a payment by reference."""

    status: str  # "pending" | "approved" | "rejected" | "failed"
    order_id: str | None = None
    amount: Decimal | None = None  # provider-reported transaction amount
    currency: str | None = None  # ISO currency code, e.g. "ARS"
