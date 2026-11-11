"""Tests del renderer de Factura C ARCA (endpoint POST /render/invoice-arca).

Cubre:
- funciones puras del QR RG 4291/2018 (``build_qr_payload`` / ``build_qr_url``)
  con valores exactos esperados (payload fijo → base64 literal + URL exacta);
- el renderer ReportLab (bytes %PDF, contenido textual del comprobante,
  CUIT normalizado, items vacíos, paginación de detalle);
- el endpoint HTTP (200 application/pdf + filename correcto, 422 ante
  payload inválido: CAE de 13 dígitos, doc_tipo fuera de {99, 80, 86}).
"""
import base64
import io
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from pdfgenerator.renderers.invoice_arca import (
    InvoiceArcaRequest,
    build_qr_payload,
    build_qr_url,
    normalize_cuit,
    render_invoice_arca_pdf,
)
from pdfgenerator.server import app

client = TestClient(app)

# ── QR: valores fijos y base64 literal esperado (RG 4291/2018) ──────────

QR_JSON = (
    '{"ver":1,"fecha":"2026-11-05","cuit":"30123456789","ptoVta":1,'
    '"tipoCmp":11,"nroCmp":42,"importe":3100.5,"moneda":0,"ctz":3,'
    '"tipoDocRec":86,"nroDocRec":12345678,"tipoCodAut":"E",'
    '"codAut":"12345678901234"}'
)
QR_B64 = (
    "eyJ2ZXIiOjEsImZl"
    "Y2hhIjoiMjAyNi0x"
    "MS0wNSIsImN1aXQi"
    "OiIzMDEyMzQ1Njc4"
    "OSIsInB0b1Z0YSI6"
    "MSwidGlwb0NtcCI6"
    "MTEsIm5yb0NtcCI6"
    "NDIsImltcG9ydGUi"
    "OjMxMDAuNSwibW9u"
    "ZWRhIjowLCJjdHoi"
    "OjMsInRpcG9Eb2NS"
    "ZWMiOjg2LCJucm9E"
    "b2NSZWMiOjEyMzQ1"
    "Njc4LCJ0aXBvQ29k"
    "QXV0IjoiRSIsImNv"
    "ZEF1dCI6IjEyMzQ1"
    "Njc4OTAxMjM0In0="
)
QR_URL = "https://www.afip.gob.ar/fe/qr/?p=" + QR_B64


def _fixed_payload_kwargs() -> dict:
    return {
        "fecha": date(2026, 11, 5),
        "cuit": "30-12345678-9",
        "punto_venta": 1,
        "tipo_cbte": 11,
        "numero": 42,
        "importe": Decimal("3100.50"),
        "doc_tipo": 86,
        "doc_nro": 12345678,
        "cae": "12345678901234",
    }


# ── build_qr_payload / build_qr_url (puras, sin ReportLab) ──────────────


class TestBuildQrPayload:
    def test_payload_exacto_rg_4291(self):
        payload = build_qr_payload(**_fixed_payload_kwargs())
        assert payload == {
            "ver": 1,
            "fecha": "2026-11-05",
            "cuit": "30123456789",
            "ptoVta": 1,
            "tipoCmp": 11,
            "nroCmp": 42,
            "importe": 3100.5,
            "moneda": 0,
            "ctz": 3,
            "tipoDocRec": 86,
            "nroDocRec": 12345678,
            "tipoCodAut": "E",
            "codAut": "12345678901234",
        }

    def test_cuit_se_lleva_sin_guiones(self):
        payload = build_qr_payload(**_fixed_payload_kwargs())
        assert payload["cuit"] == "30123456789"

    def test_importe_se_cuadra_a_2_decimales(self):
        kwargs = _fixed_payload_kwargs()
        kwargs["importe"] = Decimal("10.004")
        payload = build_qr_payload(**kwargs)
        assert payload["importe"] == 10.0


class TestBuildQrUrl:
    def test_url_exacta_con_b64_literal(self):
        payload = build_qr_payload(**_fixed_payload_kwargs())
        assert build_qr_url(payload) == QR_URL

    def test_b64_literal_roundtrip_al_json_canonico(self):
        decoded = base64.b64decode(QR_B64).decode("utf-8")
        assert decoded == QR_JSON


class TestNormalizeCuit:
    def test_con_y_sin_guiones(self):
        assert normalize_cuit("30-12345678-9") == "30-12345678-9"
        assert normalize_cuit("30123456789") == "30-12345678-9"

    @pytest.mark.parametrize("bad", ["123", "301234567890", "abc"])
    def test_cuit_invalido(self, bad):
        with pytest.raises(ValueError):
            normalize_cuit(bad)


# ── Renderer ReportLab ──────────────────────────────────────────────────


