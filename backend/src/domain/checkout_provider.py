"""Provider-agnostic contract for checkout payment flows (RF-P6-13, C1.3).

Safe mode: zero SDK imports, zero external I/O. The mock adapter lives in
``domain.mock_checkout_provider`` to keep the domain layer free of
MercadoPago-specific code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class CheckoutProvider(Protocol):
    """Provider-agnostic checkout contract.

    Methods:
        create_payment: initiate a payment for an order.
        get_payment: poll the current status of a payment by reference.
        verify_webhook: validate a webhook payload signature and return the
            verified payload (or None if the signature is invalid).
    """

    async def create_payment(self, order_id: str, amount: float, currency: str) -> PaymentResult:
        """Initiate a checkout payment for the given order."""
        ...  # type: ignore[misc]

    async def get_payment(self, reference: str) -> PaymentStatusResult:
        """Poll the current status of a payment by reference."""
        ...  # type: ignore[misc]

    def verify_webhook(self, payload: bytes, signature: str | None) -> bytes | None:
        """Validate a webhook payload signature and return the verified payload."""
        ...  # type: ignore[misc]


@dataclass(frozen=True)
class PaymentResult:
    """Result of initiating a checkout payment."""

    reference: str
    checkout_url: str


@dataclass(frozen=True)
class PaymentStatusResult:
    """Status of a payment by reference."""

    status: str  # "pending" | "approved" | "rejected" | "failed"
