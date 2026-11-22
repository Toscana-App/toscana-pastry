"""P13 — Dominio de facturación electrónica ARCA (reglas puras).

Factura C de monotributista emitida vía los webservice WSAA + WSFEv1 de
ARCA. Este módulo es sin dependencias (funciones puras + entidades) y
concentra las reglas fiscales del comprobante:

- concepto 2/3 exige período de servicio
- DocTipo de receptor válido (99 CF / 80 CUIT / 86 DNI)
- CAE siempre de 14 dígitos
- fechas dentro de la ventana que ARCA admite (±5 días productos,
  ±10 días servicios)
- importe > 0
- un comprobante por pedido
- número consecutivo por punto de venta

Las reglas de flujo (qué endpoint emite, guards, persistencia) viven en
``api/v1/invoicing`` y el cliente ARCA en ``data/invoicing``. Ver
``docs/specs/p13_invoicing.md``.
"""

from __future__ import annotations

import datetime
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Protocol

CONCEPTO_PRODUCTOS = 1
CONCEPTO_SERVICIOS = 2
CONCEPTO_AMBOS = 3
CONCEPTOS_VALIDOS = (CONCEPTO_PRODUCTOS, CONCEPTO_SERVICIOS, CONCEPTO_AMBOS)

TIPO_CBTE_FACTURA_C = 11

DOC_TIPO_CONSUMIDOR_FINAL = 99
DOC_TIPO_CUIT = 80
DOC_TIPO_DNI = 86
DOC_TIPOS_VALIDOS = (DOC_TIPO_CONSUMIDOR_FINAL, DOC_TIPO_CUIT, DOC_TIPO_DNI)

CAE_LENGTH = 14

ESTADO_APROBADO = "A"
ESTADO_RECHAZADO = "R"
ESTADOS_VALIDOS = (ESTADO_APROBADO, ESTADO_RECHAZADO)

PRODUCTS_DATE_WINDOW_DAYS = 5
SERVICES_DATE_WINDOW_DAYS = 10

MONOTRIBUTO_CATEGORIES = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K")

_CUIT_RE = re.compile(r"\d{11}")
_INICIO_ACTIVIDADES_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

_MAX_OBSERVACIONES = 10
_OBSERVACION_MAX_LEN = 200
_OBSERVACION_RUIDO = re.compile(
    r"traceback|file\s+\"|line\s+\d+|column\s+\d+|exception|stack\s*trace", re.IGNORECASE
)


