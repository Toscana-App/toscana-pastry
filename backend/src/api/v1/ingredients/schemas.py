from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.v1.money import Money, Qty

UNITS = Literal["kg", "g", "L", "ml", "unidad"]
REASONS = Literal["compra", "merma", "ajuste"]
STATUSES = Literal["OK", "LOW", "EMPTY"]


class IngredientCreate(BaseModel):
    """Body de POST /ingredients (spec p02 RF-P2-01, api_endpoints FASE 1).

    extra="forbid": un campo desconocido es 422, no un silencio que se
    pierde entre el frontend y la base.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    unit: UNITS
    price_per_unit: Money = Field(ge=0)
    stock_qty: Qty = Field(default=Decimal("0"), ge=Decimal("0"))
    low_stock_threshold: Qty = Field(default=Decimal("0"), ge=Decimal("0"))

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        # min_length=1 deja pasar "  "; un nombre de solo espacios no
        # existe. 422 por payload, no 400 por dominio.
        if not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip()


class IngredientUpdate(BaseModel):
    """Body de PATCH /ingredients/{id}: solo nombre/unidad/precio/umbral.
    El stock se cambia por /stock (deja movimiento registrado)."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    unit: Optional[UNITS] = None
    price_per_unit: Optional[Money] = Field(default=None, ge=0)
    low_stock_threshold: Optional[Qty] = Field(default=None, ge=Decimal("0"))

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def _require_at_least_one(self):
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("al menos un campo para actualizar")
        return self


class IngredientResponse(BaseModel):
    id: str
    name: str
    unit: str
    price_per_unit: Money
    stock_qty: Qty
    low_stock_threshold: Qty
    status: str  # OK | LOW | EMPTY — campo computado del servidor


class IngredientListResponse(BaseModel):
    items: List[IngredientResponse]
    total: int
    page: int
    page_size: int


class IngredientDetailResponse(BaseModel):
    ingredient: IngredientResponse
    movements: Optional[List["StockMovementResponse"]] = None


class StockAdjustment(BaseModel):
    """Body de POST /ingredients/{id}/stock. Delta firmado:
    entrada positiva, salida negativa."""

    model_config = ConfigDict(extra="forbid")

    delta: Qty
    reason: REASONS
    ref: Optional[str] = Field(default=None, max_length=120)


class StockMovementResponse(BaseModel):
    id: str
    qty_delta: Qty
    reason: str
    ref: Optional[str]
    created_at: datetime


class StockAdjustmentResponse(BaseModel):
    stock_qty: Qty
    movement: StockMovementResponse


class MovementListResponse(BaseModel):
    items: List[StockMovementResponse]
    total: int
    page: int
    page_size: int


class ImportRequest(BaseModel):
    """RF-P2-07: carga inicial por lista pegada."""

    lines: List[str] = Field(min_length=1, max_length=500)


class ImportErrorItem(BaseModel):
    line: int  # 1-based, la línea tal como la envió el usuario
    message: str


class ImportResponse(BaseModel):
    created: int
    errors: List[ImportErrorItem]
