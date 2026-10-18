/**
 * Formatadores ARS de la app (specs master RF-07, p02, p05).
 *
 * Reglas de oro:
 * - Los montos viajan por la API como string ("1200.5"). Acá se convierten a
 *   número SOLO para formatear; nunca se reintroduce el resultado en un
 *   payload.
 * - Es ARS: siempre prefijo "ARS", moneda SIEMPRE MAYÚSCULA, separador de miles
 *   ".", decimales ",".
 * - Cero decimales en el default (ARS doméstico, step de redondeo = 100).
 * - Nunca Math.round: el redondeo de precios es responsabilidad del backend.
 * - La cantidad es string para no perder precisión (Decimal en el backend).
 */

const ZERO_DECIMALS = { maximumFractionDigits: 0 };
const TWO_DECIMALS = { maximumFractionDigits: 2 };
const MINUS = "−"; // U+2212, signo de resta tipográfico para deltas

/** "1200" → "ARS 1.200" · "1200.50" → "ARS 1.200,50" · "" / NaN → "ARS 0" */
export function formatMoney(amount: string | number): string {
  const n = typeof amount === "number" ? amount : Number(amount);
  const value = Number.isFinite(n) ? n : 0;
  return `ARS ${value.toLocaleString("es-AR", ZERO_DECIMALS)}`;
}

/**
 * Decimales explícitos (campos de precio/umbral donde los centavos importan):
 * "1200.50" → "1.200,50".
 */
export function formatMoneyDecimals(amount: string | number): string {
  const n = typeof amount === "number" ? amount : Number(amount);
  const value = Number.isFinite(n) ? n : 0;
  return value.toLocaleString("es-AR", TWO_DECIMALS);
}

/** "5", "kg" → "5 kg" · "0.5", "kg" → "0,5 kg" · "1.5", "unidad" → "1,5 unidad" */
export function formatQty(qty: string | number, unit: string): string {
  const n = typeof qty === "number" ? qty : Number(qty);
  const value = Number.isFinite(n) ? n : 0;
  return `${value.toLocaleString("es-AR", TWO_DECIMALS)} ${unit}`;
}

/**
 * Delta de stock con signo y prefijo:
 * 2 → "+2" · -3 → "−3" (U+2212, no guion) · 0 → "0" · NaN → "0"
 */
export function formatSignedQty(delta: string | number): string {
  const n = typeof delta === "number" ? delta : Number(delta);
  if (!Number.isFinite(n) || n === 0) return "0";
  const abs = Math.abs(n).toLocaleString("es-AR", TWO_DECIMALS);
  return n > 0 ? `+${abs}` : `${MINUS}${abs}`;
}

/**
 * Montos internos: la app representa TODOS los montos como `long` (entero de
 * centavos): los últimos 2 dígitos son los centavos (310000 → $3.100,00).
 *
 * - `moneyToCents` convierte el string de la API ("3100", "1550.5") a centavos
 *   con aritmética exacta (BigInt): nunca pasa por float en la conversión.
 * - `formatCents` es el único camino de centavos a texto.
 * - El frontend NUNCA reintroduce un monto calculado en un payload: el backend
 *   sigue siendo la única autoridad de cálculo (RNF-P4-02).
 */

/** "3100" → 310000 · "1550.5" → 155050 · "12.25" → 1225 · "" / NaN → 0 */
export function moneyToCents(money: string | number): number {
  const s = String(money).trim().replace(",", ".");
  if (!s) return 0;
  const negative = s.startsWith("-");
  const body = negative ? s.slice(1) : s;
  if (!/^\d*(\.\d*)?$/.test(body) || body === "" || body === ".") return 0;
  const [intPart = "0", decPart = ""] = body.split(".");
  // Últimos 2 dígitos = centavos; el contrato no emite más de 2 decimales.
  // Aritmética exacta por partes (sin float intermedio en la fracción).
  const cents = (intPart === "" ? 0 : Number(intPart)) * 100 + Number((decPart + "00").slice(0, 2));
  return negative ? -cents : cents;
}

/** 310000 → "ARS 3.100" · 120050 → "ARS 1.200,50" (decimales solo si existen). */
export function formatCents(cents: number): string {
  const value = Number.isFinite(cents) ? cents / 100 : 0;
  return `ARS ${value.toLocaleString("es-AR", { maximumFractionDigits: 2 })}`;
}

/** 100 → "100%" · 1.5 → "1,5%" (margen_pct del contrato es porcentaje). */
export function formatPct(pct: number | null): string {
  const value = Number.isFinite(pct ?? NaN) ? (pct as number) : 0;
  return `${value.toLocaleString("es-AR", { maximumFractionDigits: 2 })}%`;
}

/** ISO 8601 → "16/10/2026, 14:30" (24 h, formato local del navegador). */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

/**
 * Montos en centavos (long): el backend emite Money como entero de centavos
 * (310050 = $3.100,50). `formatCents` es el único camino centavos → texto.
 * En los formularios el usuario tipea pesos: la conversión ocurre en el borde
 * (`pesosToCents` al enviar, `centsToPesos` al precargar).
 */

/** 310050 → "ARS 3.100,50" · 310000 → "ARS 3.100" · NaN → "ARS 0". */
export function formatCents(cents: number): string {
  const value = Number.isFinite(cents) ? cents / 100 : 0;
  return `ARS ${value.toLocaleString("es-AR", TWO_DECIMALS)}`;
}

/** 3000.5 → 300050 · 1200 → 120000 (aritmética exacta por partes, sin float). */
export function pesosToCents(pesos: string | number): number {
  const s = String(pesos).trim().replace(",", ".");
  if (!s) return 0;
  const negative = s.startsWith("-");
  const body = negative ? s.slice(1) : s;
  if (!/^\d*(\.\d*)?$/.test(body) || body === "" || body === ".") return 0;
  const [intPart = "0", decPart = ""] = body.split(".");
  const cents =
    (intPart === "" ? 0 : Number(intPart)) * 100 +
    Number((decPart + "00").slice(0, 2));
  return negative ? -cents : cents;
}

/** 300050 → 3000.5 (precarga de inputs que se tipean en pesos). */
export function centsToPesos(cents: number): number {
  return Number.isFinite(cents) ? cents / 100 : 0;
}

/** 100 → "100%" · 1.5 → "1,5%" (porcentajes: no son dinero). */
export function formatPct(pct: number | null): string {
  const value = Number.isFinite(pct ?? NaN) ? (pct as number) : 0;
  return `${value.toLocaleString("es-AR", { maximumFractionDigits: 2 })}%`;
}
