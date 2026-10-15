# P7 — Presupuesto · Paso 1 (Cliente)
Módulo: `web/modules/budgets` (wizard step 1) · Ruta: `/presupuestos/nuevo` (paso 1) · Fase: **3**

## Contexto
Inicio del wizard de presupuesto (screenshot verificado): "Nuevo presupuesto" con pasos **1. Cliente → 2. Productos → 3. Resumen**. Paso 1 captura los datos del cliente (screenshot: nombre, teléfono, email, fecha de entrega, notas).

## User story
> Como **repostera**, quiero **registrar quién es el cliente del presupuesto en un formulario rápido**, para **que el presupuesto final lleve sus datos y pueda enviarlo por WhatsApp**.

**Criterios de aceptación**
- [ ] Lleno: nombre (requerido), teléfono, email, fecha de entrega, notas.
- [ ] Si el cliente ya existe (mismo nombre+teléfono), el sistema me lo ofrece para reusarlo (sin duplicar).
- [ ] Con solo nombre completo, puedo avanzar (email/teléfono opcionales para avanzar, requeridos solo para enviar por WhatsApp).
- [ ] Al volver al paso no pierdo lo escrito.

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Registrar cliente nuevo | Repostera | Llena el form → "Continuar a Productos" |
| UC-02 Reusar cliente existente | Repostera | Autocompletado de clientes → selecciona → datos precargados |
| UC-03 Volver/avanzar | Repostera | Navega el wizard sin perder datos |

## Requerimientos funcionales
- **RF-P7-01**: Campos: `name*`, `phone`, `email`, `delivery_date` (fecha, sugerido hoy+3 días), `notes`. (UC-01)
- **RF-P7-02**: Validación: nombre ≥ 3 chars; teléfono y email validados **solo si se ingresan**; email/teléfono requeridos para el envío por WhatsApp (se avisa antes de llegar a ese CTA). (UC-01)
- **RF-P7-03**: Detección de cliente duplicado: mismo `name+phone` (normalizado) → sugerencia "¿Es {nombre}? Usar datos guardados". (UC-02)
- **RF-P7-04**: Persistencia del draft del wizard entre pasos (sin crear presupuesto en la DB hasta el paso 3). (UC-03)
- **RF-P7-05**: El cliente se crea en `customers` al guardar el presupuesto (no antes). (UC-01)

## Requerimientos no funcionales
- **RNF-P7-01**: Autocompletado de clientes: < 150 ms, top 10 por nombre/teléfono.
- **RNF-P7-02**: El form completo cabe en la viewport de 375px sin scroll del teclado (inputs compactos, teclado numérico para teléfono).
- **RNF-P7-03**: A11y: labels visibles, error inline asociado, `inputmode` correcto (tel/email/numeric).

## Tareas
- [ ] API: `GET /customers?q=` (búsqueda para autocompletado)
- [ ] Web: paso 1 del wizard (form zod + RHF)
- [ ] Web: Combobox de clientes existentes (selección → precarga)
- [ ] Web: guardado de draft del wizard (sessionStorage)
- [ ] Tests: pytest de normalización de teléfono (formatos +54/0/loc); Vitest de validaciones condicionales
- [ ] GA4: `budget_client_step_completed`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Field.Root`, `Input` (inputmode por tipo), `DatePicker` (o `Input type=date` estilizado), `Textarea` (notas), `Combobox` (clientes), `Button` (Continuar).
- Header del wizard: "Nuevo presupuesto" + pasos (1 Cliente — 2 Productos — 3 Resumen) como indicador de progreso.
- CTA único del paso: **Continuar** (primario); "Volver" como ghost (no compite).
- Tokens: focus ring blue-400 en inputs; errores en danger con ícono.
