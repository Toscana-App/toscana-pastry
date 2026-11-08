
const ZERO_DECIMALS = { maximumFractionDigits: 0 };
const TWO_DECIMALS = { maximumFractionDigits: 2 };
const MINUS = "−";

export function formatMoney(amount: string | number): string {
  const n = typeof amount === "number" ? amount : Number(amount);
  const value = Number.isFinite(n) ? n : 0;
  return `ARS ${value.toLocaleString("es-AR", ZERO_DECIMALS)}`;
}

export function formatMoneyDecimals(amount: string | number): string {
  const n = typeof amount === "number" ? amount : Number(amount);
  const value = Number.isFinite(n) ? n : 0;
  return value.toLocaleString("es-AR", TWO_DECIMALS);
}

export function formatQty(qty: string | number, unit: string): string {
  const n = typeof qty === "number" ? qty : Number(qty);
  const value = Number.isFinite(n) ? n : 0;
  return `${value.toLocaleString("es-AR", TWO_DECIMALS)} ${unit}`;
}

export function formatSignedQty(delta: string | number): string {
  const n = typeof delta === "number" ? delta : Number(delta);
  if (!Number.isFinite(n) || n === 0) return "0";
  const abs = Math.abs(n).toLocaleString("es-AR", TWO_DECIMALS);
  return n > 0 ? `+${abs}` : `${MINUS}${abs}`;
}

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


export function formatCents(cents: number): string {
  const value = Number.isFinite(cents) ? cents / 100 : 0;
  return `ARS ${value.toLocaleString("es-AR", TWO_DECIMALS)}`;
}

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

export function centsToPesos(cents: number): number {
  return Number.isFinite(cents) ? cents / 100 : 0;
}

export function formatPct(pct: number | null): string {
  const value = Number.isFinite(pct ?? NaN) ? (pct as number) : 0;
  return `${value.toLocaleString("es-AR", { maximumFractionDigits: 2 })}%`;
}
