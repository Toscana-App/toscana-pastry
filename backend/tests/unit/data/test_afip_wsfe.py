"""T3 — WSFEv1: FECompUltimoAutorizado y FeCAESolicitar (parseo defensivo).

Cero red: los objetos SOAP se simulan con ``SimpleNamespace`` (zeep devuelve
objetos con atributos; también se aceptan dicts).
"""

import datetime
from types import SimpleNamespace

import pytest

from data.invoicing.wsaa import AfipTicketAcceso
from data.invoicing.wsfe import AfipAuth, AfipClient, WsfeClient, build_afip_client
from domain.invoicing import (
    TIPO_CBTE_FACTURA_C,
    AfipUnavailableError,
    AfipWsfeError,
    build_fe_cae_request,
)

CAE_OK = "75123456789012"


def _errores(*pairs):
    return SimpleNamespace(Err=[SimpleNamespace(Code=c, Msg=m) for c, m in pairs])


def _observaciones(*pairs):
    return SimpleNamespace(Obs=[SimpleNamespace(Code=c, Msg=m) for c, m in pairs])


def _ultimo(cbte_nro, errors=None):
    return SimpleNamespace(CbteNro=cbte_nro, Errors=errors)


def _cae(resultado="A", cae=CAE_OK, vto="20261121", obs=None, errors=None):
    detalle = SimpleNamespace(
        Resultado=resultado, CAE=cae, CAEFchVto=vto, Observaciones=obs
    )
    return SimpleNamespace(
        FeDetResp=SimpleNamespace(FECAEDetResponse=[detalle]), Errors=errors
    )


class _FakeWsfeService:
    def __init__(self, ultimate=None, cae_response=None, error=None):
        self.ultimate = ultimate
        self.cae_response = cae_response
        self.error = error
        self.ultimo_calls: list[dict] = []
        self.cae_calls: list[dict] = []

    def FECompUltimoAutorizado(self, **kwargs):
        self.ultimo_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.ultimate

    def FeCAESolicitar(self, **kwargs):
        self.cae_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.cae_response


def _client(service: _FakeWsfeService) -> WsfeClient:
    return WsfeClient(
        wsfe_url="https://wswhomo.example/wsfev1",
        client_factory=lambda: SimpleNamespace(service=service),
    )


AUTH = AfipAuth(token="token", sign="sign", cuit="30123456789")


def _payload(**overrides) -> dict:
    base = {
        "punto_venta": 1,
        "tipo_cbte": TIPO_CBTE_FACTURA_C,
        "numero": 8,
        "imp_total": "5200.00",
        "concepto": 1,
        "doc_tipo": 99,
        "doc_nro": 0,
        "fecha": datetime.date(2026, 11, 11),
    }
    base.update(overrides)
    return build_fe_cae_request(**base)


class TestUltimoAutorizado:
    def test_devuelve_el_ultimo_numero(self):
        service = _FakeWsfeService(ultimate=_ultimo(7))
        assert _client(service).last_authorized(AUTH, 1, TIPO_CBTE_FACTURA_C) == 7

    def test_sin_comprobantes_devuelve_cero(self):
        service = _FakeWsfeService(ultimate=_ultimo(0))
        assert _client(service).last_authorized(AUTH, 1, TIPO_CBTE_FACTURA_C) == 0

    def test_envia_auth_y_punto_de_venta(self):
        service = _FakeWsfeService(ultimate=_ultimo(3))
        _client(service).last_authorized(AUTH, 4, TIPO_CBTE_FACTURA_C)
        call = service.ultimo_calls[0]
        assert call["Auth"] == {
            "Token": "token",
            "Sign": "sign",
            "Cuit": 30123456789,
        }
        assert call["PtoVta"] == 4
        assert call["CbteTipo"] == TIPO_CBTE_FACTURA_C

    def test_acepta_respuesta_tipo_dict(self):
        service = _FakeWsfeService(ultimate={"CbteNro": 12, "Errors": None})
        assert _client(service).last_authorized(AUTH, 1, TIPO_CBTE_FACTURA_C) == 12

    def test_errores_de_arca_se_propagan(self):
        service = _FakeWsfeService(ultimate=_ultimo(0, errors=_errores((600, "Punto de venta inactivo"))))
        with pytest.raises(AfipWsfeError) as exc:
            _client(service).last_authorized(AUTH, 1, TIPO_CBTE_FACTURA_C)
        assert exc.value.observaciones == ["600: Punto de venta inactivo"]

    def test_caida_de_red_saneada(self):
        service = _FakeWsfeService(error=RuntimeError("token=SECRETO /run/secrets/key.pem"))
        with pytest.raises(AfipUnavailableError) as exc:
            _client(service).last_authorized(AUTH, 1, TIPO_CBTE_FACTURA_C)
        assert str(exc.value) == "afip_unavailable"
        assert "SECRETO" not in str(exc.value)


