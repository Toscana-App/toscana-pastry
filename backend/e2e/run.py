"""Orquestador e2e (ODD e2e-order-lifecycle, S7).

Levanta: mock MP (proceso en hilo) + base e2e throwaway + uvicorn (proceso
separado), corre los 46 casos (A/B/C/D/R) y hace teardown. Exit 0 = todo verde.

Uso:  python backend/e2e/run.py
      (con el venv del backend activo; requiere Postgres local en
      127.0.0.1:5432, usuario postgres/password, y el puerto 8100 libre)
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "src"))

# IMPORTANTE: el env debe existir ANTES de importar e2e.seed: ese import crea
# el engine de data.db, que lee DATABASE_URL en el momento del import.
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://postgres:password@127.0.0.1:5432/toscana_e2e_db"
)

from e2e.cases import (
    CASES,
    WEBHOOK_SECRET,
    E2EFailure,
    build_ctx,
    close_ctx,
)
from e2e.mp_mock import MPMock
from e2e.seed import E2E_DB, drop_database, ensure_database, seed_all

assert E2E_DB == "toscana_e2e_db", "DATABASE_URL y E2E_DB divergieron"

PORT = 8100
BASE_URL = f"http://127.0.0.1:{PORT}"
READY_TIMEOUT_SECONDS = 90
SERVER_LOG = Path("/tmp/e2e_uvicorn.log")


def _silence_sqlalchemy() -> None:
    import logging

    from data.db import engine as app_engine

    # El engine de la app nace con echo=True: lo apago directamente (el logger
    # solo a veces respeta el nivel) para no anegar el reporte de casos.
    app_engine.echo = False
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)


async def _wait_ready(base_url: str) -> None:
    import httpx

    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    async with httpx.AsyncClient(timeout=3) as client:
        while time.monotonic() < deadline:
            try:
                resp = await client.get(f"{base_url}/docs")
                if resp.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.5)
    raise RuntimeError(f"uvicorn no estuvo listo en {READY_TIMEOUT_SECONDS}s (log: {SERVER_LOG})")


def _start_uvicorn(mock_base: str) -> subprocess.Popen[Any]:
    server_env = dict(
        os.environ,
        MP_API_URL=mock_base,
        MP_ACCESS_TOKEN="TEST-e2e-dummy",
        MP_WEBHOOK_SECRET=WEBHOOK_SECRET,
        PYTHONPATH="src",
    )
    # El handle se deja abierto a proposito: es el stdout del subprocess hijo.
    log_file = open(SERVER_LOG, "w")  # noqa: SIM115
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=BACKEND,
        env=server_env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )


async def _prepare_db() -> None:
    print(f"[e2e] base de datos: drop+create {E2E_DB}")
    await drop_database()
    await ensure_database()


async def amain(mock_base: str, server: subprocess.Popen[Any]) -> int:
    print(f"[e2e] uvicorn pid={server.pid} (log: {SERVER_LOG})")

    ctx = None
    try:
        await _wait_ready(BASE_URL)
        print("[e2e] seed...")
        _silence_sqlalchemy()
        await seed_all()

        ctx = await build_ctx(BASE_URL, mock_base, "prod-e2e-1")
        print(f"[e2e] precio catalogo (consumidor_final): {ctx.catalog_price}")
        print(f"[e2e] corriendo {len(CASES)} casos...\n")

        results: list[tuple[str, str, str, str]] = []
        for case_id, title, fn in CASES:
            start = time.perf_counter()
            try:
                await fn(ctx)
                results.append((case_id, title, "PASS", f"{time.perf_counter() - start:.2f}s"))
                print(f"  PASS  {case_id:<4} {title}")
            except E2EFailure as err:
                results.append((case_id, title, "FAIL", str(err)))
                print(f"  FAIL  {case_id:<4} {title}\n        -> {err}")
            except Exception as err:  # noqa: BLE001 - reporte de corrida
                results.append((case_id, title, "ERROR", repr(err)))
                print(f"  ERROR {case_id:<4} {title}\n        -> {err!r}")

        passed = sum(1 for r in results if r[2] == "PASS")
        print(f"\n[e2e] {passed}/{len(results)} pasaron")
        if passed == len(results):
            await drop_database()
            print(f"[e2e] todo verde; base {E2E_DB} eliminada")
            return 0
        failed = [r[0] for r in results if r[2] != "PASS"]
        print(f"[e2e] FALLOS: {', '.join(failed)}")
        print(f"[e2e] base {E2E_DB} conservada para inspeccionar")
        return 1
    finally:
        if ctx is not None:
            await close_ctx(ctx)
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        print("[e2e] teardown completado")


def main() -> None:
    mock = MPMock()
    mock_base = f"http://127.0.0.1:{mock.start()}"
    print(f"[e2e] mock MP en {mock_base}")
    # Primero la base (async, in-proceso), despues el server: asi uvicorn
    # arranca contra un esquema limpio y sin carrera con el drop.
    asyncio.run(_prepare_db())
    server = _start_uvicorn(mock_base)
    try:
        code = asyncio.run(amain(mock_base, server))
    finally:
        mock.stop()
    sys.exit(code)


if __name__ == "__main__":
    main()
