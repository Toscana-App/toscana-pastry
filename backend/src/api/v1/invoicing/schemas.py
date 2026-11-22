from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.v1.money import Money

DocTipo = Literal[99, 80, 86]


class InvoiceItemInput(BaseModel):
    """Ítem descriptivo del comprobante (detalle para el PDF)."""

    model_config = ConfigDict(extra="forbid")

    descripcion: str = Field(min_length=1, max_length=300)
    cantidad: int = Field(ge=1)
    precio_unit: Money = Field(gt=0)


class InvoiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(min_length=1, max_length=64)
    concepto: int = Field(default=1, ge=1, le=3)
    fch_serv_desde: date | None = None
    fch_serv_hasta: date | None = None
    doc_tipo: DocTipo = 99
    doc_nro: int = Field(default=0, ge=0)
    receptor_nombre: str = Field(default="", max_length=120)
    items: list[InvoiceItemInput] | None = None


class InvoiceItemResponse(BaseModel):
    descripcion: str
    cantidad: int
    precio_unit: Money


class InvoiceResponse(BaseModel):
    id: str
    order_id: str
    punto_venta: int
    tipo_cbte: int
    numero: int
    cae: str
    cae_vto: date
    fecha: date
    imp_total: Money
    estado: str
    pdf_url: str


class InvoiceListItem(BaseModel):
    id: str
    order_id: str
    punto_venta: int
    tipo_cbte: int
    numero: int
    cae: str
    cae_vto: date
    fecha: date
    imp_total: Money
    estado: str
    created_at: datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceListItem]
    total: int
    page: int
    page_size: int


class InvoiceDetail(BaseModel):
    id: str
    order_id: str
    punto_venta: int
    tipo_cbte: int
    numero: int
    cae: str
    cae_vto: date
    fecha: date
    imp_total: Money
    estado: str
    condicion_iva: str
    receptor_doc_tipo: int
    receptor_doc_nro: int
    receptor_nombre: str
    created_at: datetime
    pdf_url: str


class InvoiceDetailResponse(BaseModel):
    invoice: InvoiceDetail
    items: list[InvoiceItemResponse]
    observaciones: list[str]


class InvoicingSettingsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cuit: str = Field(pattern=r"^\d{11}$")
    punto_venta: int = Field(ge=1)
    razon_social: str = Field(default="", max_length=120)
    domicilio: str = Field(default="", max_length=200)
    condicion_iva: str = Field(default="Responsable Monotributo", max_length=60)
    categoria_monotributo: str = Field(default="", pattern=r"^[A-Ka-k]?$")
    ingresos_brutos: str = Field(default="", max_length=40)
    inicio_actividades: str = Field(
        default="", pattern=r"^(\d{2}/\d{2}/\d{4})?$"
    )


class InvoicingSettingsResponse(BaseModel):
    configured: bool
    settings: InvoicingSettingsPayload | None = None


class InvoicingSettingsSaved(BaseModel):
    settings: InvoicingSettingsPayload
