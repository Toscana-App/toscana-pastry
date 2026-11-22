# web-guidelines-frontend
Objective: apply Vercel Web Interface Guidelines across the frontend, Client role first, then Admin. Branch: fix/skeletons-endpoint-only (dirty tree, no commits made). Runner: `npx vitest run` + `npx tsc --noEmit` in `frontend/`.

## Specs
- S1: "implementa los guidelines en todo el frontend.Comenza primero por las pantallas del role Client y luego por el de admin"
- S2: "tienes que utilizar obligatoriamente chakra-ui" (Chakra UI v3 only; no Tailwind classes)
- S3: Rules source: https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md (a11y, focus, forms, animation, typography, content handling, images, performance, nav/state, touch, dark mode, i18n, hydration, hover, copy).
- S4: Change only markup/props/copy needed for a guideline; keep existing Spanish copy language and behavior; no new requirements.

## Tasks
- T1 (S1-S4) Client screens: `/`, `/products`, `/tienda/[id]`, `/carrito`, `/checkout`, `/my-orders`, `/profile`, `/contact`, `/login`, `/unauthorized` + their components. Route: delegated (context backstop). Status: pending
- T2 (S1-S4) Admin screens: `/admin/**`, `/productos/**`, `/pedidos/**`, `/presupuestos/**` + calc/admin/modules components. Route: delegated. Status: pending

## Specs (feature 2: Chakra components)
- S5: "1)Implementa el componente menu para las opciones de la navbar" (Chakra `Menu`)
- S6: "2)En el compoenete de perfil de la navbar,utiliza el componente de chakra-ui avatar" (Chakra `Avatar`)
- S7: "3)Format Number para los montos" (Chakra `FormatNumber`)
- S8: "4)Card verticales para ver los pedidos" (Chakra `Card`, vertical layout)
- S9: "5)Status para mostrar el estado del pedido" (Chakra `Status`)
- S10: "6)Empty State para el carrito" (Chakra `EmptyState`)
- S11: "7)Layout Float Used to anchor an element to the edge of a container para el badge del carrito en la navbar" (Chakra `Float`)
- S12: "8)useChart para la implementacion de charts en la seccion de dashboard para mostrar los principales kpi de la pasteleria" (`useChart` from @chakra-ui/charts; deps @chakra-ui/charts + recharts installed)
- S13: "Todos los componentes nombrados forman parte de chakra-ui"

## Tasks (feature 2)
- T3 (S5,S6,S11,S7) Navbar: Menu, Avatar, Float cart badge. Route: delegated (parallel). Status: pending
- T4 (S8,S9,S7) My orders: vertical Cards + Status. Route: delegated (parallel). Status: pending
- T5 (S10,S7) Cart: EmptyState. Route: delegated (parallel). Status: pending
- T6 (S12,S7) Dashboard: useChart KPIs. Route: delegated (parallel). Status: pending
- T7 (S7) FormatNumber for remaining money amounts. Route: after T3-T6. Status: pending

## Specs (feature 3: dashboard endpoints, backend)
- S14: "crea los casos de uso para incorporar los endpoints para crear los dashboard"
- S15: "Sigue las caracteristicas de senior-dev para la definicion del nuevo endpoint para la implementacion del dashboard,para que sean consultas a la db livianas y performantes"
- S16 (assumption, KPIs from existing orders data): admin-only `GET /api/v1/dashboard/*` read endpoints: sales summary, sales time series, orders by status, top products, payment method split; each a use case over a DashboardRepository port; SQL aggregates only (GROUP BY, no entity loading), bounded period, index migration if needed.
- S17: out of scope now: frontend wiring of these endpoints.

## Tasks (feature 3)
- T8 (S14-S17) Backend dashboard use cases + endpoints + tests. Route: delegated (parallel with T7, disjoint surface). Risk: item 1 (index migration). Status: pending

## Log
- L5 (2026-11-10): "si, hacelo así.\nLuego,crea los casos de uso para incorporar los endpoints para crear los dashboard.Sigue las caracteristicas de senior-dev para la definicion del nuevo endpoint para la implementacion del dashboard,para que sean consultas a la db livianas y performantes"
- L4 (2026-11-09): user message with items 1-8 quoted in S5-S13 verbatim.
- L1 (2026-11-09): "implementa los guidelines en todo el frontend.Comenza primero por las pantallas del role Client y luego por el de admin"
- L2 (2026-11-09): "tienes que utilizar obligatoriamente chakra-ui"
- L3: Done earlier (hero, login, layout skip link): hero_section.tsx, HeroSearchNav.tsx, PortalSearch.tsx, LoginForm.tsx, login/page.tsx, app/layout.tsx.
