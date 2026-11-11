"""T1 — Dominio de comprobantes ARCA: reglas puras (sin I/O).

Cubre p13_invoicing.md RF-P13-01/02 y D3/D8: concepto/periodo de servicio,
DocTipo receptor, CAE de 14 dígitos, ventana de fechas ARCA, importe > 0,
un comprobante por pedido, número consecutivo, saneamiento de obs y
payload FeCAESolicitar.
"""

import datetime
from decimal import Decimal

import pytest

from domain.invoicing import (
    CONCEPTO_AMBOS,
    CONCEPTO_PRODUCTOS,
    CONCEPTO_SERVICIOS,
    DOC_TIPO_CONSUMIDOR_FINAL,
    DOC_TIPO_CUIT,
    DOC_TIPO_DNI,
    ESTADO_APROBADO,
    ESTADO_RECHAZADO,
    TIPO_CBTE_FACTURA_C,
    AfipCredentialMissingError,
    AfipUnavailableError,
    AfipWsfeError,
    Invoice,
    InvoiceItem,
    InvoiceValidationError,
    InvoicingSettings,
    build_fe_cae_request,
    ensure_order_not_invoiced,
    format_cbte,
    next_invoice_number,
    normalize_cae,
    parse_arca_fecha,
    sanitize_arca_observaciones,
    validar_fechas_arca,
    validate_concepto_periodo,
    validate_cuit,
    validate_doc_receptor,
    validate_importe,
    validate_inicio_actividades,
    validate_monotributo_categoria,
)

HOY = datetime.date(2026, 11, 10)


class TestValidateCuit:
    def test_ok(self):
        assert validate_cuit("30123456789") == "30123456789"

    def test_ok_con_espacios(self):
        assert validate_cuit("  30123456789  ") == "30123456789"

    @pytest.mark.parametrize("cuit", ["", "3012345678", "301234567890", "abcdefghijk", "3012345678a"])
    def test_invalido(self, cuit):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_cuit(cuit)
        assert exc.value.code == "cuit_invalido"


class TestValidateCategoriaMonotributo:
    @pytest.mark.parametrize("cat", ["A", "K", "f", ""])
    def test_ok(self, cat):
        expected = cat.upper()
        assert validate_monotributo_categoria(cat) == expected

    @pytest.mark.parametrize("cat", ["L", "0", "AB", "12"])
    def test_invalido(self, cat):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_monotributo_categoria(cat)
        assert exc.value.code == "categoria_monotributo_invalida"


class TestValidateInicioActividades:
    def test_ok(self):
        assert validate_inicio_actividades("01/05/2020") == "01/05/2020"

    def test_vacio_es_ok(self):
        assert validate_inicio_actividades("") == ""

    @pytest.mark.parametrize("valor", ["01/05/20", "31/02/2020", "2020-05-01", "abc"])
    def test_invalido(self, valor):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_inicio_actividades(valor)
        assert exc.value.code == "inicio_actividades_invalido"


class TestValidateConceptoPeriodo:
    def test_productos_sin_fechas(self):
        validate_concepto_periodo(CONCEPTO_PRODUCTOS, None, None)

    def test_servicios_con_periodo(self):
        validate_concepto_periodo(CONCEPTO_SERVICIOS, HOY, HOY)

    def test_mezclado_con_periodo(self):
        validate_concepto_periodo(CONCEPTO_AMBOS, HOY - datetime.timedelta(days=2), HOY)

    @pytest.mark.parametrize("concepto", [CONCEPTO_SERVICIOS, CONCEPTO_AMBOS])
    def test_servicios_sin_desde(self, concepto):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_concepto_periodo(concepto, None, HOY)
        assert exc.value.code == "periodo_servicio_requerido"

    @pytest.mark.parametrize("concepto", [CONCEPTO_SERVICIOS, CONCEPTO_AMBOS])
    def test_servicios_sin_hasta(self, concepto):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_concepto_periodo(concepto, HOY, None)
        assert exc.value.code == "periodo_servicio_requerido"

    def test_desde_mayor_que_hasta(self):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_concepto_periodo(CONCEPTO_SERVICIOS, HOY, HOY - datetime.timedelta(days=1))
        assert exc.value.code == "periodo_servicio_invalido"

    def test_concepto_desconocido(self):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_concepto_periodo(4, None, None)
        assert exc.value.code == "concepto_invalido"


