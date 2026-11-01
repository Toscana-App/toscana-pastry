"""Unit tests for the order window domain (RF-P5-07, C6).

Ventana de pedidos: open (default true), reopens_at (requerido al cerrar),
message (<= 200 chars). Cerrada → 409 order_window_closed en la creación
de pedidos del portal.
"""

import datetime

import pytest
from domain.order_window import MAX_WINDOW_MESSAGE, OrderWindow


class TestOrderWindow:
    def test_default_is_open(self):
        window = OrderWindow()
        assert window.open is True
        assert window.reopens_at is None
        assert window.message == ""

    def test_closed_requires_reopens_at(self):
        with pytest.raises(ValueError):
            OrderWindow(open=False, reopens_at=None)

    def test_closed_with_reopens_at_is_valid(self):
        window = OrderWindow(
            open=False,
            reopens_at=datetime.datetime(2026, 11, 1, 9, 0, 0),
            message="Cerrado por vacaciones",
        )
        assert window.open is False
        assert window.message == "Cerrado por vacaciones"

    def test_message_max_length(self):
        assert MAX_WINDOW_MESSAGE == 200
        with pytest.raises(ValueError):
            OrderWindow(
                open=False,
                reopens_at=datetime.datetime(2026, 11, 1),
                message="x" * 201,
            )

    def test_message_at_limit_is_valid(self):
        window = OrderWindow(
            open=False,
            reopens_at=datetime.datetime(2026, 11, 1),
            message="x" * 200,
        )
        assert len(window.message) == 200

    def test_mixed_naive_aware_reopens_at_is_normalized(self):
        window = OrderWindow(
            open=False,
            reopens_at=datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC),
        )
        assert window.reopens_at.tzinfo is None
        assert window.reopens_at.year == 2026
