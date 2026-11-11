"""P13 — WSAA: Ticket de Requerimiento de Acceso, firma y cache en memoria.

Flujo (RF-P13-02, decisión D3):

1. ``build_tra`` arma el XML ``loginTicketRequest`` (``service="wsfe"``,
   vigencia 10 minutos, hora de Argentina).
2. ``sign_tra`` lo firma con PKCS#7/CMS SHA-256 y lo devuelve en base64.
3. ``WsaaClient.login`` llama ``loginCms`` y parsea ``token``/``sign``/
   ``expirationTime``.
4. ``WsaaClient.get_ticket`` cachea el TA **en memoria por proceso** (TTL
   11h50m = ~12 h menos 10 minutos de margen). Nunca se escribe a disco.

Ningún error de este módulo incluye paths, tokens, firmas ni contenido del
certificado: la capa API los traduce a 503 ``afip_credential_missing`` /
``afip_unavailable``.
"""

from __future__ import annotations

import base64
import datetime
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7

from domain.invoicing import AfipCredentialMissingError, AfipUnavailableError

TRA_SERVICE = "wsfe"
TRA_VALIDITY = datetime.timedelta(minutes=10)
TOKEN_CACHE_TTL = datetime.timedelta(hours=11, minutes=50)
TOKEN_CACHE_MARGIN = datetime.timedelta(minutes=10)
AR_TZ = datetime.timezone(datetime.timedelta(hours=-3))
_ART_SUFFIX = "-03:00"
_HTTP_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class AfipCredentials:
    """Par clave privada RSA + certificado X.509 en PEM."""

    private_key_pem: bytes
    certificate_pem: bytes


@dataclass(frozen=True)
class AfipTicketAcceso:
    """Ticket de Acceso emitido por WSAA (~12 h de vigencia)."""

    token: str
    sign: str
    expiration: datetime.datetime

    def is_valid(self, now: datetime.datetime) -> bool:
        return now < self.expiration


@dataclass
class _CacheEntry:
    ticket: AfipTicketAcceso
    expires_at: datetime.datetime


_TICKET_CACHE: dict[str, _CacheEntry] = {}


def clear_ticket_cache() -> None:
    """Vacía el cache del proceso (tests y reinicio lógico)."""
    _TICKET_CACHE.clear()


def _read_pem(value: str) -> bytes:
    text = value or ""
    if not text.strip():
        raise AfipCredentialMissingError("afip_credential_missing")
    if "-----BEGIN" in text:
        return text.strip().encode("utf-8") + b"\n"
    try:
        return base64.b64decode(text.strip(), validate=True)
    except (ValueError, TypeError):
        raise AfipCredentialMissingError("afip_credential_missing") from None


def load_credentials(config) -> AfipCredentials:
    """Credenciales desde env (paths o PEM/base64 en variables).

    Los errores no revelan paths ni contenido: ``AfipCredentialMissingError``
    con el código estable ``afip_credential_missing``.
    """
    key_pem = getattr(config, "AFIP_PRIVATE_KEY_PEM", "") or ""
    cert_pem = getattr(config, "AFIP_CERT_PEM", "") or ""
    if key_pem.strip() and cert_pem.strip():
        return AfipCredentials(
            private_key_pem=_read_pem(key_pem),
            certificate_pem=_read_pem(cert_pem),
        )

    key_path = (getattr(config, "AFIP_PRIVATE_KEY_PATH", "") or "").strip()
    cert_path = (getattr(config, "AFIP_CERT_PATH", "") or "").strip()
    if not key_path or not cert_path:
        raise AfipCredentialMissingError("afip_credential_missing")
    try:
        with open(key_path, "rb") as key_file:
            private_key_pem = key_file.read()
        with open(cert_path, "rb") as cert_file:
            certificate_pem = cert_file.read()
    except OSError:
        raise AfipCredentialMissingError("afip_credential_missing") from None
    return AfipCredentials(
        private_key_pem=private_key_pem, certificate_pem=certificate_pem
    )


def _now_ar() -> datetime.datetime:
    return datetime.datetime.now(AR_TZ)


def build_tra(
    service: str = TRA_SERVICE,
    *,
    now: datetime.datetime | None = None,
    unique_id: str | None = None,
) -> bytes:
    """TRA XML (``loginTicketRequest``) con vigencia de 10 minutos."""
    current = (now or _now_ar()).astimezone(AR_TZ).replace(microsecond=0)
    generation = f"{current:%Y-%m-%dT%H:%M:%S}{_ART_SUFFIX}"
    expiration = f"{current + TRA_VALIDITY:%Y-%m-%dT%H:%M:%S}{_ART_SUFFIX}"

    root = ET.Element("loginTicketRequest", {"version": "1.0"})
    header = ET.SubElement(root, "header")
    ET.SubElement(header, "uniqueId").text = unique_id or str(int(time.time()))
    ET.SubElement(header, "generationTime").text = generation
    ET.SubElement(header, "expirationTime").text = expiration
    ET.SubElement(root, "service").text = service
    return ET.tostring(root, xml_declaration=True, encoding="UTF-8")


