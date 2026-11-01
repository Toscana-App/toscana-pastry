import { apiFetch } from "@/lib/api";
import { pesosToCents } from "@/lib/format";
import type {
  CostHistoryListResponse,
  Material,
  MaterialCreatePayload,
  MaterialListQuery,
  MaterialListResponse,
  MaterialUpdatePayload,
} from "@/types/calc";

// Service de materiales de la calculadora de costos (RF-P2CC-01..05).
// Mismo patrón que calcSettingsService: fetch directo con apiFetch (sin
// react-query), helpers locales buildQuery/jsonOptions/deleteViaApiFetch
// (copiados acá; calcSettingsService no se modifica).

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

function jsonOptions(method: string, body: unknown): RequestInit {
  return { method, body: JSON.stringify(body) };
}

// apiFetch termina siempre con response.json(); un DELETE exitoso responde
// 204 con body vacío y ese json() lanza SyntaxError. Se traga ese caso
// concreto como éxito; los errores reales (Error con detail) se re-lanzan.
async function deleteViaApiFetch(endpoint: string): Promise<void> {
  try {
    await apiFetch(endpoint, { method: "DELETE" });
  } catch (error) {
    if (error instanceof SyntaxError) return;
    throw error;
  }
}

// La API habla centavos enteros (Money, ver api/v1/money.py); la UI trabaja
// en pesos. La conversión ocurre solo en el borde, acá: pesos → centavos al
// enviar, centavos → string de pesos ("50.00") al recibir.
type Cents = number | string | null;

function fromCents(value: Cents): string | null {
  if (value === null || value === undefined) return null;
  return (Number(value) / 100).toFixed(2);
}

function toCentsPayload<T extends { purchase_total_price?: number | null }>(
  payload: T
): T {
  if (payload.purchase_total_price === undefined || payload.purchase_total_price === null) {
    return payload;
  }
  return { ...payload, purchase_total_price: pesosToCents(payload.purchase_total_price) };
}

function materialFromApi(material: Material): Material {
  return {
    ...material,
    purchase_total_price: fromCents(material.purchase_total_price),
    unit_cost: fromCents(material.unit_cost),
  };
}

export const calcMaterialsService = {
  // GET /calc/materials?q?,category_id?,supplier_id?,status?,page,page_size.
  async listMaterials(query: MaterialListQuery = {}): Promise<MaterialListResponse> {
    const res = await apiFetch<MaterialListResponse>(
      `/calc/materials${buildQuery({ ...query })}`
    );
    return { ...res, items: res.items.map(materialFromApi) };
  },

  // GET /calc/materials/{id}
  async getMaterial(id: string): Promise<Material> {
    return materialFromApi(await apiFetch<Material>(`/calc/materials/${id}`));
  },

  // POST /calc/materials → 201. extra="forbid": el payload nunca lleva
  // unit_cost ni status (RF-P2CC-02/03).
  async createMaterial(payload: MaterialCreatePayload): Promise<Material> {
    return materialFromApi(
      await apiFetch<Material>(
        "/calc/materials",
        jsonOptions("POST", toCentsPayload(payload))
      )
    );
  },

  // PATCH /calc/materials/{id} (exclude_unset): solo campos tocados;
  // null en purchase_total_price/package_quantity elimina el dato.
  async updateMaterial(
    id: string,
    payload: MaterialUpdatePayload
  ): Promise<Material> {
    return materialFromApi(
      await apiFetch<Material>(
        `/calc/materials/${id}`,
        jsonOptions("PATCH", toCentsPayload(payload))
      )
    );
  },

  // DELETE /calc/materials/{id} → 204 / 404 / 409 {"impacted_products": N}
  // (sin `detail`: apiFetch lo reporta como Error("Network error")).
  deleteMaterial(id: string): Promise<void> {
    return deleteViaApiFetch(`/calc/materials/${id}`);
  },

  // GET /calc/materials/{id}/cost-history?page,page_size (RF-P2CC-04):
  // más recientes primero (desc).
  async listCostHistory(
    id: string,
    query: { page?: number; page_size?: number } = {}
  ): Promise<CostHistoryListResponse> {
    const res = await apiFetch<CostHistoryListResponse>(
      `/calc/materials/${id}/cost-history${buildQuery({ ...query })}`
    );
    return {
      ...res,
      items: res.items.map((entry) => ({
        ...entry,
        previous_unit_cost: fromCents(entry.previous_unit_cost),
        new_unit_cost: fromCents(entry.new_unit_cost),
      })),
    };
  },
};
