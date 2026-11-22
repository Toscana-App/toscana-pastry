"""T3 — Sesión HTTP para AFIP (SSL debilitado sólo en el nivel de cifrado).

AFIP usa claves Diffie-Hellman débiles; sin bajar ``SECLEVEL`` la conexión
falla con ``DH_KEY_TOO_SMALL``. La verificación del certificado del servidor
se mantiene activa (no se acepta un TLS sin validar).
"""

import ssl

from data.invoicing.ssl_session import (
    AFIP_CIPHERS,
    AfipSSLAdapter,
    create_afip_ssl_context,
    get_afip_session,
)


def test_cipher_string_lowers_security_level():
    assert "SECLEVEL=1" in AFIP_CIPHERS


def test_ssl_context_keeps_certificate_verification():
    context = create_afip_ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_ssl_context_accepts_weak_dh_suites():
    context = create_afip_ssl_context()
    names = {cipher["name"] for cipher in context.get_ciphers()}
    assert any(name.startswith("DHE-RSA-") for name in names)


def test_session_mounts_afip_adapter():
    session = get_afip_session()
    adapter = session.get_adapter("https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL")
    assert isinstance(adapter, AfipSSLAdapter)


def test_session_is_fresh_per_call():
    assert get_afip_session() is not get_afip_session()
