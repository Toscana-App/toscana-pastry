"""Maquina de estados de pago (GoF State) — unica dueña del flujo de pagos.

Valores persistentes (API, frontend, BD), siempre en inglés snake_case:
    pending / approved / rejected / failed

Semantica: `approved` es terminal (paid es monotónico); un intento
rechazado o fallido solo lo desbloquea un `approved`. El origen `None`
(sin evento de provider registrado aún) transiciona a cualquier valor.

Este modulo es la unica fuente de la maquina: `PaymentStatus`, los estados
concretos con sus transiciones declarativas, la transicion validada y
las etiquetas derivadas de los propios estados.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Final


class PaymentStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class InvalidPaymentTransitionError(ValueError):
    """Transicion de pago no permitida por la maquina (mismo contrato que pedidos)."""

    def __init__(self, current: str, target: str):
        self.current = current
        self.target = target
        super().__init__(f"Transicion invalida: {current} -> {target}")


class PaymentState(ABC):
    """Estado concreto de la maquina con transiciones declarativas."""

    @property
    @abstractmethod
    def status(self) -> PaymentStatus:
        ...

    @property
    @abstractmethod
    def label(self) -> str:
        ...

    @property
    @abstractmethod
    def transitions(self) -> dict[PaymentStatus, PaymentStatus]:
        ...

    def can_transition_to(self, target: PaymentStatus) -> bool:
        return target in self.transitions

    def transition_to(self, target: PaymentStatus) -> PaymentStatus:
        if target not in self.transitions:
            raise InvalidPaymentTransitionError(self.status, target)
        return self.transitions[target]


class PendingState(PaymentState):
    @property
    def status(self) -> PaymentStatus:
        return PaymentStatus.PENDING

    @property
    def label(self) -> str:
        return "Pagando"

    @property
    def transitions(self) -> dict[PaymentStatus, PaymentStatus]:
        return {
            PaymentStatus.APPROVED: PaymentStatus.APPROVED,
            PaymentStatus.REJECTED: PaymentStatus.REJECTED,
            PaymentStatus.FAILED: PaymentStatus.FAILED,
        }


class ApprovedState(PaymentState):
    @property
    def status(self) -> PaymentStatus:
        return PaymentStatus.APPROVED

    @property
    def label(self) -> str:
        return "Aprobado"

    @property
    def transitions(self) -> dict[PaymentStatus, PaymentStatus]:
        return {}


class RejectedState(PaymentState):
    @property
    def status(self) -> PaymentStatus:
        return PaymentStatus.REJECTED

    @property
    def label(self) -> str:
        return "Rechazado"

    @property
    def transitions(self) -> dict[PaymentStatus, PaymentStatus]:
        return {PaymentStatus.APPROVED: PaymentStatus.APPROVED}


class FailedState(PaymentState):
    @property
    def status(self) -> PaymentStatus:
        return PaymentStatus.FAILED

    @property
    def label(self) -> str:
        return "Fallido"

    @property
    def transitions(self) -> dict[PaymentStatus, PaymentStatus]:
        return {PaymentStatus.APPROVED: PaymentStatus.APPROVED}


_ALL_STATES: Final[tuple[PaymentState, ...]] = (
    PendingState(),
    ApprovedState(),
    RejectedState(),
    FailedState(),
)

_STATE_BY_STATUS: Final[dict[PaymentStatus, PaymentState]] = {
    state.status: state for state in _ALL_STATES
}


def state_for(status: str | PaymentStatus) -> PaymentState | None:
    """Estado de la maquina para un valor, o None si es desconocido."""
    try:
        return _STATE_BY_STATUS[PaymentStatus(status)]
    except ValueError:
        return None


def is_known_payment_status(status: str | PaymentStatus) -> bool:
    """True si el valor pertenece a la maquina."""
    return state_for(status) is not None


def transition(
    current: str | PaymentStatus | None, target: str | PaymentStatus
) -> PaymentStatus:
    """Transicion validada. Mantiene el contrato de error de O1.

    `current=None` (sin evento de provider aún) transiciona a cualquier
    valor conocido. Levanta InvalidPaymentTransitionError si el origen o
    destino no pertenece a la maquina, o si la transicion no esta permitida.
    """
    if current is None:
        try:
            return PaymentStatus(target)
        except ValueError:
            raise InvalidPaymentTransitionError("None", str(target)) from None
    state = state_for(current)
    if state is None:
        raise InvalidPaymentTransitionError(str(current), str(target))
    try:
        resolved_target = PaymentStatus(target)
    except ValueError:
        raise InvalidPaymentTransitionError(str(current), str(target)) from None
    return state.transition_to(resolved_target)


PAYMENT_STATUS_LABELS: Final[dict[str, str]] = {
    state.status.value: state.label for state in _ALL_STATES
}
