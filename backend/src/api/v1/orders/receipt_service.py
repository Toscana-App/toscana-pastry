import re
from pathlib import Path

MAX_RECEIPT_BYTES = 5 * 1024 * 1024

_PDF_MAGIC = b"%PDF-"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"

_ORDER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ALLOWED_EXT = frozenset({"pdf", "jpg", "png"})

_RECEIPTS_DIR = Path(__file__).resolve().parents[4] / "data" / "receipts"


class ReceiptValidationError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)


def detect_receipt_type(data: bytes) -> str | None:
    if data.startswith(_PDF_MAGIC):
        return "pdf"
    if data.startswith(_PNG_MAGIC):
        return "png"
    if data.startswith(_JPEG_MAGIC):
        return "jpg"
    return None


def validate_receipt(data: bytes) -> str:
    receipt_type = detect_receipt_type(data)
    if receipt_type is None:
        raise ReceiptValidationError(
            "receipt_invalid_type", "Formato inválido: solo PDF, JPEG o PNG"
        )
    if len(data) > MAX_RECEIPT_BYTES:
        raise ReceiptValidationError(
            "receipt_too_large", "El comprobante supera el máximo de 5 MB"
        )
    return receipt_type


def _receipt_path(order_id: str, ext: str, base_dir: Path | None) -> Path:
    if not _ORDER_ID_RE.fullmatch(order_id):
        raise ValueError(f"order_id inválido para storage: {order_id!r}")
    if ext not in _ALLOWED_EXT:
        raise ValueError(f"extensión inválida para comprobante: {ext!r}")
    return (base_dir or _RECEIPTS_DIR) / f"{order_id}.{ext}"


def write_receipt(
    order_id: str, data: bytes, ext: str, base_dir: Path | None = None
) -> Path:
    target = _receipt_path(order_id, ext, base_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def read_receipt(order_id: str, ext: str, base_dir: Path | None = None) -> bytes:
    return _receipt_path(order_id, ext, base_dir).read_bytes()


def delete_receipt(order_id: str, ext: str, base_dir: Path | None = None) -> None:
    _receipt_path(order_id, ext, base_dir).unlink(missing_ok=True)
