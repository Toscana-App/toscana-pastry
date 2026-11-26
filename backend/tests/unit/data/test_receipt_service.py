from pathlib import Path

import pytest

from api.v1.orders.receipt_service import (
    MAX_RECEIPT_BYTES,
    ReceiptValidationError,
    delete_receipt,
    read_receipt,
    validate_receipt,
    write_receipt,
)

_PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32

FAKES = [
    ("texto plano", b"transferencia realizada el 24/11 por $48.600"),
    ("cabecera PDF falsa", b"MKPDF-1.7\n1 0 obj\n"),
    ("gif", b"GIF89a" + b"\x00" * 16),
    ("webp", b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 16),
    ("vacío", b""),
    ("binario aleatorio", bytes(range(256))),
]


def test_detecta_pdf():
    assert validate_receipt(_PDF) == "pdf"


def test_detecta_png():
    assert validate_receipt(_PNG) == "png"


def test_detecta_jpeg():
    assert validate_receipt(_JPEG) == "jpg"


@pytest.mark.parametrize("data", [f[1] for f in FAKES], ids=[f[0] for f in FAKES])
def test_rechaza_falsificaciones(data):
    with pytest.raises(ReceiptValidationError) as exc:
        validate_receipt(data)
    assert exc.value.code == "receipt_invalid_type"


def test_limite_maximo_cinco_mib():
    data = b"%PDF-1.7" + b"\x00" * (MAX_RECEIPT_BYTES - 5 + 1)
    with pytest.raises(ReceiptValidationError) as exc:
        validate_receipt(data)
    assert exc.value.code == "receipt_too_large"


def test_exactamente_cinco_mib_es_valido():
    data = b"%PDF-1.7" + b"\x00" * (MAX_RECEIPT_BYTES - 8)
    assert validate_receipt(data) == "pdf"


def test_write_read_roundtrip(tmp_path: Path):
    write_receipt("42", _PDF, "pdf", base_dir=tmp_path)
    assert read_receipt("42", "pdf", base_dir=tmp_path) == _PDF


def test_write_crea_directorio(tmp_path: Path):
    write_receipt("7", _PNG, "png", base_dir=tmp_path)
    assert (tmp_path / "7.png").is_file()


def test_delete_remueve_archivo(tmp_path: Path):
    write_receipt("9", _JPEG, "jpg", base_dir=tmp_path)
    delete_receipt("9", "jpg", base_dir=tmp_path)
    assert not (tmp_path / "9.jpg").exists()


def test_delete_idempotente(tmp_path: Path):
    delete_receipt("no-existe", "pdf", base_dir=tmp_path)


def test_read_sin_archivo_lanza(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        read_receipt("no-existe", "pdf", base_dir=tmp_path)


def test_order_id_con_path_traversal_rechazado(tmp_path: Path):
    with pytest.raises(ValueError):
        write_receipt("../outside", _PDF, "pdf", base_dir=tmp_path)


def test_extesion_invalida_rechazada(tmp_path: Path):
    with pytest.raises(ValueError):
        write_receipt("42", b"x", "php", base_dir=tmp_path)
