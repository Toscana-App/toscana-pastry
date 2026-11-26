# e2e — ciclo de vida de pedido + maquina de pagos

Suite e2e de nivel API (ODD: `odd/tasks/e2e-order-lifecycle.md`). 20 casos
GIVEN-WHEN-THEN contra un backend vivo: uvicorn real + Postgres real; la unica
frontera mockeada es la API de Mercado Pago (mock HTTP local via env
`MP_API_URL`).

## Requisitos

- Postgres local en `127.0.0.1:5432` (usuario `postgres`, password `password`).
- Puerto `8100` libre.
- venv del backend activo (`backend/.venv`).

## Ejecucion

```bash
python backend/e2e/run.py
```

El runner:

1. Levanta el mock MP (puerto efemero).
2. `DROP/CREATE` de la base throwaway `toscana_e2e_db` (limpia por corrida).
3. Levanta `uvicorn main:app` en `127.0.0.1:8100` (log: `/tmp/e2e_uvicorn.log`).
4. Siembra usuarios (1 admin, 2 clientes), 1 ingrediente y 1 producto con receta.
5. Corre los 20 casos en orden (A: creacion/RBAC, B: maquina de pedido, C: pagos).
6. Teardown: baja uvicorn y el mock; drop de la base SOLO si todo fue verde
   (si algo falla, la base queda para inspeccionar).

Exit code `0` = todo verde; `1` = hay fallos (se listan y se conserva la base).

## Archivos

- `run.py` — orquestador (una sola entrada).
- `cases.py` — los 20 casos (autoritativos en el ODD) + helpers de transporte.
- `seed.py` — base throwaway + seed idempotente (reusa engine/ORM de la app).
- `mp_mock.py` — mock HTTP de la API de Mercado Pago.

## Notas

- No esta en CI (requiere Postgres local + puerto libre); se corre a demanda
  antes de mergear cambios que toquen el ciclo de vida de pedido o pagos.
- `MP_API_URL` tiene default `https://api.mercadopago.com` en produccion; la
  suite lo apunta al mock.