class TestSolicitarCae:
    def test_aprobada_devuelve_cae_y_vencimiento(self):
        service = _FakeWsfeService(cae_response=_cae())
        result = _client(service).request_cae(AUTH, _payload())
        assert result.resultado == "A"
        assert result.cae == CAE_OK
        assert result.cae_vto == datetime.date(2026, 11, 21)
        assert result.observaciones == ()

    def test_rechazada_devuelve_resultado_y_observaciones(self):
        service = _FakeWsfeService(
            cae_response=_cae(
                resultado="R",
                cae="",
                vto="",
                obs=_observaciones((10015, "Fecha fuera de rango"), (10016, "Importe invalido")),
            )
        )
        result = _client(service).request_cae(AUTH, _payload())
        assert result.resultado == "R"
        assert result.observaciones == (
            "10015: Fecha fuera de rango",
            "10016: Importe invalido",
        )
        assert result.cae_vto is None

    def test_aprobada_sin_cae_es_error(self):
        service = _FakeWsfeService(cae_response=_cae(cae=""))
        with pytest.raises(AfipWsfeError):
            _client(service).request_cae(AUTH, _payload())

    def test_respuesta_sin_detalle_es_error(self):
        service = _FakeWsfeService(cae_response=SimpleNamespace(FeDetResp=None, Errors=None))
        with pytest.raises(AfipWsfeError):
            _client(service).request_cae(AUTH, _payload())

    def test_errores_globales_se_propagan(self):
        service = _FakeWsfeService(
            cae_response=SimpleNamespace(
                FeDetResp=None, Errors=_errores((1000, "Servicio no disponible"))
            )
        )
        with pytest.raises(AfipWsfeError) as exc:
            _client(service).request_cae(AUTH, _payload())
        assert exc.value.observaciones == ["1000: Servicio no disponible"]

    def test_envia_el_payload_construido(self):
        service = _FakeWsfeService(cae_response=_cae())
        payload = _payload()
        _client(service).request_cae(AUTH, payload)
        assert service.cae_calls[0]["FeCAEReq"] == payload
        assert service.cae_calls[0]["Auth"]["Cuit"] == 30123456789

    def test_fecha_de_vencimiento_invalida_es_error(self):
        service = _FakeWsfeService(cae_response=_cae(vto="20261340"))
        with pytest.raises(AfipWsfeError):
            _client(service).request_cae(AUTH, _payload())


class _FakeWsaa:
    def __init__(self, ticket: AfipTicketAcceso) -> None:
        self.ticket = ticket
        self.calls = 0

    def get_ticket(self, *, force: bool = False) -> AfipTicketAcceso:
        self.calls += 1
        return self.ticket


class _FakeWsfe:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def last_authorized(self, auth, punto_venta, tipo_cbte):
        self.calls.append((auth, punto_venta, tipo_cbte))
        return 41

    def request_cae(self, auth, request):
        self.calls.append((auth, request))
        from domain.invoicing import AfipCaeResult

        return AfipCaeResult(
            resultado="A",
            cae=CAE_OK,
            cae_vto=datetime.date(2026, 11, 21),
        )


class TestAfipClient:
    def _ticket(self) -> AfipTicketAcceso:
        return AfipTicketAcceso(
            token="tk",
            sign="sg",
            expiration=datetime.datetime(2026, 11, 11, 22, 0),
        )

    async def test_last_authorized_usa_el_ticket_y_el_cuit(self):
        wsaa = _FakeWsaa(self._ticket())
        wsfe = _FakeWsfe()
        client = AfipClient(wsaa=wsaa, wsfe=wsfe)

        assert await client.last_authorized(cuit="30123456789", punto_venta=3, tipo_cbte=11) == 41
        auth, punto_venta, tipo = wsfe.calls[0]
        assert auth.token == "tk"
        assert auth.sign == "sg"
        assert auth.cuit == "30123456789"
        assert punto_venta == 3
        assert tipo == 11
        assert wsaa.calls == 1

    async def test_request_cae_delega(self):
        wsaa = _FakeWsaa(self._ticket())
        wsfe = _FakeWsfe()
        client = AfipClient(wsaa=wsaa, wsfe=wsfe)
        payload = _payload()

        result = await client.request_cae(cuit="30123456789", request=payload)

        assert result.cae == CAE_OK
        assert wsfe.calls[0][1] == payload


class _FakeConfig:
    AFIP_ENV = "homo"
    AFIP_WSAA_URL = ""
    AFIP_WSFE_URL = ""
    AFIP_PRIVATE_KEY_PATH = ""
    AFIP_CERT_PATH = ""
    AFIP_PRIVATE_KEY_PEM = ""
    AFIP_CERT_PEM = ""

    @property
    def afip_wsaa_url(self):
        return "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL"

    @property
    def afip_wsfe_url(self):
        return "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"


def test_build_afip_client_no_toca_disco_ni_red():
    client = build_afip_client(_FakeConfig())
    assert isinstance(client, AfipClient)
