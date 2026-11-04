"""Pedidos (Fase 6, P6): modelo de dominio puro (sin FastAPI/SQLAlchemy).

Entidades y reglas:

* `Customer`: cliente del pedido (nombre + telefono). La dedup es por
  (nombre normalizado, telefono normalizado) — normalizaciones puras
  para que queden testeadas (RF-P6-08).
* `Order`: pedido con fecha, items, override de margen y estado.
* `OrderItem`: linea del pedido (producto + cantidad + porciones + nota).
* `OrderItemSnapshot`: foto del desglose al momento del pedido
  (RNF-P6-03): no se recalcula nunca, sobrevive a cambios de receta,
  precios y margin del tenant.
* Maquina de estados (RNF-P6-01):
      nuevo -> confirmado -> entregado
                   \\-> cancelado
  La confirmacion descuenta stock atomicamente; la cancelacion (solo
  desde confirmado) repone.
"""
from __future__ import annotations

import datetime
import re
import unicodedata
import uuid

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple, Dict

ORDER_STATUSES: Tuple[str, ...] = ("nuevo", "confirmado", "entregado", "cancelado")

ORDER_STATUS_LABELS: Dict[str, str] = {
    "nuevo": "Nuevo",
    "confirmado": "Confirmado",
    "entregado": "Entregado",
    "cancelado": "Cancelado",
}

# Transiciones permitidas (RNF-P6-01). Cancelar solo desde confirmado:
# un pedido "nuevo" todavia no tiene stock descuenta, no hay nada que
# reponer.
ORDER_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "nuevo": ("confirmado",),
    "confirmado": ("entregado", "cancelado"),
    "entregado": (),
    "cancelado": (),
}

_PHONE_DIGITS = re.compile(r"\d+")


class InvalidStatusTransitionError(ValueError):
    """Transicion de estado no permitida (RNF-P6-01)."""

    def __init__(self, current: str, target: str):
        self.current = current
        self.target = target
        super().__init__(f"Transicion invalida: {current} -> {target}")


class OrderNotEditableError(Exception):
    """El pedido ya no esta en estado `nuevo` (verificado bajo lock)."""

    def __init__(self, current: str):
        self.current = current
        super().__init__("Solo se puede editar un pedido en estado nuevo")


class InsufficientOrderStockError(Exception):
    """Stock insuficiente para confirmar un pedido (RNF-P6-02/04).

    `shortage` mapea ingredient_id -> cantidad que falta. `available` y
    `required` (ingredient_id -> cantidad) se capturan bajo lock, en el
    mismo instante del chequeo. La capa de datos lo levanta dentro de la
    transicion (despues de rollback): ningun movimiento ni cambio de
    estado queda aplicado."""

    def __init__(
        self,
        shortage: Dict[str, Decimal],
        available: Optional[Dict[str, Decimal]] = None,
        required: Optional[Dict[str, Decimal]] = None,
    ):
        self.shortage = shortage
        self.available = available if available is not None else {}
        self.required = required if required is not None else {}
        super().__init__(
            f"stock insuficiente en {len(shortage)} insumo(s) para el pedido"
        )


def transition_status(current: str, target: str) -> str:
    """Valida la transicion y devuelve el estado objetivo."""
    if current not in ORDER_TRANSITIONS:
        raise InvalidStatusTransitionError(current, target)
    if target not in ORDER_TRANSITIONS[current]:
        raise InvalidStatusTransitionError(current, target)
    return target


def normalize_customer_name(name: str) -> str:
    """Clave de dedup de nombre: trim + casefold + plegado de acentos.

    '  María ' y 'maria' son el mismo cliente (mismo criterio que la
    busqueda con acentos de RF-P2-02).
    """
    folded = "".join(
        char
        for char in unicodedata.normalize("NFD", name.strip().casefold())
        if unicodedata.category(char) != "Mn"
    )
    return folded


def normalize_phone(phone: str) -> str:
    """Clave de dedup de telefono: solo digitos (acepta +54, espacios, guiones)."""
    match = _PHONE_DIGITS.findall(phone)
    if not match:
        raise ValueError("El telefono no contiene digitos")
    return "".join(match)


