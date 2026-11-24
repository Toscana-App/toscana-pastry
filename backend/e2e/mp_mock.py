"""Mock HTTP de la API de Mercado Pago para e2e (ODD e2e-order-lifecycle, S2).

Unica frontera mockeada de la suite: el provider `MercadoPagoCheckoutProvider`
habla con MP por HTTP, y e2e lo apunta a este mock local mediante el env
`MP_API_URL`. El resto (uvicorn, Postgres, maquinas de dominio) es real.

Endpoints:
  POST /__admin/payments    registra un pago {id, order_id, status, amount, currency}
  GET  /v1/payments/{id}    payload MP (status, external_reference,
                            transaction_amount, currency_id)
  POST /checkout/preferences respuesta dummy con init_point
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class MPMock:
    def __init__(self) -> None:
        self.payments: dict[str, dict[str, Any]] = {}
        self._server: ThreadingHTTPServer | None = None

    def start(self) -> int:
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # silencioso
                pass

            def _send(self, code: int, body: dict[str, Any]) -> None:
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/__admin/payments":
                    mock.payments[str(body["id"])] = body
                    self._send(200, {"ok": True})
                    return
                if self.path == "/checkout/preferences":
                    self._send(
                        200,
                        {"id": "mock-pref-1", "init_point": "http://mock.local/checkout"},
                    )
                    return
                self._send(404, {"message": "not found", "status": 404})

            def do_GET(self) -> None:
                if self.path.startswith("/v1/payments/"):
                    pid = self.path.rsplit("/", 1)[-1]
                    payment = mock.payments.get(pid)
                    if payment is None:
                        self._send(404, {"message": "Not found", "status": 404})
                        return
                    self._send(
                        200,
                        {
                            "id": payment["id"],
                            "status": payment["status"],
                            "external_reference": payment.get("order_id"),
                            "transaction_amount": payment.get("amount"),
                            "currency_id": payment.get("currency"),
                        },
                    )
                    return
                self._send(404, {"message": "not found", "status": 404})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self._server.server_address[1]

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
