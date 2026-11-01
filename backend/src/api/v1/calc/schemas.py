"""Schemas para la API de la calculadora de costos (P5-CC).

Pydantic v2 con extra="forbid" en todos los esquemas de escritura
(RNF-P5CC-02). Money viaja como Decimal (api.v1.money.Money).
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.v1.money import Money, Qty

# Allow-lists
ROUNDING_MODES = Literal["none", "integer", "multiple_10", "commercial_99"]
DEFAULT_COST_TYPES = Literal["labor", "extra_cost"]
DEFAULT_COST_STATUSES = Literal["active", "inactive"]

# String length limits
MAX_BUSINESS_NAME = 120
MAX_CURRENCY_NAME = 40
MAX_CURRENCY_SYMBOL = 8
MAX_CATEGORY_NAME = 80
MAX_CATEGORY_DESCRIPTION = 200
MAX_SUPPLIER_NAME = 120
MAX_SUPPLIER_CONTACT_NAME = 120
MAX_SUPPLIER_PHONE = 30
MAX_SUPPLIER_EMAIL = 120
MAX_SUPPLIER_NOTES = 500
MAX_DEFAULT_COST_NAME = 120


# ─── Settings ───────────────────────────────────────────────────────────

class CalcSettingsRequest(BaseModel):
    """PUT /calc/settings (RF-P5CC-02)."""

    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=1, max_length=MAX_BUSINESS_NAME)
    main_currency_name: str = Field(min_length=1, max_length=MAX_CURRENCY_NAME)
    main_currency_symbol: str = Field(min_length=1, max_length=MAX_CURRENCY_SYMBOL)
    default_margin_percent: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    default_discount_percent: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    default_tax_percent: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    rounding_mode: ROUNDING_MODES


class CalcSettingsResponse(BaseModel):
    """GET /calc/settings response (RF-P5CC-01)."""

    business_name: str
    main_currency_name: str
    main_currency_symbol: str
    default_margin_percent: Decimal
    default_discount_percent: Decimal
    default_tax_percent: Decimal
    rounding_mode: str


# ─── Categories (material + product share same schema shape) ────────────

class CategoryCreate(BaseModel):
    """POST /calc/{material,product}-categories (RF-P5CC-03/04)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_CATEGORY_NAME)
    description: Optional[str] = Field(default=None, max_length=MAX_CATEGORY_DESCRIPTION)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip()


class CategoryUpdate(BaseModel):
    """PATCH /calc/{material,product}-categories/{id} (RF-P5CC-03/04)."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=MAX_CATEGORY_NAME)
    description: Optional[str] = Field(default=None, max_length=MAX_CATEGORY_DESCRIPTION)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip() if value is not None else None

    def _require_at_least_one(self):
        """Validate at least one field is set (enforced in API layer)."""
        pass


class CategoryResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CategoryListResponse(BaseModel):
    items: List[CategoryResponse]
    total: int
    page: int
    page_size: int


# ─── Suppliers ──────────────────────────────────────────────────────────

class SupplierCreate(BaseModel):
    """POST /calc/suppliers (RF-P5CC-05)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_SUPPLIER_NAME)
    contact_name: Optional[str] = Field(default=None, max_length=MAX_SUPPLIER_CONTACT_NAME)
    phone: Optional[str] = Field(default=None, max_length=MAX_SUPPLIER_PHONE)
    email: Optional[str] = Field(default=None, max_length=MAX_SUPPLIER_EMAIL)
    notes: Optional[str] = Field(default=None, max_length=MAX_SUPPLIER_NOTES)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip()

    @field_validator("email")
    @classmethod
    def _email_format(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value.strip():
            import re
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
                raise ValueError("email invalido")
        return value


class SupplierUpdate(BaseModel):
    """PATCH /calc/suppliers/{id} (RF-P5CC-05)."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=MAX_SUPPLIER_NAME)
    contact_name: Optional[str] = Field(default=None, max_length=MAX_SUPPLIER_CONTACT_NAME)
    phone: Optional[str] = Field(default=None, max_length=MAX_SUPPLIER_PHONE)
    email: Optional[str] = Field(default=None, max_length=MAX_SUPPLIER_EMAIL)
    notes: Optional[str] = Field(default=None, max_length=MAX_SUPPLIER_NOTES)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip() if value is not None else None

    @field_validator("email")
    @classmethod
    def _email_format(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value.strip():
            import re
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
                raise ValueError("email invalido")
        return value


class SupplierResponse(BaseModel):
    id: str
    name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: List[SupplierResponse]
    total: int
    page: int
    page_size: int


# ─── Default Costs ─────────────────────────────────────────────────────

class DefaultCostCreate(BaseModel):
    """POST /calc/default-costs (RF-P5CC-06)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_DEFAULT_COST_NAME)
    type: DEFAULT_COST_TYPES
    default_unit_cost_or_rate: Money = Field(ge=Decimal("0"))
    default_quantity_or_minutes: Qty = Field(ge=Decimal("0"))
    status: DEFAULT_COST_STATUSES = "active"

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip()


