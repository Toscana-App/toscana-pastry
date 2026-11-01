"""Dominio de materiales de la calculadora de costos (P2-CC).

Entidades frozen con __post_init__ para validacion de rangos. Money y
cantidades siempre Decimal, nunca float (RNF-P5CC-01). `unit_cost` y
`status` son SOLO derivados del servidor (RF-P2CC-02/03, security #8):
ningun valor de entrada del cliente los fija.
"""

import datetime
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

# String length limits (RF-P2CC-01)
MAX_MATERIAL_NAME = 120
MAX_MATERIAL_INTERNAL_CODE = 40
MAX_MATERIAL_UNIT_OF_MEASURE = 20
MAX_MATERIAL_NOTES = 500

# Estados derivados (RF-P2CC-03)
MATERIAL_STATUS_ACTIVE = "active"
MATERIAL_STATUS_INCOMPLETE = "incomplete"

_CENTS = Decimal("0.01")


def compute_unit_cost(
    purchase_total_price: Decimal | None,
    package_quantity: Decimal | None,
) -> Decimal | None:
    """unit_cost = purchase_total_price / package_quantity (RF-P2CC-02).

    Faltando precio o cantidad devuelve None (material `incomplete`).
    Si package_quantity es <= 0 o el precio es negativo lanza ValueError
    (la API lo traduce a 422). El redondeo es ROUND_HALF_UP a centavos;
    el float nunca toca el monto (RNF-P5CC-01).
    """
    if purchase_total_price is None or package_quantity is None:
        return None
    if package_quantity <= 0:
        raise ValueError("package_quantity debe ser > 0")
    if purchase_total_price < 0:
        raise ValueError(f"purchase_total_price >= 0: {purchase_total_price}")
    return (purchase_total_price / package_quantity).quantize(
        _CENTS, rounding=ROUND_HALF_UP
    )


def derive_status(
    purchase_total_price: Decimal | None,
    package_quantity: Decimal | None,
) -> str:
    """Status derivado (RF-P2CC-03): `incomplete` si falta precio o
    cantidad por paquete; `active` si no."""
    if purchase_total_price is None or package_quantity is None:
        return MATERIAL_STATUS_INCOMPLETE
    return MATERIAL_STATUS_ACTIVE


@dataclass(frozen=True)
class CalcMaterial:
    """Material de la calculadora de costos (RF-P2CC-01).

    `unit_cost` y `status` se derivan aqui en el servidor a partir de
    `purchase_total_price` y `package_quantity`; cualquier valor
    pasado por el cliente se descarta (RF-P2CC-02/03, security #8).
    """

    name: str
    internal_code: str | None = None
    category_id: str | None = None
    supplier_id: str | None = None
    unit_of_measure: str | None = None
    purchase_total_price: Decimal | None = None
    package_quantity: Decimal | None = None
    notes: str | None = None
    unit_cost: Decimal | None = None
    status: str = MATERIAL_STATUS_INCOMPLETE
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    def __post_init__(self):
        name = self.name.strip()
        if not name:
            raise ValueError("name requerido y no puede ser solo espacios")
        if not (1 <= len(name) <= MAX_MATERIAL_NAME):
            raise ValueError(f"name longitud 1-{MAX_MATERIAL_NAME}: {len(name)}")
        if (
            self.internal_code is not None
            and len(self.internal_code) > MAX_MATERIAL_INTERNAL_CODE
        ):
            raise ValueError(
                f"internal_code max {MAX_MATERIAL_INTERNAL_CODE}: "
                f"{len(self.internal_code)}"
            )
        if (
            self.unit_of_measure is not None
            and len(self.unit_of_measure) > MAX_MATERIAL_UNIT_OF_MEASURE
        ):
            raise ValueError(
                f"unit_of_measure max {MAX_MATERIAL_UNIT_OF_MEASURE}: "
                f"{len(self.unit_of_measure)}"
            )
        if self.notes is not None and len(self.notes) > MAX_MATERIAL_NOTES:
            raise ValueError(f"notes max {MAX_MATERIAL_NOTES}: {len(self.notes)}")
        if self.purchase_total_price is not None and self.purchase_total_price < 0:
            raise ValueError(f"purchase_total_price >= 0: {self.purchase_total_price}")
        if self.package_quantity is not None and self.package_quantity <= 0:
            raise ValueError("package_quantity debe ser > 0")

        # Derivacion en el servidor: unit_cost/status nunca del cliente.
        object.__setattr__(
            self,
            "unit_cost",
            compute_unit_cost(self.purchase_total_price, self.package_quantity),
        )
        object.__setattr__(
            self,
            "status",
            derive_status(self.purchase_total_price, self.package_quantity),
        )


@dataclass(frozen=True)
class CalcMaterialCostHistory:
    """Fila del historial de costos unitarios (RF-P2CC-04).

    Append-only: solo se INSERTA, nunca se UPDATE/DELETE (estilo
    StockMovementORM, RF-P2-04).
    """

    material_id: str
    previous_unit_cost: Decimal | None = None
    new_unit_cost: Decimal | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    changed_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
