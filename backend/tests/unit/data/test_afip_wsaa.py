"""T3 — WSAA: TRA, firma PKCS#7/CMS y cache de Ticket de Acceso (D3).

Cero red: el cliente SOAP se inyecta con un fake.
"""

import base64
import datetime
import shutil
import subprocess
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from data.invoicing.wsaa import (
    TOKEN_CACHE_TTL,
    AfipCredentials,
    WsaaClient,
    build_tra,
    clear_ticket_cache,
    load_credentials,
    sign_tra,
)
from domain.invoicing import AfipCredentialMissingError, AfipUnavailableError

AR_TZ = datetime.timezone(datetime.timedelta(hours=-3))
NOW = datetime.datetime(2026, 11, 11, 10, 30, 0, tzinfo=AR_TZ)

LOGIN_OK = """<?xml version="1.0" encoding="UTF-8"?>
<loginCmsResponse xmlns="http://wsaa.view.sua.dvadac.desein.afip.gov">
  <loginCmsReturn>&lt;?xml version="1.0" encoding="UTF-8"?&gt;
&lt;loginTicketResponse version="1.0"&gt;
  &lt;header&gt;
    &lt;source&gt;CN=wsaahomo, O=AFIP, C=AR&lt;/source&gt;
    &lt;destination&gt;CN=toscana, O=AFIP, C=AR&lt;/destination&gt;
    &lt;uniqueId&gt;123456&lt;/uniqueId&gt;
    &lt;generationTime&gt;2026-11-11T10:30:00.000-03:00&lt;/generationTime&gt;
    &lt;expirationTime&gt;2026-11-11T22:30:00.000-03:00&lt;/expirationTime&gt;
  &lt;/header&gt;
  &lt;credentials&gt;
    &lt;token&gt;TOKEN-DE-PRUEBA&lt;/token&gt;
    &lt;sign&gt;FIRMA-DE-PRUEBA&lt;/sign&gt;
  &lt;/credentials&gt;
&lt;/loginTicketResponse&gt;</loginCmsReturn>
</loginCmsResponse>"""


def _make_credentials(tmp_path) -> AfipCredentials:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "toscana-test")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    (tmp_path / "private_key.pem").write_bytes(key_pem)
    (tmp_path / "certificate.pem").write_bytes(cert_pem)
    return AfipCredentials(private_key_pem=key_pem, certificate_pem=cert_pem)