class TestValidateDocReceptor:
    def test_consumidor_final_sin_numero(self):
        validate_doc_receptor(DOC_TIPO_CONSUMIDOR_FINAL, 0)

    def test_consumidor_final_con_numero_rechazado(self):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_doc_receptor(DOC_TIPO_CONSUMIDOR_FINAL, 123)
        assert exc.value.code == "doc_receptor_invalido"

    def test_cuit_11_digitos(self):
        validate_doc_receptor(DOC_TIPO_CUIT, 30123456789)

    def test_cuit_corto(self):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_doc_receptor(DOC_TIPO_CUIT, 123456789)
        assert exc.value.code == "doc_receptor_invalido"

    def test_dni_8_digitos(self):
        validate_doc_receptor(DOC_TIPO_DNI, 30123456)

    def test_dni_7_digitos_ok(self):
        # DNIs viejos de 7 dígitos siguen vigentes
        validate_doc_receptor(DOC_TIPO_DNI, 1234567)

    def test_dni_con_exceso_de_digitos(self):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_doc_receptor(DOC_TIPO_DNI, 123456789)
        assert exc.value.code == "doc_receptor_invalido"

    def test_doc_tipo_desconocido(self):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_doc_receptor(87, 0)
        assert exc.value.code == "doc_receptor_invalido"


class TestNormalizeCae:
    def test_14_digitos_invariante(self):
        assert normalize_cae("12345678901234") == "12345678901234"

    def test_rellena_con_ceros(self):
        assert normalize_cae("123") == "00000000000123"
        assert len(normalize_cae("123")) == 14

    def test_int_aceptado(self):
        assert normalize_cae(42) == "00000000000042"

    def test_mas_de_14_digitos(self):
        with pytest.raises(InvoiceValidationError) as exc:
            normalize_cae("123456789012345")
        assert exc.value.code == "cae_invalido"

    def test_no_numerico(self):
        with pytest.raises(InvoiceValidationError) as exc:
            normalize_cae("12A4567890123")
        assert exc.value.code == "cae_invalido"

    def test_vacio(self):
        with pytest.raises(InvoiceValidationError):
            normalize_cae("")


class TestParseArcaFecha:
    def test_yyyymmdd(self):
        assert parse_arca_fecha("20261121") == datetime.date(2026, 11, 21)

    def test_int_yyyymmdd(self):
        assert parse_arca_fecha(20261121) == datetime.date(2026, 11, 21)

    def test_iso(self):
        assert parse_arca_fecha("2026-11-21") == datetime.date(2026, 11, 21)

    def test_invalido(self):
        with pytest.raises(InvoiceValidationError) as exc:
            parse_arca_fecha("no-fecha")
        assert exc.value.code == "cae_vto_invalido"


class TestValidarFechasArca:
    def test_productos_hoy(self):
        validar_fechas_arca(HOY, CONCEPTO_PRODUCTOS, HOY)

    def test_productos_fuera_ventana(self):
        with pytest.raises(InvoiceValidationError) as exc:
            validar_fechas_arca(HOY + datetime.timedelta(days=6), CONCEPTO_PRODUCTOS, HOY)
        assert exc.value.code == "fecha_fuera_ventana_arca"

    def test_productos_borde_ventana(self):
        validar_fechas_arca(HOY - datetime.timedelta(days=5), CONCEPTO_PRODUCTOS, HOY)

    def test_servicios_periodo_dentro_ventana(self):
        validar_fechas_arca(
            HOY,
            CONCEPTO_SERVICIOS,
            HOY,
            fch_serv_desde=HOY - datetime.timedelta(days=10),
            fch_serv_hasta=HOY,
        )

    def test_servicios_desde_fuera_ventana(self):
        with pytest.raises(InvoiceValidationError) as exc:
            validar_fechas_arca(
                HOY,
                CONCEPTO_SERVICIOS,
                HOY,
                fch_serv_desde=HOY - datetime.timedelta(days=11),
                fch_serv_hasta=HOY,
            )
        assert exc.value.code == "fecha_fuera_ventana_arca"

    def test_servicios_hasta_fuera_ventana(self):
        with pytest.raises(InvoiceValidationError) as exc:
            validar_fechas_arca(
                HOY,
                CONCEPTO_AMBOS,
                HOY,
                fch_serv_desde=HOY,
                fch_serv_hasta=HOY + datetime.timedelta(days=11),
            )
        assert exc.value.code == "fecha_fuera_ventana_arca"


class TestValidateImporte:
    def test_ok(self):
        assert validate_importe(Decimal("5200.00")) == Decimal("5200.00")

    def test_ok_str(self):
        assert validate_importe("5200.00") == Decimal("5200.00")

    def test_cero_rechazado(self):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_importe(Decimal("0.00"))
        assert exc.value.code == "importe_invalido"

    def test_negativo_rechazado(self):
        with pytest.raises(InvoiceValidationError) as exc:
            validate_importe(Decimal("-50.00"))
        assert exc.value.code == "importe_invalido"

    def test_no_numerico(self):
        with pytest.raises(InvoiceValidationError):
            validate_importe("abc")


