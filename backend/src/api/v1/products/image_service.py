import struct

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MIN_IMAGE_DIMENSION = 200

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


class ImageValidationError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)


def detect_image_type(data: bytes) -> str | None:
    if data.startswith(_PNG_MAGIC):
        return "png"
    if data.startswith(_JPEG_MAGIC):
        return "jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    return None


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    n = len(data)
    i = 2
    while i + 4 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0x00, 0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if i + 4 > n:
            return None
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if i + 9 <= n:
                height, width = struct.unpack(">HH", data[i + 5 : i + 9])
                return width, height
            return None
        i += 2 + length
    return None


def _webp_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 30:
        return None
    chunk = data[12:16]
    if chunk == b"VP8 ":
        if data[20:23] != b"\x9d\x01\x2a":
            return None
        width = struct.unpack("<H", data[23:25])[0] & 0x3FFF
        height = struct.unpack("<H", data[25:27])[0] & 0x3FFF
        return width, height
    if chunk == b"VP8L":
        if len(data) >= 25 and data[20] != 0x2F:
            return None
        if len(data) < 25:
            return None
        b0, b1, b2, b3 = data[21], data[22], data[23], data[24]
        width = 1 + (((b1 & 0x3F) << 8) | b0)
        height = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
        return width, height
    if chunk == b"VP8X":
        width = 1 + (data[24] | (data[25] << 8) | (data[26] << 16))
        height = 1 + (data[27] | (data[28] << 8) | (data[29] << 16))
        return width, height
    return None


def image_dimensions(data: bytes, image_type: str) -> tuple[int, int] | None:
    if image_type == "png":
        return _png_dimensions(data)
    if image_type == "jpg":
        return _jpeg_dimensions(data)
    if image_type == "webp":
        return _webp_dimensions(data)
    return None


def validate_image(data: bytes) -> str:
    image_type = detect_image_type(data)
    if image_type is None:
        raise ImageValidationError(
            "image_invalid_type", "Formato inválido: solo JPEG, PNG o WebP"
        )
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageValidationError(
            "image_too_large", "La imagen supera el máximo de 5 MB"
        )
    dimensions = image_dimensions(data, image_type)
    if (
        dimensions is None
        or dimensions[0] < MIN_IMAGE_DIMENSION
        or dimensions[1] < MIN_IMAGE_DIMENSION
    ):
        raise ImageValidationError(
            "image_too_small", "La imagen debe medir al menos 200×200 px"
        )
    return image_type