class DefaultCostUpdate(BaseModel):
    """PATCH /calc/default-costs/{id} (RF-P5CC-06)."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=MAX_DEFAULT_COST_NAME)
    type: Optional[DEFAULT_COST_TYPES] = None
    default_unit_cost_or_rate: Optional[Money] = Field(default=None, ge=Decimal("0"))
    default_quantity_or_minutes: Optional[Qty] = Field(default=None, ge=Decimal("0"))
    status: Optional[DEFAULT_COST_STATUSES] = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip() if value is not None else None


class DefaultCostResponse(BaseModel):
    id: str
    name: str
    type: str
    default_unit_cost_or_rate: Money
    default_quantity_or_minutes: Qty
    status: str
    created_at: datetime
    updated_at: datetime


class DefaultCostListResponse(BaseModel):
    items: List[DefaultCostResponse]
    total: int
    page: int
    page_size: int


# ─── Materials (RF-P2CC-01..05) ────────────────────────────────────────

MAX_MATERIAL_NAME = 120
MAX_MATERIAL_INTERNAL_CODE = 40
MAX_MATERIAL_UNIT_OF_MEASURE = 20
MAX_MATERIAL_NOTES = 500


class MaterialCreate(BaseModel):
    """POST /calc/materials (RF-P2CC-01).

    extra="forbid": unit_cost y status NUNCA aceptan entrada del cliente
    (RF-P2CC-02/03, security #8).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_MATERIAL_NAME)
    internal_code: str | None = Field(default=None, max_length=MAX_MATERIAL_INTERNAL_CODE)
    category_id: str | None = None
    supplier_id: str | None = None
    unit_of_measure: str | None = Field(default=None, max_length=MAX_MATERIAL_UNIT_OF_MEASURE)
    purchase_total_price: Money | None = Field(default=None, ge=Decimal("0"))
    package_quantity: Qty | None = Field(default=None, gt=Decimal("0"))
    notes: str | None = Field(default=None, max_length=MAX_MATERIAL_NOTES)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip()


class MaterialUpdate(BaseModel):
    """PATCH /calc/materials/{id} (RF-P2CC-01).

    Envio explicito de null en purchase_total_price/package_quantity
    elimina el dato (unit_cost -> None, status -> incomplete, y se
    registra en el historial si cambio, RF-P2CC-04).
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=MAX_MATERIAL_NAME)
    internal_code: str | None = Field(default=None, max_length=MAX_MATERIAL_INTERNAL_CODE)
    category_id: str | None = None
    supplier_id: str | None = None
    unit_of_measure: str | None = Field(default=None, max_length=MAX_MATERIAL_UNIT_OF_MEASURE)
    purchase_total_price: Money | None = Field(default=None, ge=Decimal("0"))
    package_quantity: Qty | None = Field(default=None, gt=Decimal("0"))
    notes: str | None = Field(default=None, max_length=MAX_MATERIAL_NOTES)

    @field_validator("name", mode="before")
    @classmethod
    def _name_not_null(cls, value):
        if value is None:
            raise ValueError("nombre no puede ser null")
        return value

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip() if value is not None else None


class MaterialResponse(BaseModel):
    id: str
    name: str
    internal_code: str | None = None
    category_id: str | None = None
    supplier_id: str | None = None
    unit_of_measure: str | None = None
    purchase_total_price: Money | None = None
    package_quantity: Qty | None = None
    unit_cost: Money | None = None
    notes: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class MaterialListResponse(BaseModel):
    items: list[MaterialResponse]
    total: int
    page: int
    page_size: int


class CostHistoryResponse(BaseModel):
    """Fila del historial de costos unitarios (RF-P2CC-04). Montos como str."""

    previous_unit_cost: Money | None = None
    new_unit_cost: Money | None = None
    changed_at: datetime


class CostHistoryListResponse(BaseModel):
    items: list[CostHistoryResponse]
    total: int
    page: int
    page_size: int


# ─── Products (RF-P4CC-01..08) ─────────────────────────────────────────

MAX_PRODUCT_NAME = 120
MAX_PRODUCT_SKU = 40
MAX_PRODUCT_DESCRIPTION = 500
MAX_PRODUCT_NOTES = 500
MAX_LINE_NAME = 120

PRODUCT_STATUSES = Literal["draft", "active", "archived"]


class ProductLineMaterialIn(BaseModel):
    """Linea de material del payload (RF-P4CC-02).

    extra="forbid": los snapshots (`material_name`,
    `unit_of_measure_snapshot`, `unit_cost_snapshot`) y
    `line_total_cost` NUNCA vienen del cliente (security #8): el
    servidor los resuelve desde calc_materials al guardar.
    """

    model_config = ConfigDict(extra="forbid")

    material_id: str
    quantity_used: Qty = Field(ge=Decimal("0"))


class ProductLineLaborIn(BaseModel):
    """Linea de mano de obra del payload (RF-P4CC-02).

    extra="forbid": `line_total_cost` nunca viene del cliente
    (security #8): lo deriva el motor.
    """

    model_config = ConfigDict(extra="forbid")

    activity_name: str = Field(min_length=1, max_length=MAX_LINE_NAME)
    hourly_rate: Money = Field(ge=Decimal("0"))
    minutes_required: Qty = Field(ge=Decimal("0"))


class ProductLineExtraCostIn(BaseModel):
    """Linea de costo extra del payload (RF-P4CC-02).

    extra="forbid": `line_total_cost` nunca viene del cliente
    (security #8).
    """

    model_config = ConfigDict(extra="forbid")

    concept_name: str = Field(min_length=1, max_length=MAX_LINE_NAME)
    unit_cost: Money = Field(ge=Decimal("0"))
    quantity: Qty = Field(ge=Decimal("0"))


class ProductCreate(BaseModel):
    """POST /calc/products (RF-P4CC-01..05).

    Percents omitidos -> defaults del singleton CalcSettings
    (RF-P5CC-01). `costs`, `line_total_cost` y campos `*_snapshot`
    no existen en el payload (extra="forbid", security #8).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_PRODUCT_NAME)
    sku: str | None = Field(default=None, max_length=MAX_PRODUCT_SKU)
    category_id: str | None = None
    description: str | None = Field(default=None, max_length=MAX_PRODUCT_DESCRIPTION)
    notes: str | None = Field(default=None, max_length=MAX_PRODUCT_NOTES)
    margin_percent: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    discount_percent: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    tax_percent: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    status: PRODUCT_STATUSES = "draft"
    materials: list[ProductLineMaterialIn] = Field(default_factory=list)
    labor: list[ProductLineLaborIn] = Field(default_factory=list)
    extra_costs: list[ProductLineExtraCostIn] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip()

    @field_validator("sku")
    @classmethod
    def _sku_strip(cls, value: str | None) -> str | None:
        return value.strip() if value is not None and value.strip() else None


class ProductUpdate(BaseModel):
    """PATCH /calc/products/{id} (RF-P4CC-01/02).

    Semantica de lineas (regla 4): clave ausente -> no cambia;
    clave [] -> vacia el set de ese tipo; lista -> reemplazo
    completo. Sin campos -> 422 (idomatico a B4-B7).
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=MAX_PRODUCT_NAME)
    sku: str | None = Field(default=None, max_length=MAX_PRODUCT_SKU)
    category_id: str | None = None
    description: str | None = Field(default=None, max_length=MAX_PRODUCT_DESCRIPTION)
    notes: str | None = Field(default=None, max_length=MAX_PRODUCT_NOTES)
    margin_percent: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    discount_percent: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    tax_percent: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    status: PRODUCT_STATUSES | None = None
    materials: list[ProductLineMaterialIn] | None = None
    labor: list[ProductLineLaborIn] | None = None
    extra_costs: list[ProductLineExtraCostIn] | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("nombre no puede estar vacio")
        return value.strip() if value is not None else None

    @field_validator("sku")
    @classmethod
    def _sku_strip(cls, value: str | None) -> str | None:
        return value.strip() if value is not None and value.strip() else None


class ProductResponse(BaseModel):
    """Producto sin lineas ni costs. Percents como numero (estilo
    CalcSettingsResponse); montos de lineas/costs siempre str."""

    id: str
    name: str
    sku: str | None = None
    category_id: str | None = None
    description: str | None = None
    notes: str | None = None
    margin_percent: Decimal
    discount_percent: Decimal
    tax_percent: Decimal
    status: str
    last_recalculated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int


class ProductCostsResponse(BaseModel):
    """Desglose de 6 montos (RF-P4CC-05), nombres exactos del motor
    legacy. Montos siempre str (Money)."""

    product_total_cost: Money
    profit_amount: Money
    discount_amount: Money
    adjusted_profit_amount: Money
    tax_amount: Money
    final_sale_price: Money


class ProductLineMaterialOut(BaseModel):
    material_id: str
    material_name: str
    quantity_used: Qty
    unit_of_measure_snapshot: str | None = None
    unit_cost_snapshot: Money
    line_total_cost: Money
    sort_order: int


class ProductLineLaborOut(BaseModel):
    activity_name: str
    hourly_rate: Money
    minutes_required: Qty
    line_total_cost: Money
    sort_order: int


class ProductLineExtraCostOut(BaseModel):
    concept_name: str
    unit_cost: Money
    quantity: Qty
    line_total_cost: Money
    sort_order: int


class ProductLinesOut(BaseModel):
    materials: list[ProductLineMaterialOut]
    labor: list[ProductLineLaborOut]
    extra_costs: list[ProductLineExtraCostOut]


class ProductWithLinesResponse(BaseModel):
    """Respuesta de POST/PATCH/recalculate: producto + lineas + costs."""

    product: ProductResponse
    product_lines: ProductLinesOut
    costs: ProductCostsResponse


class ProductVersionResponse(BaseModel):
    """Version append-only del precio (RF-P4CC-07). Montos str."""

    version_number: int
    product_total_cost: Money
    profit_amount: Money
    discount_amount: Money
    adjusted_profit_amount: Money
    tax_amount: Money
    final_sale_price: Money
    changed_at: datetime


class ProductVersionListResponse(BaseModel):
    items: list[ProductVersionResponse]
    total: int
    page: int
    page_size: int
