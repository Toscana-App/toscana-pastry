"""Tests de la maquina de estados de pago (domain/payment_states).

Matriz 5 orígenes (None + 4 valores) × 4 destinos = 20 pares:
9 válidas / 11 inválidas. Contrato de error idéntico al de pedidos.
"""

from __future__ import annotations

import pytest

from domain.payment_states import (
    PAYMENT_STATUS_LABELS,
    InvalidPaymentTransitionError,
    PaymentStatus,
    is_known_payment_status,
    state_for,
    transition,
)

_ALL_TARGETS = (
    PaymentStatus.PENDING,
    PaymentStatus.APPROVED,
    PaymentStatus.REJECTED,
    PaymentStatus.FAILED,
)

_VALID: dict[PaymentStatus | None, frozenset[PaymentStatus]] = {
    None: frozenset(_ALL_TARGETS),
    PaymentStatus.PENDING: frozenset(
        {PaymentStatus.APPROVED, PaymentStatus.REJECTED, PaymentStatus.FAILED}
    ),
    PaymentStatus.REJECTED: frozenset({PaymentStatus.APPROVED}),
    PaymentStatus.FAILED: frozenset({PaymentStatus.APPROVED}),
    PaymentStatus.APPROVED: frozenset(),
}


class TestMatrizCompleta:
    def test_matriz_5x4_completa(self) -> None:
        for current in (None, *_ALL_TARGETS):
            for target in _ALL_TARGETS:
                if target in _VALID[current]:
                    assert transition(current, target) is target
                else:
                    with pytest.raises(InvalidPaymentTransitionError):
                        transition(current, target)

    def test_cantidad_validas_e_invalidas(self) -> None:
        validas = sum(len(targets) for targets in _VALID.values())
        total = len(_VALID) * len(_ALL_TARGETS)
        assert validas == 9
        assert total - validas == 11

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            (PaymentStatus.PENDING, PaymentStatus.PENDING),
            (PaymentStatus.REJECTED, PaymentStatus.PENDING),
            (PaymentStatus.REJECTED, PaymentStatus.REJECTED),
            (PaymentStatus.REJECTED, PaymentStatus.FAILED),
            (PaymentStatus.FAILED, PaymentStatus.PENDING),
            (PaymentStatus.FAILED, PaymentStatus.REJECTED),
            (PaymentStatus.FAILED, PaymentStatus.FAILED),
            (PaymentStatus.APPROVED, PaymentStatus.PENDING),
            (PaymentStatus.APPROVED, PaymentStatus.APPROVED),
            (PaymentStatus.APPROVED, PaymentStatus.REJECTED),
            (PaymentStatus.APPROVED, PaymentStatus.FAILED),
        ],
    )
    def test_invalida_mensaje_y_atributos(
        self, current: PaymentStatus, target: PaymentStatus
    ) -> None:
        with pytest.raises(InvalidPaymentTransitionError) as excinfo:
            transition(current, target)
        assert str(excinfo.value) == (
            f"Transicion invalida: {current.value} -> {target.value}"
        )
        assert excinfo.value.current == current.value
        assert excinfo.value.target == target.value


class TestOrigenNulo:
    def test_none_hacia_cualquier_valor(self) -> None:
        for target in _ALL_TARGETS:
            assert transition(None, target) is target

    def test_none_acepta_strings(self) -> None:
        assert transition(None, "pending") is PaymentStatus.PENDING


class TestOrigenDestinoDesconocidos:
    def test_origen_desconocido_levanta(self) -> None:
        with pytest.raises(InvalidPaymentTransitionError) as excinfo:
            transition("weird", PaymentStatus.PENDING)
        assert str(excinfo.value) == "Transicion invalida: weird -> pending"

    def test_destino_desconocido_levanta(self) -> None:
        with pytest.raises(InvalidPaymentTransitionError) as excinfo:
            transition(PaymentStatus.PENDING, "weird")
        assert str(excinfo.value) == (
            "Transicion invalida: pending -> weird"
        )

    def test_estado_desconocido_state_for_none(self) -> None:
        assert state_for("weird") is None
        assert not is_known_payment_status("weird")
        assert is_known_payment_status("pending")


class TestTerminalesYLabels:
    def test_approved_es_terminal(self) -> None:
        state = state_for(PaymentStatus.APPROVED)
        assert state is not None
        assert state.transitions == {}
        assert state.can_transition_to(PaymentStatus.PENDING) is False

    def test_labels_espanol(self) -> None:
        assert PAYMENT_STATUS_LABELS == {
            "pending": "Pagando",
            "approved": "Aprobado",
            "rejected": "Rechazado",
            "failed": "Fallido",
        }

    def test_enum_cuatro_valores_ingles(self) -> None:
        assert [s.value for s in PaymentStatus] == [
            "pending",
            "approved",
            "rejected",
            "failed",
        ]