class TestUnicoPorPedido:
    def test_sin_comprobante(self):
        ensure_order_not_invoiced(None)

    def test_ya_facturado(self):
        already = Invoice(
            order_id="ord-1",
            punto_venta=1,
            tipo_cbte=TIPO_CBTE_FACTURA_C,
            numero=7,
            cae="12345678901234",
            cae_vto=HOY + datetime.timedelta(days=10),
            fecha=HOY,
            imp_total="5200.00",
            receptor_doc_tipo=DOC_TIPO_CONSUMIDOR_FINAL,
            receptor_doc_nro=0,
            receptor_nombre="Maria",
        )
        with pytest.raises(InvoiceValidationError) as exc:
            ensure_order_not_invoiced(already)
        assert exc.value.code == "pedido_ya_facturado"
        assert exc.value.invoice == already


class TestNextInvoiceNumber:
    def test_desde_cero(self):
        assert next_invoice_number(0) == 1

    def test_consecutivo(self):
        assert next_invoice_number(7) == 8


class TestSanitizeObservaciones:
    def test_mantiene_texto_normal(self):
        assert sanitize_arca_observaciones(["Falta el CUIT"]) == ["Falta el CUIT"]

    def test_limpia_ruido_tecnico(self):
        obs = [
            "Line 113, Column 54: error",
            "Traceback (most recent call last):",
            "  File \"/var/app/server.py\", line 12",
            "ok",
        ]
        assert sanitize_arca_observaciones(obs) == ["ok"]

    def test_trunca_largas(self):
        result = sanitize_arca_observaciones(["x" * 500])
        assert len(result[0]) <= 200

    def test_limite_de_items(self):
        result = sanitize_arca_observaciones([f"obs {i}" for i in range(20)])
        assert len(result) == 10

    def test_vacio(self):
        assert sanitize_arca_observaciones(None) == []
        assert sanitize_arca_observaciones([]) == []


class TestFormatCbte:
    def test_zero_padding(self):
        assert format_cbte(1, 42) == "0001-00000042"

    def test_punto_de_venta_grande(self):
        assert format_cbte(12, 3) == "0012-00000003"


class TestInvoicingSettings:
    def test_ok(self):
        s = InvoicingSettings(
            cuit="30123456789",
            punto_venta=1,
            razon_social="PASTA FRESCA SAS",
            domicilio="Av. Corrientes 123",
            condicion_iva="Responsable Monotributo",
            categoria_monotributo="f",
            ingresos_brutos="",
            inicio_actividades="01/05/2020",
        )
        assert s.categoria_monotributo == "F"  # normalizado a mayúscula

    def test_cuit_invalido(self):
        with pytest.raises(InvoiceValidationError):
            InvoicingSettings(cuit="123", punto_venta=1)

    def test_punto_venta_cero(self):
        with pytest.raises(InvoiceValidationError) as exc:
            InvoicingSettings(cuit="30123456789", punto_venta=0)
        assert exc.value.code == "punto_venta_invalido"

    def test_inicio_actividades_invalido(self):
        with pytest.raises(InvoiceValidationError):
            InvoicingSettings(
                cuit="30123456789",
                punto_venta=1,
                inicio_actividades="01/05/20",
            )


class TestInvoiceItem:
    def test_ok(self):
        item = InvoiceItem(descripcion="Bizmerengue 20", cantidad=Decimal(20), precio_unit="1000.00", position=1)
        assert item.position == 1

    def test_descripcion_vacia(self):
        with pytest.raises(InvoiceValidationError):
            InvoiceItem(descripcion="", cantidad=Decimal(1), precio_unit="10.00")

    def test_cantidad_cero(self):
        with pytest.raises(InvoiceValidationError) as exc:
            InvoiceItem(descripcion="x", cantidad=Decimal(0), precio_unit="10.00")
        assert exc.value.code == "cantidad_invalida"

    def test_precio_invalido(self):
        with pytest.raises(InvoiceValidationError) as exc:
            InvoiceItem(descripcion="x", cantidad=Decimal(1), precio_unit="abc")
        assert exc.value.code == "importe_invalido"


