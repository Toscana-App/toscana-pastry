import io

QR_MEDIA_TYPE = "image/svg+xml"
QR_ERROR_LEVEL = "q"
QR_BORDER = 4
QR_SCALE = 8
QR_DARK = "#1c1718"
QR_LIGHT = "#ffffff"


class QrUnavailableError(RuntimeError):
    pass


def delivery_qr_svg(url: str) -> str:
    try:
        import segno
    except ImportError as exc:
        raise QrUnavailableError("qr_unavailable") from exc
    code = segno.make(url, error=QR_ERROR_LEVEL, micro=False)
    buffer = io.BytesIO()
    code.save(
        buffer,
        kind="svg",
        border=QR_BORDER,
        scale=QR_SCALE,
        dark=QR_DARK,
        light=QR_LIGHT,
        xmldecl=False,
    )
    return buffer.getvalue().decode("utf-8")
