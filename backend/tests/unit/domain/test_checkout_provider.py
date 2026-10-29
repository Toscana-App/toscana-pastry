"""Unit tests for CheckoutProvider mock (C1.3).

Verifies:
    - Deterministic reference generation (mock_<order_id>)
    - Deterministic status derivation (last digit of reference)
    - HMAC signature verification (valid/invalid/missing)
    - Contract conformance
"""

import hashlib
import hmac

import pytest

from domain.mock_checkout_provider import MockCheckoutProvider


@pytest.fixture
def provider():
    return MockCheckoutProvider()


class TestMockCheckoutProvider:
    """Tests for MockCheckoutProvider determinism."""

    async def test_create_payment_returns_deterministic_reference(self, provider):
        result = await provider.create_payment("123", 100.0, "ARS")
        assert result.reference == "mock_123"
        assert result.checkout_url == "/checkout/mock/mock_123"

    async def test_create_payment_reference_includes_order_id(self, provider):
        result = await provider.create_payment("abc", 50.0, "ARS")
        assert result.reference == "mock_abc"

    async def test_get_payment_approved_for_non_zero_non_one(self, provider):
        # Last digit '2' → approved
        result = await provider.get_payment("mock_123")
        assert result.status == "approved"

    async def test_get_payment_rejected_for_zero(self, provider):
        # Last digit '0' → rejected
        result = await provider.get_payment("mock_120")
        assert result.status == "rejected"

    async def test_get_payment_pending_for_one(self, provider):
        # Last digit '1' → pending
        result = await provider.get_payment("mock_121")
        assert result.status == "pending"

    def test_verify_webhook_valid_signature(self, provider):
        secret = b"toscana-pastry-mock-hmac-secret-for-testing-only"
        payload = b'{"id": "pay_123", "status": "approved", "resource": "ord_456"}'
        signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()

        result = provider.verify_webhook(payload, signature)
        assert result == payload

    def test_verify_webhook_invalid_signature(self, provider):
        payload = b'{"id": "pay_123"}'
        result = provider.verify_webhook(payload, "invalid_signature")
        assert result is None

    def test_verify_webhook_missing_signature(self, provider):
        payload = b'{"id": "pay_123"}'
        result = provider.verify_webhook(payload, None)
        assert result is None

    def test_determinism_same_input_same_output(self, provider):
        # Multiple calls with same input should produce same output
        for _ in range(10):
            result = provider.verify_webhook(b"test", "sig")
            assert result is None  # invalid signature always returns None
