import uuid

import pytest

from domain.delivery import (
    DELIVERY_STATE_MESSAGES,
    DeliveryLink,
    DeliveryLinkState,
    delivery_url,
    new_delivery_token,
    normalize_token,
    public_view,
    revocation_reason,
    state_for_link,
)


def _link(
    *,
    order_status: str = "confirmed",
    revoked_at=None,
    revoked_reason: str | None = None,
    order_code: str = "#00001",
) -> DeliveryLink:
    return DeliveryLink(
        token="2f1c9a1e-3b7d-4a55-9f42-6a0e4b1c2d3e",
        order_id="o1",
        order_code=order_code,
        order_status=order_status,
        created_at=None,
        revoked_at=revoked_at,
        revoked_reason=revoked_reason,
    )


def test_new_delivery_token_is_uuid4_and_unique():
    first = new_delivery_token()
    second = new_delivery_token()

    assert uuid.UUID(first).version == 4
    assert first != second


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "123",
        "no-es-uuid",
        "../orders/1",
        str(uuid.uuid1()),
        "2f1c9a1e-3b7d-4a55-9f42-6a0e4b1c2d3e00",
    ],
)
def test_normalize_token_rejects_anything_but_uuid4(raw):
    assert normalize_token(raw) is None


def test_normalize_token_accepts_uuid4_in_canonical_form():
    token = new_delivery_token()

    assert normalize_token(token) == token
    assert normalize_token("  " + token + "  ") == token


def test_normalize_token_lowercases_hexadecimal_form():
    token = new_delivery_token().upper()

    assert normalize_token(token) == token.lower()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("delivered", "delivered"),
        ("cancelled", "cancelled"),
        ("new", None),
        ("confirmed", None),
        ("preparing", None),
        ("pending_delivery", None),
        ("desconocido", None),
    ],
)
def test_revocation_reason_only_for_terminal_states(status, expected):
    assert revocation_reason(status) == expected


def test_state_is_active_when_link_alive_and_order_in_progress():
    assert state_for_link(_link()) is DeliveryLinkState.ACTIVE


def test_state_follows_order_status_even_without_materialized_revocation():
    assert state_for_link(_link(order_status="delivered")) is DeliveryLinkState.DELIVERED
    assert state_for_link(_link(order_status="cancelled")) is DeliveryLinkState.CANCELLED


def test_state_is_expired_for_revoked_link_on_active_order():
    link = _link(revoked_at="2026-11-26T10:00:00Z", revoked_reason="delivered")

    assert state_for_link(link) is DeliveryLinkState.EXPIRED


def test_delivered_view_shows_the_exact_message_and_code():
    view = public_view(_link(order_status="delivered"))

    assert view.state is DeliveryLinkState.DELIVERED
    assert view.message == "Su pedido ha sido entregado"
    assert view.order_code == "#00001"
    assert view.status_label == "Entregado"


def test_active_view_shows_status_label():
    view = public_view(_link(order_status="pending_delivery"))

    assert view.state is DeliveryLinkState.ACTIVE
    assert view.status == "pending_delivery"
    assert view.status_label == "Pendiente entrega"


def test_expired_view_hides_order_code():
    view = public_view(
        _link(revoked_at="2026-11-26T10:00:00Z", revoked_reason="delivered")
    )

    assert view.state is DeliveryLinkState.EXPIRED
    assert view.order_code == ""
    assert view.status == ""


def test_every_state_has_a_message():
    assert set(DELIVERY_STATE_MESSAGES) == set(DeliveryLinkState)


def test_delivery_url_normalizes_trailing_slash():
    token = "2f1c9a1e-3b7d-4a55-9f42-6a0e4b1c2d3e"

    assert (
        delivery_url("https://app.example.com/", token)
        == f"https://app.example.com/entrega/{token}"
    )
    assert (
        delivery_url("https://app.example.com", token)
        == f"https://app.example.com/entrega/{token}"
    )
