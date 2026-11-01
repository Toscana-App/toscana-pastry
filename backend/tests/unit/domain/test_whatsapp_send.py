"""Unit tests for the WhatsAppSend domain entity + state machine (RF-P10-07/08, C7).

Covers:
- Invariants (provider, status, phone/message non-blank).
- State machine: sent -> delivered -> read by priority; out-of-order events
  ignored; idempotent same-status updates; failed is terminal.
- Resend rules: only failed + business_api; reset clears all trace fields.
- read_rate helper (0/0 -> 0.0).
"""

import datetime

import pytest

from domain.whatsapp_send import (
    WhatsAppSend,
    apply_status,
    can_resend,
    read_rate,
    reset_for_resend,
)

NOW = datetime.datetime(2026, 10, 26, 12, 0, 0, tzinfo=datetime.UTC)


def make_send(**overrides) -> WhatsAppSend:
    base = {
        "id": "send-1",
        "provider": "business_api",
        "phone": "+5491122334455",
        "message": "Hola, tu presupuesto",
        "reference_kind": "order",
        "reference_id": "order-1",
        "sent_at": NOW,
    }
    base.update(overrides)
    return WhatsAppSend(**base)  # type: ignore[arg-type]


# ─── Invariants ─────────────────────────────────────────────────────────


def test_defaults_to_sent():
    send = make_send()
    assert send.status == "sent"
    assert send.failed_reason is None
    assert send.delivered_at is None
    assert send.read_at is None


def test_invalid_provider_rejected():
    with pytest.raises(ValueError):
        make_send(provider="telegram")


def test_invalid_status_rejected():
    with pytest.raises(ValueError):
        make_send(status="pending")


def test_blank_phone_rejected():
    with pytest.raises(ValueError):
        make_send(phone="   ")


def test_blank_message_rejected():
    with pytest.raises(ValueError):
        make_send(message="")


def test_blank_reference_id_rejected():
    with pytest.raises(ValueError):
        make_send(reference_id="  ")


# ─── State machine: transitions ─────────────────────────────────────────


def test_sent_to_delivered_sets_delivered_at():
    send = make_send()
    updated = apply_status(send, "delivered", now=NOW)
    assert updated.status == "delivered"
    assert updated.delivered_at == NOW
    assert updated.read_at is None


def test_delivered_to_read_sets_read_at_and_backfills_delivered_at():
    send = make_send(status="delivered", delivered_at=NOW)
    updated = apply_status(send, "read", now=NOW)
    assert updated.status == "read"
    assert updated.read_at == NOW
    assert updated.delivered_at == NOW


def test_sent_to_read_backfills_delivered_at():
    """read llega sin delivered previo: backfill para no perder trazabilidad."""
    send = make_send()
    updated = apply_status(send, "read", now=NOW)
    assert updated.status == "read"
    assert updated.delivered_at == NOW
    assert updated.read_at == NOW


def test_read_to_delivered_ignored_out_of_order():
    """delivered llega despues de read: prioridad, no regresa."""
    send = make_send(status="read", delivered_at=NOW, read_at=NOW)
    updated = apply_status(send, "delivered", now=NOW)
    assert updated is send


def test_sent_to_delivered_ignored_out_of_order():
    send = make_send(status="delivered", delivered_at=NOW)
    updated = apply_status(send, "sent", now=NOW)
    assert updated is send


def test_same_status_is_idempotent():
    send = make_send(status="delivered", delivered_at=NOW)
    updated = apply_status(send, "delivered", now=NOW)
    assert updated is send


def test_failed_sets_status_and_reason():
    send = make_send()
    updated = apply_status(send, "failed", failed_reason="undeliverable", now=NOW)
    assert updated.status == "failed"
    assert updated.failed_reason == "undeliverable"


def test_failed_is_terminal():
    """Una vez failed, eventos de entrega/lectura no lo reviven."""
    send = make_send(status="failed", failed_reason="expired")
    assert apply_status(send, "delivered", now=NOW) is send
    assert apply_status(send, "read", now=NOW) is send
    assert apply_status(send, "sent", now=NOW) is send


def test_failed_to_failed_keeps_original_reason():
    send = make_send(status="failed", failed_reason="expired")
    updated = apply_status(send, "failed", failed_reason="retry", now=NOW)
    assert updated is send


# ─── Resend rules ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("provider", "status", "expected"),
    [
        ("business_api", "failed", True),
        ("business_api", "sent", False),
        ("business_api", "delivered", False),
        ("business_api", "read", False),
        ("wa_me", "failed", False),
        ("wa_me", "sent", False),
    ],
)
def test_can_resend_matrix(provider, status, expected):
    send = make_send(provider=provider, status=status)
    if status == "failed":
        send = make_send(provider=provider, status=status, failed_reason="x")
    assert can_resend(send) is expected


def test_reset_for_resend_clears_all_trace_fields():
    send = make_send(
        status="failed",
        failed_reason="expired",
        delivered_at=NOW,
        read_at=None,
        message_id="MOCK_OLD",
    )
    updated = reset_for_resend(send, new_message_id="MOCK_NEW", now=NOW)
    assert updated.status == "sent"
    assert updated.failed_reason is None
    assert updated.delivered_at is None
    assert updated.read_at is None
    assert updated.message_id == "MOCK_NEW"
    assert updated.sent_at == NOW


def test_reset_for_resend_requires_retriable():
    send = make_send(status="sent")
    with pytest.raises(ValueError):
        reset_for_resend(send, new_message_id="x", now=NOW)


# ─── read_rate ──────────────────────────────────────────────────────────


def test_read_rate_normal():
    assert read_rate(total=10, read=3) == pytest.approx(0.3)


def test_read_rate_zero_total():
    assert read_rate(total=0, read=0) == 0.0
