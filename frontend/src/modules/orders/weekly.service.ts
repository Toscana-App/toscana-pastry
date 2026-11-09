import { apiFetch } from "@/lib/api";
import { downloadEndpoint } from "@/lib/download";
import type { WeeklySummary } from "./types";

const BASE = "/orders/weekly";

export const weeklyService = {
  get(week?: string | null): Promise<WeeklySummary> {
    const qs = week ? `?week=${encodeURIComponent(week)}` : "";
    return apiFetch<WeeklySummary>(`${BASE}${qs}`);
  },

  exportCsv(range: { from: string; to: string }): Promise<void> {
    return downloadEndpoint(
      `/orders/export?from=${range.from}&to=${range.to}&format=csv`,
      "pedidos_semana.csv",
    );
  },

  exportPdf(week?: string | null): Promise<void> {
    const qs = week ? `?week=${encodeURIComponent(week)}` : "";
    const fallback = week ? `resumen_semanal_${week}.pdf` : "resumen_semanal.pdf";
    return downloadEndpoint(`${BASE}/pdf${qs}`, fallback);
  },
};
