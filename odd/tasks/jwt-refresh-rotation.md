# JWT + refresh token rotation (HttpOnly cookies)

Objective: professional, secure login sessions. Branch: `feat/jwt-refresh-rotation` (worktree `toscana-pastry-worktrees/jwt-refresh-rotation`). Delivery: ask-on-risk. Runners: `pytest` (backend), `vitest` + `tsc` (frontend).

## Specs

- S1. "implementar jwt y refresh token en el login de una manera profesional y segura".
- S2. Access token 15 min; refresh token rotated on every use (approved design, L3).
- S3. Refresh tokens persisted in Postgres (`refresh_tokens`) with `jti` and family so they can be revoked (Redis does not exist in the project, L4).
- S4. Reusing an already-rotated refresh token revokes the whole family.
- S5. Both tokens in `HttpOnly`, `Secure`, `SameSite=Strict` cookies; refresh cookie restricted to `path=/api/v1/auth`. Tokens never reach JavaScript (no tokens in response bodies).
- S6. Separate secrets for access and refresh; TTLs in `settings` (no magic numbers). Prod startup refuses the dev refresh secret.
- S7. `/auth/logout` revokes the session server-side.
- S8. `get_current_user` reads the access cookie; `Authorization: Bearer` stays as fallback (existing tests / API clients).
- S9. Frontend uses `credentials: "include"`; no token handling from JS; `proxy.ts` keeps working with the `auth_token` cookie.
- Assumption: in prod, frontend and `/api` are served same-site (Caddy, per `docs/specs/security.md`).

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S2-S8 backend: config, token logic, refresh store, auth router, tests | inline (no writer trigger) | done | 2a7dd1c |
| T2 | S5, S9 frontend: api.ts, authService, downloads, types, tests | inline | done | 85ef7bc |

## Log

- L1 (2026-11-08, user): "busca una skill con find-skill para implementar jwt y refresh token en el login de una manera profesional y segura"
- L2 (user): "leé api-authentication primero" — skill reviewed, judged too shallow (no rotation/revocation, Node/Flask), not installed.
- L3 (user): "dale, arrancá con ese diseño"
- L4: Redis claim corrected — not in the project; store refresh tokens in Postgres.
- L5 (user): "trabaja sobre un worktree cono estos cambios,no modifiques los cambios de la branch actual" — worktree created from `fix/skeletons-endpoint-only` HEAD, the uncommitted magic-link removal carried over as commit `6e9c6c8`; original checkout untouched.
- L6: T1 RED 12 failing auth tests -> GREEN 24/24. 31 test helpers switched from `json()["access_token"]` to the `auth_token` cookie; prod config tests set REFRESH_SECRET_KEY.
- L7: T2 RED 4/4 new api.test.ts cases fail on the old api.ts -> GREEN. tsc clean, eslint clean. Full vitest: 470/473; `login/page.test.tsx` static-form case also fails at baseline; 2 MaterialsAbm cases are timing-flaky under full-suite load (pass 21/21 in isolation).
- L8 (user): "commitea y pusea.Luego crea el PR". Engram mirror pending (memory tools unavailable this session).
