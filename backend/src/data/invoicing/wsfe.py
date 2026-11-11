"""P13 — WSFEv1: numeración y solicitud de CAE (Factura C).

Llamadas usadas (``docs/specs/p13_invoicing.md`` RF-P13-02):

- ``FECompUltimoAutorizado(Auth, PtoVta, CbteTipo)`` → ``CbteNro`` (último
  autorizado; 0 si el punto de venta no emitió nada) y ``Errors``.
- ``FeCAESolicitar(Auth, FeCAEReq)`` → ``FeDetResp.FECAEDetResponse[0]`` con
  ``Resultado`` (A/R), ``CAE``, ``CAEFchVto`` y ``Observaciones.Obs[]``;
  ``Errors`` a nivel raíz para fallas del servicio.

``Auth`` viaja como ``{Token, Sign, Cuit}``. El payload ``FeCAEReq`` lo arma
``domain.invoicing.build_fe_cae_request`` (ImpTotal en pesos, no centavos).

El parseo es defensivo: zeep devuelve objetos con atributos, pero también se
aceptan dicts (``raw_response``). Ningún error expone token, sign, paths ni
contenido de certificados.
"""

from __future__ import annotations

import asyncio
import datetime
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from data.invoicing.wsaa import WsaaClient
from domain.invoicing import (
    AfipCaeResult,
    AfipUnavailableError,
    AfipWsfeError,
    InvoiceValidationError,
    normalize_cae,
    parse_arca_fecha,
)

_HTTP_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class AfipAuth:
    """Credenciales de invocación de WSFEv1 (token WSAA + CUIT emisor)."""

    token: str
    sign: str
    cuit: str

    def as_dict(self) -> dict:
        return {"Token": self.token, "Sign": self.sign, "Cuit": int(self.cuit)}


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _messages(container: Any, item_name: str) -> list[str]:
    """``"<Code>: <Msg>"`` de ``Errors.Err`` / ``Observaciones.Obs``."""
    messages: list[str] = []
    for item in _as_list(_get(container, item_name)):
        code = _get(item, "Code")
        msg = _get(item, "Msg")
        if code is None and msg is None:
            continue
        messages.append(f"{code}: {msg}")
    return messages


def _default_client_factory(wsdl_url: str):
    """Cliente zeep perezoso: el WSDL se baja en la primera llamada."""
    from zeep import Client
    from zeep.transports import Transport

    from data.invoicing.ssl_session import get_afip_session

    def _build():
        return Client(
            wsdl=wsdl_url,
            transport=Transport(
                session=get_afip_session(), timeout=_HTTP_TIMEOUT_SECONDS
            ),
        )

    return _build


class WsfeClient:
    """Wrapper sincrónico de WSFEv1 (se invoca desde ``asyncio.to_thread``)."""

    def __init__(
        self,
        *,
        wsfe_url: str,
        client_factory: Callable[[], object] | None = None,
    ) -> None:
        self._wsfe_url = wsfe_url
        self._client_factory = client_factory or _default_client_factory(wsfe_url)
        self._client: object | None = None

    def _soap_client(self):
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _call(self, method: str, **kwargs):
        try:
            return getattr(self._soap_client().service, method)(**kwargs)
        except (AfipUnavailableError, AfipWsfeError):
            raise
        except Exception:  # noqa: BLE001
            raise AfipUnavailableError("afip_unavailable") from None

    def last_authorized(self, auth: AfipAuth, punto_venta: int, tipo_cbte: int) -> int:
        """Último comprobante autorizado para ``(punto_venta, tipo_cbte)``."""
        response = self._call(
            "FECompUltimoAutorizado",
            Auth=auth.as_dict(),
            PtoVta=punto_venta,
            CbteTipo=tipo_cbte,
        )
        errors = _messages(_get(response, "Errors"), "Err")
        if errors:
            raise AfipWsfeError("afip_wsfe_error", errors)
        try:
            return int(_get(response, "CbteNro") or 0)
        except (TypeError, ValueError):
            raise AfipWsfeError(
                "afip_wsfe_error", ["respuesta de numeración ilegible"]
            ) from None

    def request_cae(self, auth: AfipAuth, request: dict) -> AfipCaeResult:
        """``FeCAESolicitar`` de un comprobante (una línea)."""
        response = self._call("FeCAESolicitar", Auth=auth.as_dict(), FeCAEReq=request)
        errors = _messages(_get(response, "Errors"), "Err")
        if errors:
            raise AfipWsfeError("afip_wsfe_error", errors)

        detalle = (_as_list(_get(_get(response, "FeDetResp"), "FECAEDetResponse")) or [None])[0]
        if detalle is None:
            raise AfipWsfeError("afip_wsfe_error", ["respuesta sin detalle de comprobante"])

        resultado = str(_get(detalle, "Resultado") or "").strip().upper()
        observaciones = tuple(_messages(_get(detalle, "Observaciones"), "Obs"))
        cae_raw = _get(detalle, "CAE")
        vto_raw = _get(detalle, "CAEFchVto")

        cae = ""
        if cae_raw not in (None, ""):
            try:
                cae = normalize_cae(cae_raw)
            except InvoiceValidationError:
                raise AfipWsfeError("afip_wsfe_error", ["CAE ilegible"]) from None

        cae_vto: datetime.date | None = None
        if vto_raw not in (None, ""):
            try:
                cae_vto = parse_arca_fecha(vto_raw)
            except InvoiceValidationError:
                raise AfipWsfeError(
                    "afip_wsfe_error", ["vencimiento de CAE ilegible"]
                ) from None

        if resultado == "A" and not cae:
            raise AfipWsfeError("afip_wsfe_error", ["comprobante sin CAE"])
        return AfipCaeResult(
            resultado=resultado or "R",
            cae=cae,
            cae_vto=cae_vto,
            observaciones=observaciones,
        )


class AfipClient:
    """Fachada async: TA cacheado (WSAA) + llamadas WSFEv1 en un thread."""

    def __init__(self, *, wsaa: WsaaClient, wsfe: WsfeClient) -> None:
        self._wsaa = wsaa
        self._wsfe = wsfe

    def _auth(self, cuit: str) -> AfipAuth:
        ticket = self._wsaa.get_ticket()
        return AfipAuth(token=ticket.token, sign=ticket.sign, cuit=cuit)

    async def last_authorized(
        self, *, cuit: str, punto_venta: int, tipo_cbte: int
    ) -> int:
        def _run() -> int:
            return self._wsfe.last_authorized(self._auth(cuit), punto_venta, tipo_cbte)

        return await asyncio.to_thread(_run)

    async def request_cae(self, *, cuit: str, request: dict) -> AfipCaeResult:
        def _run() -> AfipCaeResult:
            return self._wsfe.request_cae(self._auth(cuit), request)

        return await asyncio.to_thread(_run)


def build_afip_client(config=None) -> AfipClient:
    """Cliente configurado por entorno (sin leer disco ni abrir red todavía)."""
    from core.config import settings as app_settings
    from data.invoicing.wsaa import load_credentials

    config = config or app_settings
    wsaa = WsaaClient(
        wsaa_url=config.afip_wsaa_url,
        credentials_provider=lambda: load_credentials(config),
    )
    wsfe = WsfeClient(wsfe_url=config.afip_wsfe_url)
    return AfipClient(wsaa=wsaa, wsfe=wsfe)
