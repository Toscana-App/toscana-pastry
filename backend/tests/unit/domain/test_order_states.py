"""T1 — Máquina de estados de pedidos (domain/order_states.py).

Contrato: matriz completa 6x6 con mensajes de error exactos, terminales
sin salidas y labels derivados de la máquina.

Máquina (valores persistentes en inglés):
    new -> confirmed -> preparing -> pending_delivery -> delivered
    new -> cancelled           (O5/S4: sin efecto de stock)
    confirmed -> cancelled
    preparing -> cancelled
"""

import pytest

from domain.order_states import (
    ORDER_STATUS_LABELS,
    InvalidStatusTransitionError,
    OrderStatus,
    state_for,
    transition,
)

ALL_STATUSES = list(OrderStatus)
VALID_TRANSITIONS = {
    ("new", "confirmed"),
    ("new", "cancelled"),
    ("confirmed", "preparing"),
    ("confirmed", "cancelled"),
    ("preparing", "pending_delivery"),
    ("preparing", "cancelled"),
    ("pending_delivery", "delivered"),
}
TERMINAL_STATUSES = (OrderStatus.DELIVERED, OrderStatus.CANCELLED)


class TestMatrizCompleta:
    @pytest.mark.parametrize(
        ("current", "target"),
        [(current, target) for current in ALL_STATUSES for target in ALL_STATUSES],
    )
    def test_transicion_valida(self, current: OrderStatus, target: OrderStatus):
        if (current.value, target.value) in VALID_TRANSITIONS:
            assert transition(current, target) == target

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            (current, target)
            for current in ALL_STATUSES
            for target in ALL_STATUSES
            if (current.value, target.value) not in VALID_TRANSITIONS
        ],
    )
    def test_transicion_invalida_mensaje_exacto(
        self, current: OrderStatus, target: OrderStatus
    ):
        with pytest.raises(InvalidStatusTransitionError) as exc:
            transition(current, target)
        assert str(exc.value) == (
            f"Transicion invalida: {current.value} -> {target.value}"
        )

    def test_contador_de_transiciones(self):
        # 6x6 = 36 pares: 7 válidos (O5/S4 sumó new -> cancelled) y 29 inválidos.
        assert len(ALL_STATUSES) == 6
        assert len(VALID_TRANSITIONS) == 7
        assert 36 - len(VALID_TRANSITIONS) == 29

    def test_current_desconocido(self):
        with pytest.raises(InvalidStatusTransitionError) as exc:
            transition("perdido", OrderStatus.CONFIRMED)
        assert str(exc.value) == "Transicion invalida: perdido -> confirmed"

    def test_target_desconocido(self):
        with pytest.raises(InvalidStatusTransitionError) as exc:
            transition(OrderStatus.NEW, "hecho")
        assert str(exc.value) == "Transicion invalida: new -> hecho"

    def test_acepta_valores_str(self):
        assert transition("new", "confirmed") == OrderStatus.CONFIRMED
        assert transition("new", "confirmed").value == "confirmed"


class TestEstadosTerminales:
    @pytest.mark.parametrize("terminal", TERMINAL_STATUSES)
    @pytest.mark.parametrize("target", ALL_STATUSES)
    def test_no_tienen_salidas(self, terminal: OrderStatus, target: OrderStatus):
        with pytest.raises(InvalidStatusTransitionError) as exc:
            transition(terminal, target)
        assert str(exc.value) == (
            f"Transicion invalida: {terminal.value} -> {target.value}"
        )


class TestLabelsDerivados:
    def test_cubre_exactamente_los_seis_estados(self):
        assert set(ORDER_STATUS_LABELS) == {status.value for status in ALL_STATUSES}

    def test_labels_esperados(self):
        assert ORDER_STATUS_LABELS == {
            "new": "Nuevo",
            "confirmed": "Confirmado",
            "preparing": "Pendiente preparación",
            "pending_delivery": "Pendiente entrega",
            "delivered": "Entregado",
            "cancelled": "Cancelado",
        }


class TestStateFor:
    def test_por_valor_str(self):
        state = state_for("preparing")
        assert state is not None
        assert state.status is OrderStatus.PREPARING
        assert state.label == "Pendiente preparación"

    def test_por_member(self):
        state = state_for(OrderStatus.DELIVERED)
        assert state is not None
        assert state.label == "Entregado"

    def test_desconocido_da_none(self):
        assert state_for("no-existe") is None