class _FakeLoginService:
    def __init__(self, response: str = LOGIN_OK, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[str] = []

    def loginCms(self, in0=None):
        self.calls.append(in0)
        if self.error is not None:
            raise self.error
        return self.response


def _fake_client(service: _FakeLoginService):
    return SimpleNamespace(service=service)


class TestTra:
    def test_declara_servicio_y_header(self):
        tra = build_tra(now=NOW, unique_id="1700000000")
        root = ET.fromstring(tra)
        assert root.tag == "loginTicketRequest"
        assert root.get("version") == "1.0"
        assert root.findtext("header/uniqueId") == "1700000000"
        assert root.findtext("service") == "wsfe"

    def test_ventana_de_diez_minutos(self):
        tra = build_tra(now=NOW)
        root = ET.fromstring(tra)
        generation = root.findtext("header/generationTime")
        expiration = root.findtext("header/expirationTime")
        assert generation == "2026-11-11T10:30:00-03:00"
        assert expiration == "2026-11-11T10:40:00-03:00"

    def test_unique_id_por_defecto_es_numerico(self):
        root = ET.fromstring(build_tra(now=NOW))
        assert root.findtext("header/uniqueId").isdigit()


class TestFirma:
    def test_firma_es_un_cms_verificable(self, tmp_path):
        credentials = _make_credentials(tmp_path)
        tra = build_tra(now=NOW)
        signed = sign_tra(tra, credentials)

        der = base64.b64decode(signed, validate=True)
        assert len(pkcs7.load_der_pkcs7_certificates(der)) == 1
        assert tra in der

        if shutil.which("openssl") is None:
            pytest.skip("openssl no disponible para verificar la firma")
        signature = tmp_path / "tra.p7"
        signature.write_bytes(der)
        extracted = tmp_path / "tra.xml"
        result = subprocess.run(
            [
                "openssl",
                "smime",
                "-verify",
                "-inform",
                "DER",
                "-in",
                str(signature),
                "-noverify",
                "-out",
                str(extracted),
            ],
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr.decode()
        assert extracted.read_bytes() == tra

    def test_firma_usa_el_certificado_propio(self, tmp_path):
        credentials = _make_credentials(tmp_path)
        der = base64.b64decode(sign_tra(b"<x/>", credentials), validate=True)
        certificate = pkcs7.load_der_pkcs7_certificates(der)[0]
        expected = x509.load_pem_x509_certificate(credentials.certificate_pem)
        assert certificate.fingerprint(hashes.SHA256()) == expected.fingerprint(hashes.SHA256())


class TestCredentials:
    def test_carga_desde_paths(self, tmp_path):
        credentials = _make_credentials(tmp_path)
        config = SimpleNamespace(
            AFIP_PRIVATE_KEY_PATH=str(tmp_path / "private_key.pem"),
            AFIP_CERT_PATH=str(tmp_path / "certificate.pem"),
            AFIP_PRIVATE_KEY_PEM="",
            AFIP_CERT_PEM="",
        )
        loaded = load_credentials(config)
        assert loaded.private_key_pem == credentials.private_key_pem
        assert loaded.certificate_pem == credentials.certificate_pem

    def test_carga_desde_pem(self, tmp_path):
        credentials = _make_credentials(tmp_path)
        config = SimpleNamespace(
            AFIP_PRIVATE_KEY_PATH="",
            AFIP_CERT_PATH="",
            AFIP_PRIVATE_KEY_PEM=credentials.private_key_pem.decode(),
            AFIP_CERT_PEM=credentials.certificate_pem.decode(),
        )
        loaded = load_credentials(config)
        assert loaded.private_key_pem == credentials.private_key_pem
        assert loaded.certificate_pem == credentials.certificate_pem

    def test_carga_desde_pem_base64(self, tmp_path):
        credentials = _make_credentials(tmp_path)
        config = SimpleNamespace(
            AFIP_PRIVATE_KEY_PATH="",
            AFIP_CERT_PATH="",
            AFIP_PRIVATE_KEY_PEM=base64.b64encode(credentials.private_key_pem).decode(),
            AFIP_CERT_PEM=base64.b64encode(credentials.certificate_pem).decode(),
        )
        loaded = load_credentials(config)
        assert loaded.private_key_pem == credentials.private_key_pem

    def test_faltantes_no_filtran_paths(self):
        config = SimpleNamespace(
            AFIP_PRIVATE_KEY_PATH="/run/secrets/privada.pem",
            AFIP_CERT_PATH="",
            AFIP_PRIVATE_KEY_PEM="",
            AFIP_CERT_PEM="",
        )
        with pytest.raises(AfipCredentialMissingError) as exc:
            load_credentials(config)
        assert "privada.pem" not in str(exc.value)
        assert str(exc.value) == "afip_credential_missing"

    def test_archivo_inexistente_no_filtra_path(self):
        config = SimpleNamespace(
            AFIP_PRIVATE_KEY_PATH="/run/secrets/privada.pem",
            AFIP_CERT_PATH="/run/secrets/certificado.pem",
            AFIP_PRIVATE_KEY_PEM="",
            AFIP_CERT_PEM="",
        )
        with pytest.raises(AfipCredentialMissingError) as exc:
            load_credentials(config)
        assert "/run/secrets" not in str(exc.value)


class TestLogin:
    def test_parsea_token_sign_y_expiracion(self, tmp_path):
        service = _FakeLoginService()
        credentials = _make_credentials(tmp_path)
        client = WsaaClient(
            wsaa_url="https://wsaahomo.example/LoginCms",
            credentials_provider=lambda: credentials,
            client_factory=lambda: _fake_client(service),
            clock=lambda: NOW,
        )

        ticket = client.login()

        assert ticket.token == "TOKEN-DE-PRUEBA"
        assert ticket.sign == "FIRMA-DE-PRUEBA"
        assert ticket.expiration == datetime.datetime(2026, 11, 11, 22, 30, tzinfo=AR_TZ)
        assert len(service.calls) == 1
        assert base64.b64decode(service.calls[0].encode(), validate=True)

    def test_error_de_red_saneado(self, tmp_path):
        credentials = _make_credentials(tmp_path)
        client = WsaaClient(
            wsaa_url="https://wsaahomo.example/LoginCms",
            credentials_provider=lambda: credentials,
            client_factory=lambda: _fake_client(
                _FakeLoginService(error=RuntimeError("token=A1B2C3 /run/secrets/privada.pem"))
            ),
            clock=lambda: NOW,
        )
        with pytest.raises(AfipUnavailableError) as exc:
            client.login()
        assert str(exc.value) == "afip_unavailable"
        assert "A1B2C3" not in str(exc.value)
        assert "privada.pem" not in str(exc.value)

    def test_respuesta_ilegible_saneada(self, tmp_path):
        credentials = _make_credentials(tmp_path)
        client = WsaaClient(
            wsaa_url="https://wsaahomo.example/LoginCms",
            credentials_provider=lambda: credentials,
            client_factory=lambda: _fake_client(_FakeLoginService(response="<html>error</html>")),
            clock=lambda: NOW,
        )
        with pytest.raises(AfipUnavailableError):
            client.login()


class TestCacheToken:
    def _client(self, tmp_path, service, clock):
        credentials = _make_credentials(tmp_path)
        return WsaaClient(
            wsaa_url="https://wsaahomo.example/LoginCms",
            credentials_provider=lambda: credentials,
            client_factory=lambda: _fake_client(service),
            clock=clock,
        )

    def test_reusa_el_ticket(self, tmp_path):
        clear_ticket_cache()
        service = _FakeLoginService()
        clock = lambda: NOW
        client = self._client(tmp_path, service, clock)

        first = client.get_ticket()
        second = client.get_ticket()

        assert first is second
        assert len(service.calls) == 1

    def test_expira_al_pasar_el_ttl(self, tmp_path):
        clear_ticket_cache()
        service = _FakeLoginService()
        current = [NOW]
        client = self._client(tmp_path, service, lambda: current[0])

        client.get_ticket()
        current[0] = NOW + TOKEN_CACHE_TTL - datetime.timedelta(minutes=1)
        client.get_ticket()
        assert len(service.calls) == 1

        current[0] = NOW + TOKEN_CACHE_TTL + datetime.timedelta(seconds=1)
        client.get_ticket()
        assert len(service.calls) == 2

    def test_force_ignora_el_cache(self, tmp_path):
        clear_ticket_cache()
        service = _FakeLoginService()
        client = self._client(tmp_path, service, lambda: NOW)

        client.get_ticket()
        client.get_ticket(force=True)
        assert len(service.calls) == 2

    def test_cache_es_por_proceso_y_se_limpia(self, tmp_path):
        clear_ticket_cache()
        service = _FakeLoginService()
        client = self._client(tmp_path, service, lambda: NOW)
        client.get_ticket()
        clear_ticket_cache()
        client.get_ticket()
        assert len(service.calls) == 2