@dataclass(frozen=True)
class Customer:
    """Cliente (nombre + telefono). Sin email: el canal de contacto es
    WhatsApp (RF-P6-06)."""

    name: str
    phone: str
    id: Optional[str] = None
    created_at: Optional[datetime.datetime] = None

    def __post_init__(self):
        name = self.name.strip()
        if len(name) < 2 or len(name) > 120:
            raise ValueError("El nombre del cliente debe tener entre 2 y 120 caracteres")
        object.__setattr__(self, "name", name)
        phone = normalize_phone(self.phone)
        if not (5 <= len(phone) <= 20):
            raise ValueError("El telefono debe tener entre 5 y 20 digitos")
        object.__setattr__(self, "phone", phone)
        if self.id is None:
            # La identidad la genera el dominio (mismo criterio que User, F5).
            object.__setattr__(self, "id", str(uuid.uuid4()))

    @property
    def name_norm(self) -> str:
        return normalize_customer_name(self.name)

    @property
    def phone_norm(self) -> str:
        return self.phone


@dataclass(frozen=True)
class OrderItem:
    """Linea del pedido: producto + unidades + porciones + nota.

    `portions` permite convertir el producto a otra cantidad de porciones
    (decisión de negocio confirmada): el factor = portions / servings del
    producto escala insumos y mano de obra.
    """

    product_id: str
    qty: int
    portions: int
    note: str = ""
    product_name: str = ""  # snapshot al momento del pedido
    id: str | None = None
    position: int = 0

    def __post_init__(self):
        if self.qty < 1:
            raise ValueError("La cantidad del item debe ser al menos 1")
        if self.portions < 1:
            raise ValueError("Las porciones del item deben ser al menos 1")
        if len(self.note) > 200:
            raise ValueError("La nota del item debe tener hasta 200 caracteres")
        if self.id is None:
            # La identidad la genera el dominio (mismo criterio que User, F5).
            object.__setattr__(self, "id", str(uuid.uuid4()))
            # After __post_init__ sets id, it's no longer None
            # But the type annotation still allows None for backward compatibility
            # We'll use a property to ensure id is never None when accessed
        
    @property
    def safe_id(self) -> str:
        """Return the item's id, ensuring it's not None after initialization."""
        if self.id is None:
            raise ValueError("OrderItem.id is None - __post_init__ was not called")
        return self.id or ""


@dataclass(frozen=True)
class OrderItemSnapshotLine:
    """Linea de insumo dentro del snapshot: cantidad ya escalada por
    porciones y unidades, costo al precio vigente al momento del pedido."""

    ingredient_id: str
    ingredient_name: str
    qty: Decimal
    unit: str
    cost: Decimal
    is_missing: bool = False  # insumo sin precio: costo 0 (parcial)


@dataclass(frozen=True)
class OrderItemSnapshot:
    """Desglose congelado de un item (RNF-P6-03). Se guarda con el pedido
    y no se recalcula: cambios de receta, precios o margen del tenant no
    lo tocan."""

    lines: tuple[OrderItemSnapshotLine, ...] = ()
    materials: Decimal = Decimal("0")
    waste: Decimal = Decimal("0")
    materials_con_merma: Decimal = Decimal("0")
    labor: Decimal = Decimal("0")
    gas: Decimal = Decimal("0")
    base: Decimal = Decimal("0")
    margin_pct: Decimal = Decimal("0")
    final: Decimal = Decimal("0")
    rounded: Decimal = Decimal("0")
    missing: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.missing


@dataclass(frozen=True)
class Order:
    """Pedido. `customer_name`/`customer_phone` son snapshot para que el
    historio sobreviva a cambios del cliente; `items` referencia el
    catalogo pero el desglose viene de `snapshot`."""

    customer_id: str
    customer_name: str
    customer_phone: str
    date: datetime.date
    status: str = "nuevo"
    margin_pct: Decimal | None = None  # None = default del tenant
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None
    whatsapp_sent_at: datetime.datetime | None = None
    id: str | None = None
    # Fase 5: estado de pago (RF-P6-10) y metodo de pago. El repositorio
    # los rellena al reconstruir (paid se deriva de paid_at, monotono).
    paid: bool = False
    payment_method: str = "cash"

    # Se setean desde el repositorio al reconstruir (frozen).
    items: tuple[OrderItem, ...] = field(default=(), compare=False)
    snapshots: dict[str, OrderItemSnapshot] = field(default_factory=dict, compare=False)

    def __post_init__(self):
        if self.status not in ORDER_TRANSITIONS:
            raise ValueError(f"Estado de pedido desconocido: {self.status}")
        if not isinstance(self.date, datetime.date):
            raise ValueError("El pedido necesita una fecha")
        if self.id is None:
            # La identidad la genera el dominio (mismo criterio que User, F5).
            object.__setattr__(self, "id", str(uuid.uuid4()))

    @property
    def total(self) -> Decimal:
        """Total del pedido: suma del precio final redondeado de cada
        item (lo que paga el cliente)."""
        return sum(
            (self.snapshots[item.id].rounded for item in self.items),
            Decimal("0"),
        )
