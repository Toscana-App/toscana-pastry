
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable


@runtime_checkable
class CheckoutProvider(Protocol):

    async def create_payment(self, order_id: str, amount: float, currency: str) -> PaymentResult:
        ...

    async def get_payment(self, reference: str) -> PaymentStatusResult:
        ...

    def verify_webhook(
        self, payload: bytes, signature: str | None, request_id: str | None
    ) -> bytes | None:
        ...


class PaymentProviderError(Exception):
    pass


@dataclass(frozen=True)
class PaymentResult:

    reference: str
    checkout_url: str


@dataclass(frozen=True)
class PaymentStatusResult:

    status: str
    order_id: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
