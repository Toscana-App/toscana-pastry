"""O5 — Errores de dominio del flujo de comprobante de transferencia.

El codigo es el contrato con la API (tabla de endpoints del ODD).
La decision vive en los use cases; estos errores son su vocabulario.
"""

from __future__ import annotations


class ReceiptVerificationError(ValueError):
    """Error base: .code es el detail del 404/409 en la API."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ReceiptNotFoundError(ReceiptVerificationError):
    def __init__(self) -> None:
        super().__init__("receipt_not_found")


class ReceiptRequiredError(ReceiptVerificationError):
    def __init__(self) -> None:
        super().__init__("receipt_required")


class ReceiptMethodNotTransferError(ReceiptVerificationError):
    def __init__(self) -> None:
        super().__init__("receipt_method_not_transfer")


class ReceiptAlreadyUploadedError(ReceiptVerificationError):
    def __init__(self) -> None:
        super().__init__("receipt_already_uploaded")


class ReceiptPaymentNotPendingError(ReceiptVerificationError):
    def __init__(self) -> None:
        super().__init__("receipt_payment_not_pending")


class ReceiptOrderTerminalError(ReceiptVerificationError):
    def __init__(self) -> None:
        super().__init__("receipt_order_terminal")


class ReceiptNotDeletableError(ReceiptVerificationError):
    def __init__(self) -> None:
        super().__init__("receipt_not_deletable")


class ReceiptOrderNotReceivableError(ReceiptVerificationError):
    def __init__(self) -> None:
        super().__init__("receipt_order_not_receivable")


class ReceiptOrderNotCancellableError(ReceiptVerificationError):
    def __init__(self) -> None:
        super().__init__("receipt_order_not_cancellable")