def _payload_body(**cb_overrides) -> dict:
    cb = {
        "punto_venta": 1,
        "tipo_cbte": 11,
        "numero": 42,
        "fecha": "2026-11-05",
        "cae": "12345678901234",
        "cae_vto": "2026-11-15",
        "imp_total": "3100.50",
        "receptor": {
            "doc_tipo": 86,
            "doc_nro": 12345678,
            "doc_nombre": "Juan Pérez",
        },
        "items": [
            {
                "descripcion": "Torta de Limón 20 porciones",
                "cantidad": 1,
                "precio_unit": "3100.50",
            },
        ],
    }
    cb.update(cb_overrides)
    return {
        "emisor": {
            "cuit": "30-12345678-9",
            "razon_social": "Pastelería Toscana",
            "domicilio": "Av. Siempreviva 7420, Villa Giardino",
            "condicion_iva": "Responsable Monotributo",
            "categoria_monotributo": "G",
            "ingresos_brutos": "Exento",
            "inicio_actividades": "01/03/2024",
        },
        "comprobante": cb,
    }


def _req(**cb_overrides) -> InvoiceArcaRequest:
    return InvoiceArcaRequest.model_validate(_payload_body(**cb_overrides))


def _extract(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text.replace("\ufb01", "fi")


class TestRenderInvoiceArcaPdf:
    def test_pdf_valido_y_contenido_del_comprobante(self):
        pdf = render_invoice_arca_pdf(_req())
        assert pdf[:4] == b"%PDF"
        text = _extract(pdf)
        assert "ORIGINAL" in text
        assert "FACTURA C" in text
        assert "30-12345678-9" in text  # CUIT del emisor, con guiones
        assert "12345678901234" in text  # CAE
        assert "Pastelería Toscana" in text  # razón social
        assert "RECEPTOR" in text
        assert "Juan Pérez" in text  # receptor
        assert "DNI:" in text  # doc_tipo 86 → etiqueta DNI
        assert "$3100,50" in text  # importe es-AR sin separador de miles
        assert "00000042" in text  # número de comprobante
        assert "05/11/2026" in text  # fecha de emisión dd/mm/aaaa
        assert "15/11/2026" in text  # vencimiento del CAE
        assert "Vto. CAE" in text
        assert "www.afip.gob.ar/fe/qr/" in text  # URL bajo el QR

    def test_items_vacios_renderiza_bloque_vacio(self):
        pdf = render_invoice_arca_pdf(_req(items=[]))
        text = _extract(pdf)
        assert "Sin detalle de operaciones" in text
        assert "$3100,50" in text

    def test_cuit_sin_guiones_se_imprime_con_guiones(self):
        body = _payload_body()
        body["emisor"]["cuit"] = "30123456789"
        pdf = render_invoice_arca_pdf(InvoiceArcaRequest.model_validate(body))
        assert "30-12345678-9" in _extract(pdf)

    def test_receptor_consumidor_final(self):
        body = _payload_body(
            receptor={"doc_tipo": 99, "doc_nro": 0, "doc_nombre": "Consumidor Final"},
        )
        text = _extract(
            render_invoice_arca_pdf(InvoiceArcaRequest.model_validate(body))
        )
        # doc label + condición IVA (el nombre del receptor también lo dice)
        assert text.count("Consumidor Final") >= 2
        assert "DNI:" not in text

    def test_muchos_items_paginan_y_totales_en_ultima_pagina(self):
        items = [
            {"descripcion": f"Producto {i}", "cantidad": 1, "precio_unit": "10.00"}
            for i in range(60)
        ]
        body = _payload_body(items=items, imp_total="600.00")
        pdf = render_invoice_arca_pdf(InvoiceArcaRequest.model_validate(body))
        reader = PdfReader(io.BytesIO(pdf))
        assert len(reader.pages) > 1
        full_text = _extract(pdf)
        assert "Producto 59" in full_text
        last_page = reader.pages[-1].extract_text() or ""
        assert "$600.00".replace(".", ",") in last_page  # TOTAL en la última página


# ── Endpoint POST /render/invoice-arca ──────────────────────────────────


class TestRenderInvoiceArcaEndpoint:
    def test_ok_pdf_content_type_y_filename(self):
        r = client.post("/render/invoice-arca", json=_payload_body())
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
        assert (
            'filename="FACTURA_1-00000042.pdf"' in r.headers["content-disposition"]
        )
        text = _extract(r.content)
        assert "30-12345678-9" in text
        assert "12345678901234" in text
        assert "Pastelería Toscana" in text
        assert "Juan Pérez" in text
        assert "$3100,50" in text
        assert "FACTURA C" in text

    def test_items_vacios_ok(self):
        r = client.post("/render/invoice-arca", json=_payload_body(items=[]))
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content.startswith(b"%PDF")

    def test_cae_de_13_digitos_rechazado(self):
        r = client.post("/render/invoice-arca", json=_payload_body(cae="1234567890123"))
        assert r.status_code == 422

    def test_cae_de_15_digitos_rechazado(self):
        r = client.post(
            "/render/invoice-arca", json=_payload_body(cae="123456789012345")
        )
        assert r.status_code == 422

    def test_doc_tipo_invalido_rechazado(self):
        body = _payload_body(
            receptor={"doc_tipo": 88, "doc_nro": 0, "doc_nombre": "Nadie"}
        )
        r = client.post("/render/invoice-arca", json=body)
        assert r.status_code == 422

    def test_imp_total_mal_formado_rechazado(self):
        r = client.post("/render/invoice-arca", json=_payload_body(imp_total="3100.5"))
        assert r.status_code == 422
