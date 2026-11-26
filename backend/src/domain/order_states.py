"""Maquina de estados de pedidos (GoF State) — unica dueña del flujo.

Valores persistentes (API, frontend, BD), siempre en inglés:
    new -> confirmed -> preparing -> pending_delivery -> delivered
    confirmed -> cancelled
    preparing -> cancelled

Este modulo es la unica fuente de la maquina: `OrderStatus`, los estados
concretos con sus transiciones declarativas, la transicion validada y
las etiquetas derivadas de los propios estados.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Final


class OrderStatus(StrEnum):
    NEW = "new"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    PENDING_DELIVERY = "pending_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class InvalidStatusTransitionError(ValueError):
    """Transicion no permitida por la maquina (contrato historico)."""

    def __init__(self, current: str, target: str):
        self.current = current
        self.target = target
        super().__init__(f"Transicion invalida: {current} -> {target}")


class OrderState(ABC):
    """Estado concreto de la maquina con transiciones declarativas."""

    @property
    @abstractmethod
    def status(self) -> OrderStatus:
        ...

    @property
    @abstractmethod
    def label(self) -> str:
        ...

    @property
    @abstractmethod
    def transitions(self) -> dict[OrderStatus, OrderStatus]:
        ...

    def can_transition_to(self, target: OrderStatus) -> bool:
        return target in self.transitions

    def transition_to(self, target: OrderStatus) -> OrderStatus:
        if target not in self.transitions:
            raise InvalidStatusTransitionError(self.status, target)
        return self.transitions[target]


class NewState(OrderState):
    @property
    def status(self) -> OrderStatus:
        return OrderStatus.NEW

    @property
    def label(self) -> str:
        return "Nuevo"

    @property
    def transitions(self) -> dict[OrderStatus, OrderStatus]:
        return {OrderStatus.CONFIRMED: OrderStatus.CONFIRMED}


class ConfirmedState(OrderState):
    @property
    def status(self) -> OrderStatus:
        return OrderStatus.CONFIRMED

    @property
    def label(self) -> str:
        return "Confirmado"

    @property
    def transitions(self) -> dict[OrderStatus, OrderStatus]:
        return {
            OrderStatus.PREPARING: OrderStatus.PREPARING,
            OrderStatus.CANCELLED: OrderStatus.CANCELLED,
        }


class PreparingState(OrderState):
    @property
    def status(self) -> OrderStatus:
        return OrderStatus.PREPARING

    @property
    def label(self) -> str:
        return "Pendiente preparación"

    @property
    def transitions(self) -> dict[OrderStatus, OrderStatus]:
        return {
            OrderStatus.PENDING_DELIVERY: OrderStatus.PENDING_DELIVERY,
            OrderStatus.CANCELLED: OrderStatus.CANCELLED,
        }


class PendingDeliveryState(OrderState):
    @property
    def status(self) -> OrderStatus:
        return OrderStatus.PENDING_DELIVERY

    @property
    def label(self) -> str:
        return "Pendiente entrega"

    @property
    def transitions(self) -> dict[OrderStatus, OrderStatus]:
        return {OrderStatus.DELIVERED: OrderStatus.DELIVERED}


class DeliveredState(OrderState):
    @property
    def status(self) -> OrderStatus:
        return OrderStatus.DELIVERED

    @property
    def label(self) -> str:
        return "Entregado"

    @property
    def transitions(self) -> dict[OrderStatus, OrderStatus]:
        return {}


class CancelledState(OrderState):
    @property
    def status(self) -> OrderStatus:
        return OrderStatus.CANCELLED

    @property
    def label(self) -> str:
        return "Cancelado"

    @property
    def transitions(self) -> dict[OrderStatus, OrderStatus]:
        return {}


_ALL_STATES: Final[tuple[OrderState, ...]] = (
    NewState(),
    ConfirmedState(),
    PreparingState(),
    PendingDeliveryState(),
    DeliveredState(),
    CancelledState(),
)

_STATE_BY_STATUS: Final[dict[OrderStatus, OrderState]] = {
    state.status: state for state in _ALL_STATES
}


def state_for(status: str | OrderStatus) -> OrderState | None:
    """Estado de la maquina para un valor, o None si es desconocido."""
    try:
        return _STATE_BY_STATUS[OrderStatus(status)]
    except ValueError:
        return None


def is_known_status(status: str | OrderStatus) -> bool:
    """True si el valor pertenece a la maquina."""
    return state_for(status) is not None


def transition(
    current: str | OrderStatus, target: str | OrderStatus
) -> OrderStatus:
    """Transicion validada. Mantiene el contrato de error historico.

    Levanta InvalidStatusTransitionError si el estado origen o destino no
    pertenece a la maquina, o si la transicion no esta permitida.
    """
    state = state_for(current)
    if state is None:
        raise InvalidStatusTransitionError(str(current), str(target))
    try:
        resolved_target = OrderStatus(target)
    except ValueError:
        raise InvalidStatusTransitionError(str(current), str(target)) from None
    return state.transition_to(resolved_target)


ORDER_STATUS_LABELS: Final[dict[str, str]] = {
    state.status.value: state.label for state in _ALL_STATES
}