class TestInvoice:
    def _invoice(self, **overrides):
        base = {
            "order_id": "ord-1",
            "punto_venta": 1,
            "tipo_cbte": TIPO_CBTE_FACTURA_C,
            "numero": 7,
            "cae": "12345678901234",
            "cae_vto": HOY + datetime.timedelta(days=10),
            "fecha": HOY,
            "imp_total": "5200.00",
            "receptor_doc_tipo": DOC_TIPO_CONSUMIDOR_FINAL,
            "receptor_doc_nro": 0,
            "receptor_nombre": "Maria",
        }
        base.update(overrides)
        return Invoice(**base)

    def test_ok(self):
        inv = self._invoice()
        assert inv.estado == ESTADO_APROBADO
        assert inv.id  # uuid generado
        assert inv.obs == ()

    def test_cae_de_13_digitos_rechazado(self):
        with pytest.raises(InvoiceValidationError) as exc:
            self._invoice(cae="1234567890123")
        assert exc.value.code == "cae_invalido"

    def test_estado_invalido(self):
        with pytest.raises(InvoiceValidationError) as exc:
            self._invoice(estado="X")
        assert exc.value.code == "estado_invalido"

    def test_estado_rechazado_ok(self):
        assert self._invoice(estado=ESTADO_RECHAZADO).estado == ESTADO_RECHAZADO

    def test_numero_cero(self):
        with pytest.raises(InvoiceValidationError):
            self._invoice(numero=0)

    def test_imp_total_invalido(self):
        with pytest.raises(InvoiceValidationError):
            self._invoice(imp_total="0.00")


class TestBuildFeCaeRequest:
    def test_productos(self):
        req = build_fe_cae_request(
            punto_venta=1,
            tipo_cbte=TIPO_CBTE_FACTURA_C,
            numero=8,
            imp_total=Decimal("5200.00"),
            concepto=CONCEPTO_PRODUCTOS,
            doc_tipo=DOC_TIPO_CONSUMIDOR_FINAL,
            doc_nro=0,
            fecha=HOY,
        )
        cab = req["FeCabReq"]
        assert cab["CantReg"] == 1
        assert cab["PtoVta"] == 1
        assert cab["CbteTipo"] == TIPO_CBTE_FACTURA_C
        det = req["FeDetReq"]["FECAEDetRequest"][0]
        assert det["CbteDesde"] == 8
        assert det["CbteHasta"] == 8
        assert det["CbteFch"] == "20261110"
        assert det["ImpTotal"] == 5200.0
        assert det["ImpNeto"] == 5200.0
        assert det["ImpIVA"] == 0
        assert det["MonId"] == "PES"
        assert det["MonCotiz"] == 1
        assert det["DocTipo"] == 99
        assert det["DocNro"] == 0
        assert "FchServDesde" not in det
        assert "FchServHasta" not in det

    def test_servicios_incluye_periodo(self):
        req = build_fe_cae_request(
            punto_venta=2,
            tipo_cbte=TIPO_CBTE_FACTURA_C,
            numero=1,
            imp_total=Decimal("100.00"),
            concepto=CONCEPTO_SERVICIOS,
            doc_tipo=DOC_TIPO_DNI,
            doc_nro=30123456,
            fecha=HOY,
            fch_serv_desde=datetime.date(2026, 11, 1),
            fch_serv_hasta=HOY,
        )
        det = req["FeDetReq"]["FECAEDetRequest"][0]
        assert det["FchServDesde"] == "20261101"
        assert det["FchServHasta"] == "20261110"

    def test_servicios_sin_fechas_rechazado(self):
        with pytest.raises(InvoiceValidationError) as exc:
            build_fe_cae_request(
                punto_venta=1,
                tipo_cbte=TIPO_CBTE_FACTURA_C,
                numero=1,
                imp_total=Decimal("100.00"),
                concepto=CONCEPTO_SERVICIOS,
                doc_tipo=DOC_TIPO_CONSUMIDOR_FINAL,
                doc_nro=0,
                fecha=HOY,
            )
        assert exc.value.code == "periodo_servicio_requerido"


class TestAfipErrors:
    def test_wsfe_error_con_observaciones(self):
        err = AfipWsfeError("Rechazo ARCA", observaciones=["10015: Fecha de comprobante inválida"])
        assert err.observaciones == ["10015: Fecha de comprobante inválida"]
        assert "10015" in str(err)

    def test_sin_observaciones(self):
        err = AfipWsfeError("Rechazo ARCA")
        assert err.observaciones == []
        assert str(err) == "Rechazo ARCA"

    def test_clases_distintas(self):
        assert issubclass(AfipCredentialMissingError, Exception)
        assert issubclass(AfipUnavailableError, Exception)
        assert issubclass(AfipWsfeError, Exception)
