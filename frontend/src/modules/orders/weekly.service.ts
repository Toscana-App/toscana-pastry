import { apiFetch } from "@/lib/api";
import { downloadEndpoint } from "@/lib/download";
import type { WeeklySummary } from "./types";

const BASE = "/orders/weekly";

/**
 * Servicio del resumen semanal (Fase 5, UC-08 / RF-P6-11):
 * GET /orders/weekly (JSON) y los exports CSV/PDF del mismo reporte.
 *
 * Money: la API emite centavos (long) y el service los pasa tal cual;
 * los componentes formatean con `formatCents`.
 *
 * `week` opcional: ISO `AAAA-Wnn` (p. ej. "2026-W45") o fecha `AAAA-MM-DD`;
 * ausente = semana actual (la resuelve el backend).
 */
export const weeklyService = {
  /** GET /orders/weekly — resumen de la semana natural (Lun-Dom). */
  get(week?: string | null): Promise<WeeklySummary> {
    const qs = week ? `?week=${encodeURIComponent(week)}` : "";
    return apiFetch<WeeklySummary>(`${BASE}${qs}`);
  },

  /**
   * Export CSV del reporte de la semana: GET /orders/export con el rango
   * de la semana (el backend no toma `week` en el export, solo from/to).
   */
  exportCsv(range: { from: string; to: string }): Promise<void> {
    return downloadEndpoint(
      `/orders/export?from=${range.from}&to=${range.to}&format=csv`,
      "pedidos_semana.csv",
    );
  },

  /** Export PDF del resumen: GET /orders/weekly/pdf (mismo `week` opcional). */
  exportPdf(week?: string | null): Promise<void> {
    const qs = week ? `?week=${encodeURIComponent(week)}` : "";
    const fallback = week ? `resumen_semanal_${week}.pdf` : "resumen_semanal.pdf";
    return downloadEndpoint(`${BASE}/pdf${qs}`, fallback);
  },
};
