"""Deterministic MockCheckoutProvider (safe mode, C1.3).

Zero SDK imports, zero external I/O. The mock adapter uses deterministic
rules verifiable by test:
    reference  = ``mock_<order_id>``
    status     = derived from the last digit of reference:
                     ``0`` → ``rejected``
                     ``1`` → ``pending``
                     anything else → ``approved``
    signature  = HMAC-SHA256 with a hard-coded test constant.
"""

from __future__ import annotations

import hashlib
import hmac

from domain.checkout_provider import PaymentResult, PaymentStatusResult

_MOCK_HMAC_SECRET = b"toscana-pastry-mock-hmac-secret-for-testing-only"


class MockCheckoutProvider:
    """Deterministic mock implementation of CheckoutProvider.

    Rules (verifiable by test, no randomness/clock/rede):
        reference  = ``mock_<order_id>``
        status     = derived from the last digit of reference:
                         ``0`` → ``rejected``
                         ``1`` → ``pending``
                         anything else → ``approved``
        signature  = HMAC-SHA256 with a hard-coded test constant.
    """

    async def create_payment(self, order_id: str, amount: float, currency: str) -> PaymentResult:
        reference = f"mock_{order_id}"
        # TODO(live): replace with real provider checkout URL.
        return PaymentResult(
            reference=reference,
            checkout_url=f"/checkout/mock/{reference}",
        )

    async def get_payment(self, reference: str) -> PaymentStatusResult:
        tail = reference[-1]
        if tail == "0":
            status = "rejected"
        elif tail == "1":
            status = "pending"
        else:
            status = "approved"
        return PaymentStatusResult(status=status)

    def verify_webhook(self, payload: bytes, signature: str | None) -> bytes | None:
        """Validate the webhook signature.

        Returns the payload bytes when the signature is valid, ``None``
        when it is missing or invalid.
        """
        if signature is None:
            return None

        expected = hmac.new(
            _MOCK_HMAC_SECRET,
            payload,
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(expected, signature):
            return payload
        return None
