"""P13 — Sesión HTTP compatible con los servidores de ARCA.

ARCA publica sus web services detrás de configuraciones TLS antiguas
(claves Diffie-Hellman cortas): con el nivel de seguridad por defecto de
OpenSSL la conexión muere con ``DH_KEY_TOO_SMALL``. Se baja ``SECLEVEL`` a 1
—lo mínimo necesario— manteniendo la validación del certificado del
servidor y el chequeo de hostname.
"""

import ssl

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

AFIP_CIPHERS = "DEFAULT:@SECLEVEL=1"


def create_afip_ssl_context() -> ssl.SSLContext:
    """Contexto TLS con suites débiles habilitadas y verificación intacta."""
    context = create_urllib3_context()
    context.set_ciphers(AFIP_CIPHERS)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


class AfipSSLAdapter(HTTPAdapter):
    """Adapter que usa el contexto TLS tolerante de ARCA."""

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = create_afip_ssl_context()
        return super().init_poolmanager(*args, **kwargs)


def get_afip_session() -> requests.Session:
    """Sesión requests lista para WSAA/WSFEv1 (una por cliente)."""
    session = requests.Session()
    session.mount("https://", AfipSSLAdapter())
    return session