class InvoiceValidationError(ValueError):
    """Error de regla de negocio con código estable (mapeo a HTTP)."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


# ─── Errores del cliente ARCA (definidos aquí para que el dominio y el
# use case no dependan de la capa data) ────────────────────────────────────


class AfipError(Exception):
    """Base de los errores del cliente AFIP/ARCA."""

    def __init__(self, message: str, observaciones: list[str] | None = None) -> None:
        self.message = message
        self.observaciones = observaciones or []
        super().__init__(message)

    def __str__(self) -> str:
        if self.observaciones:
            return f"{self.message}: {'; '.join(self.observaciones)}"
        return self.message


class AfipCredentialMissingError(AfipError):
    """Falta clave privada y/o certificado ARCA configurado."""


class AfipUnavailableError(AfipError):
    """El webservice de ARCA no respondió (red / servicio caído)."""


class AfipWsfeError(AfipError):
    """ARCA respondió con errores (Errors u observaciones) en WSFEv1."""


class InvoicingNotConfiguredError(Exception):
    """Faltan CUIT y/o punto de venta en los settings de facturación."""


@dataclass(frozen=True)
class AfipCaeResult:
    """Respuesta de ``FeCAESolicitar`` ya normalizada por la capa data.

    ``resultado`` es ``A`` (aprobado) o ``R`` (rechazado); las observaciones
    llegan como ``"<código>: <mensaje>"`` listas para sanear.
    """

    resultado: str
    cae: str = ""
    cae_vto: datetime.date | None = None
    observaciones: tuple[str, ...] = ()


class AfipClient(Protocol):
    """Contrato del cliente ARCA (implementado en ``data/invoicing``)."""

    async def last_authorized(
        self, *, cuit: str, punto_venta: int, tipo_cbte: int
    ) -> int: ...

    async def request_cae(self, *, cuit: str, request: dict) -> AfipCaeResult: ...



# ─── Validaciones puras ────────────────────────────────────────────────────


def validate_cuit(cuit: str) -> str:
    """CUIT emitente: exactamente 11 dígitos. Devuelve el valor limpio."""
    value = (cuit or "").strip()
    if not _CUIT_RE.fullmatch(value):
        raise InvoiceValidationError("cuit_invalido")
    return value


def validate_monotributo_categoria(categoria: str | None) -> str:
    """Categoría de monotributo A–K (o vacío). Normaliza a mayúscula."""
    value = (categoria or "").strip().upper()
    if value and value not in MONOTRIBUTO_CATEGORIES:
        raise InvoiceValidationError("categoria_monotributo_invalida")
    return value


def validate_inicio_actividades(valor: str | None) -> str:
    """Inicio de actividades ``DD/MM/AAAA`` (o vacío). Valida fecha real."""
    value = (valor or "").strip()
    if not value:
        return ""
    match = _INICIO_ACTIVIDADES_RE.fullmatch(value)
    if not match:
        raise InvoiceValidationError("inicio_actividades_invalido")
    day, month, year = (int(g) for g in match.groups())
    try:
        datetime.date(year, month, day)
    except ValueError as exc:
        raise InvoiceValidationError("inicio_actividades_invalido") from exc
    return value


def validate_concepto_periodo(
    concepto: int,
    fch_serv_desde: datetime.date | None,
    fch_serv_hasta: datetime.date | None,
) -> None:
    """Concepto 2/3 exige desde y hasta, con desde <= hasta."""
    if concepto not in CONCEPTOS_VALIDOS:
        raise InvoiceValidationError("concepto_invalido")
    if concepto in (CONCEPTO_SERVICIOS, CONCEPTO_AMBOS):
        if fch_serv_desde is None or fch_serv_hasta is None:
            raise InvoiceValidationError("periodo_servicio_requerido")
        if fch_serv_desde > fch_serv_hasta:
            raise InvoiceValidationError("periodo_servicio_invalido")


def validate_doc_receptor(doc_tipo: int, doc_nro: int) -> None:
    """DocTipo 99 (CF, sin número) / 80 (CUIT 11 dígitos) / 86 (DNI 7-8)."""
    if doc_tipo == DOC_TIPO_CONSUMIDOR_FINAL:
        if doc_nro != 0:
            raise InvoiceValidationError("doc_receptor_invalido")
        return
    if doc_tipo == DOC_TIPO_CUIT:
        digits = str(doc_nro)
        if not digits.isdigit() or not 11 <= len(digits) <= 11:
            raise InvoiceValidationError("doc_receptor_invalido")
        return
    if doc_tipo == DOC_TIPO_DNI:
        digits = str(doc_nro)
        if not digits.isdigit() or not 7 <= len(digits) <= 8:
            raise InvoiceValidationError("doc_receptor_invalido")
        return
    raise InvoiceValidationError("doc_receptor_invalido")


def normalize_cae(cae: object) -> str:
    """CAE de ARCA: siempre 14 dígitos (padded con ceros)."""
    text = str(cae or "").strip()
    if not text.isdigit():
        raise InvoiceValidationError("cae_invalido")
    if len(text) > CAE_LENGTH:
        raise InvoiceValidationError("cae_invalido")
    return text.zfill(CAE_LENGTH)


def parse_arca_fecha(valor: object) -> datetime.date:
    """Fecha ARCA ``YYYYMMDD`` (o ISO) → date. Inválido → error."""
    text = str(valor or "").strip()
    if len(text) == 8 and text.isdigit():
        try:
            return datetime.date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        except ValueError as exc:
            raise InvoiceValidationError("cae_vto_invalido") from exc
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError as exc:
        raise InvoiceValidationError("cae_vto_invalido") from exc


def validar_fechas_arca(
    fecha_emision: datetime.date,
    concepto: int,
    hoy: datetime.date,
    fch_serv_desde: datetime.date | None = None,
    fch_serv_hasta: datetime.date | None = None,
) -> None:
    """Fecha de emisión (y del período de servicio) dentro de la ventana.

    ARCA rechaza comprobantes con fecha fuera de ±5 días (productos) o
    ±10 días (servicios) — troubleshooting obs 10015.
    """
    window = (
        PRODUCTS_DATE_WINDOW_DAYS
        if concepto == CONCEPTO_PRODUCTOS
        else SERVICES_DATE_WINDOW_DAYS
    )
    if abs((hoy - fecha_emision).days) > window:
        raise InvoiceValidationError("fecha_fuera_ventana_arca")
    if concepto in (CONCEPTO_SERVICIOS, CONCEPTO_AMBOS):
        for fecha in (fch_serv_desde, fch_serv_hasta):
            if fecha is not None and abs((hoy - fecha).days) > window:
                raise InvoiceValidationError("fecha_fuera_ventana_arca")


def validate_importe(valor: Decimal | str | int) -> Decimal:
    """Importe total: decimal válido y estrictamente > 0."""
    try:
        amount = valor if isinstance(valor, Decimal) else Decimal(str(valor))
    except (InvalidOperation, ValueError) as exc:
        raise InvoiceValidationError("importe_invalido") from exc
    if amount <= 0:
        raise InvoiceValidationError("importe_invalido")
    return amount


def ensure_order_not_invoiced(existing: Invoice | None) -> None:
    """Un solo comprobante por pedido (D3)."""
    if existing is not None:
        err = InvoiceValidationError("pedido_ya_facturado")
        err.invoice = existing  # type: ignore[attr-defined]
        raise err


def next_invoice_number(ultimo_autorizado: int) -> int:
    """Número siguiente = FECompUltimoAutorizado + 1 (desde 1)."""
    if ultimo_autorizado < 0:
        raise InvoiceValidationError("numero_invalido")
    return ultimo_autorizado + 1


def sanitize_arca_observaciones(
    observaciones: Sequence[str] | str | None,
) -> list[str]:
    """Sanea observaciones ARCA para el 400: sin ruido técnico ni trazas.

    El texto fiscal público viaja intacto; se descartan líneas de stack
    trace, se truncan las demasiado largas y se limita a 10 observaciones.
    """
    if observaciones is None:
        return []
    if isinstance(observaciones, (str, bytes)):
        items: Sequence[object] = (observaciones,)
    else:
        items = observaciones
    cleaned: list[str] = []
    for obs in items:
        text = str(obs).strip()
        if not text:
            continue
        if _OBSERVACION_RUIDO.search(text):
            continue
        if len(text) > _OBSERVACION_MAX_LEN:
            text = text[: _OBSERVACION_MAX_LEN - 1] + "…"
        cleaned.append(text)
        if len(cleaned) >= _MAX_OBSERVACIONES:
            break
    return cleaned


def format_cbte(punto_venta: int, numero: int) -> str:
    """Formato de comprobante para exhibición: ``P-NNNN`` (p. ej. 1-00042)."""
    return f"{punto_venta:04d}-{numero:08d}"


def build_fe_cae_request(
    *,
    punto_venta: int,
    tipo_cbte: int,
    numero: int,
    imp_total: Decimal | str,
    concepto: int,
    doc_tipo: int,
    doc_nro: int,
    fecha: datetime.date,
    fch_serv_desde: datetime.date | None = None,
    fch_serv_hasta: datetime.date | None = None,
) -> dict:
    """Payload ``FeCAESolicitar`` (una línea) para Factura C.

    Es una regla pura (sin I/O): la capa data lo envía tal cual. ImpNeto =
    ImpTotal (sin IVA: Factura C de monotributista).
    """
    if punto_venta < 1 or numero < 1:
        raise InvoiceValidationError("punto_venta_invalido")
    total = validate_importe(imp_total)
    validate_concepto_periodo(concepto, fch_serv_desde, fch_serv_hasta)

    detalle: dict = {
        "Concepto": concepto,
        "DocTipo": doc_tipo,
        "DocNro": doc_nro,
        "CbteDesde": numero,
        "CbteHasta": numero,
        "CbteFch": fecha.strftime("%Y%m%d"),
        "ImpTotal": float(total),
        "ImpTotConc": 0,
        "ImpNeto": float(total),
        "ImpOpEx": 0,
        "ImpIVA": 0,
        "ImpTrib": 0,
        "MonId": "PES",
        "MonCotiz": 1,
    }
    if concepto in (CONCEPTO_SERVICIOS, CONCEPTO_AMBOS):
        desde = fch_serv_desde
        hasta = fch_serv_hasta
        if desde is None or hasta is None:
            raise InvoiceValidationError("periodo_servicio_requerido")
        detalle["FchServDesde"] = desde.strftime("%Y%m%d")
        detalle["FchServHasta"] = hasta.strftime("%Y%m%d")
        detalle["FchVtoPago"] = fecha.strftime("%Y%m%d")
    return {
        "FeCabReq": {"CantReg": 1, "PtoVta": punto_venta, "CbteTipo": tipo_cbte},
        "FeDetReq": {"FECAEDetRequest": [detalle]},
    }


# ─── Entidades de dominio ──────────────────────────────────────────────────


@dataclass(frozen=True)
class InvoiceItem:
    """Ítem del comprobante (detalle para el PDF)."""

    descripcion: str
    cantidad: Decimal
    precio_unit: str
    position: int = 0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        descripcion = (self.descripcion or "").strip()
        if not descripcion:
            raise InvoiceValidationError("descripcion_invalida")
        if len(descripcion) > 300:
            raise InvoiceValidationError("descripcion_invalida")
        try:
            cantidad = self.cantidad if isinstance(self.cantidad, Decimal) else Decimal(str(self.cantidad))
        except (InvalidOperation, ValueError) as exc:
            raise InvoiceValidationError("cantidad_invalida") from exc
        if cantidad <= 0:
            raise InvoiceValidationError("cantidad_invalida")
        validate_importe(self.precio_unit)
        object.__setattr__(self, "descripcion", descripcion)
        object.__setattr__(self, "cantidad", cantidad)
        object.__setattr__(self, "precio_unit", str(Decimal(str(self.precio_unit)).quantize(Decimal("0.01"))))


@dataclass(frozen=True)
class InvoicingSettings:
    """Settings de facturación (singleton en la capa de datos)."""

    cuit: str
    punto_venta: int
    razon_social: str = ""
    domicilio: str = ""
    condicion_iva: str = "Responsable Monotributo"
    categoria_monotributo: str = ""
    ingresos_brutos: str = ""
    inicio_actividades: str = ""

    def __post_init__(self) -> None:
        cuit = validate_cuit(self.cuit)
        if self.punto_venta < 1:
            raise InvoiceValidationError("punto_venta_invalido")
        categoria = validate_monotributo_categoria(self.categoria_monotributo)
        inicio = validate_inicio_actividades(self.inicio_actividades)
        object.__setattr__(self, "cuit", cuit)
        object.__setattr__(self, "razon_social", (self.razon_social or "").strip()[:120])
        object.__setattr__(self, "domicilio", (self.domicilio or "").strip()[:200])
        object.__setattr__(self, "condicion_iva", (self.condicion_iva or "Responsable Monotributo").strip()[:60])
        object.__setattr__(self, "categoria_monotributo", categoria)
        object.__setattr__(self, "ingresos_brutos", (self.ingresos_brutos or "").strip()[:40])
        object.__setattr__(self, "inicio_actividades", inicio)


@dataclass(frozen=True)
class Invoice:
    """Comprobante ARCA emitido (persiste como ``invoices`` + ``invoice_items``)."""

    order_id: str
    punto_venta: int
    tipo_cbte: int
    numero: int
    cae: str
    cae_vto: datetime.date
    fecha: datetime.date
    imp_total: str
    receptor_doc_tipo: int
    receptor_doc_nro: int
    receptor_nombre: str
    condicion_iva: str = "Responsable Monotributo"
    estado: str = ESTADO_APROBADO
    obs: tuple[str, ...] = ()
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    items: tuple[InvoiceItem, ...] = ()

    def __post_init__(self) -> None:
        if not (self.order_id or "").strip():
            raise InvoiceValidationError("order_id_invalido")
        if self.punto_venta < 1:
            raise InvoiceValidationError("punto_venta_invalido")
        if self.numero < 1:
            raise InvoiceValidationError("numero_invalido")
        if len(str(self.cae or "").strip()) != CAE_LENGTH or not str(self.cae or "").strip().isdigit():
            raise InvoiceValidationError("cae_invalido")
        if self.estado not in ESTADOS_VALIDOS:
            raise InvoiceValidationError("estado_invalido")
        validate_importe(self.imp_total)
        validate_doc_receptor(self.receptor_doc_tipo, self.receptor_doc_nro)
        object.__setattr__(self, "cae", str(self.cae).strip())
        object.__setattr__(self, "imp_total", str(Decimal(str(self.imp_total)).quantize(Decimal("0.01"))))
        object.__setattr__(self, "receptor_nombre", (self.receptor_nombre or "").strip()[:120])