def sign_tra(tra: bytes, credentials: AfipCredentials) -> str:
    """Firma PKCS#7/CMS (SHA-256) del TRA y lo devuelve en base64."""
    try:
        private_key = serialization.load_pem_private_key(
            credentials.private_key_pem, password=None
        )
        certificate = x509.load_pem_x509_certificate(credentials.certificate_pem)
        signed = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(tra)
            .add_signer(certificate, private_key, hashes.SHA256())
            .sign(
                serialization.Encoding.DER,
                [pkcs7.PKCS7Options.Binary],
            )
        )
    except (ValueError, TypeError, UnsupportedAlgorithm):
        raise AfipCredentialMissingError("afip_credential_missing") from None
    return base64.b64encode(signed).decode("ascii")


def _find_local(root: ET.Element, name: str) -> ET.Element | None:
    """Busca un elemento por nombre local (ignora namespaces XML)."""
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == name:
            return element
    return None


def parse_login_cms(response: str | bytes) -> AfipTicketAcceso:
    """Parsea ``loginCmsReturn`` (token, sign, expirationTime).

    Formato de respuesta de ARCA: un XML con ``loginCmsReturn`` cuyo texto
    es, a su vez, el XML ``loginTicketResponse``. Se ignoran namespaces.
    """
    try:
        raw = response.decode("utf-8") if isinstance(response, bytes) else str(response)
        root = ET.fromstring(raw)
        if _find_local(root, "credentials") is None:
            nested = _find_local(root, "loginCmsReturn")
            if nested is None or not (nested.text or "").strip():
                raise ValueError("loginCmsReturn ausente")
            root = ET.fromstring(nested.text.strip())
        credentials = _find_local(root, "credentials")
        header = _find_local(root, "header")
        if credentials is None or header is None:
            raise ValueError("TA incompleto")
        token = (credentials.findtext("token") or "").strip()
        sign = (credentials.findtext("sign") or "").strip()
        expiration_text = (header.findtext("expirationTime") or "").strip()
        if not token or not sign or not expiration_text:
            raise ValueError("TA incompleto")
        expiration = datetime.datetime.fromisoformat(expiration_text)
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=AR_TZ)
    except (ET.ParseError, ValueError, TypeError):
        raise AfipUnavailableError("afip_unavailable") from None
    return AfipTicketAcceso(token=token, sign=sign, expiration=expiration)


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


class WsaaClient:
    """Cliente WSAA con cache de TA por proceso (clave: URL + servicio)."""

    def __init__(
        self,
        *,
        wsaa_url: str,
        credentials_provider: Callable[[], AfipCredentials],
        service: str = TRA_SERVICE,
        client_factory: Callable[[], object] | None = None,
        clock: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        self._wsaa_url = wsaa_url
        self._credentials_provider = credentials_provider
        self._service = service
        self._clock = clock or _now_ar
        self._client_factory = client_factory or _default_client_factory(wsaa_url)
        self._client: object | None = None

    @property
    def cache_key(self) -> str:
        return f"{self._wsaa_url}|{self._service}"

    def _soap_client(self):
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def login(self) -> AfipTicketAcceso:
        """Nuevo TA (sin mirar el cache)."""
        credentials = self._credentials_provider()
        signed_tra = sign_tra(build_tra(self._service, now=self._clock()), credentials)
        try:
            response = self._soap_client().service.loginCms(in0=signed_tra)
        except AfipUnavailableError:
            raise
        except Exception:  # noqa: BLE001
            raise AfipUnavailableError("afip_unavailable") from None
        return parse_login_cms(response)

    def get_ticket(self, *, force: bool = False) -> AfipTicketAcceso:
        """TA vigente del cache, o uno nuevo si venció / ``force``."""
        now = self._clock()
        if not force:
            entry = _TICKET_CACHE.get(self.cache_key)
            if entry is not None and now < entry.expires_at:
                return entry.ticket
        ticket = self.login()
        expires_at = min(
            now + TOKEN_CACHE_TTL, ticket.expiration - TOKEN_CACHE_MARGIN
        )
        _TICKET_CACHE[self.cache_key] = _CacheEntry(ticket=ticket, expires_at=expires_at)
        return ticket
