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

async function deleteViaApiFetch(endpoint: string): Promise<void> {
  try {
    await apiFetch(endpoint, { method: "DELETE" });
  } catch (error) {
    if (error instanceof SyntaxError) return;
    throw error;
  }
}

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
  async listMaterials(query: MaterialListQuery = {}): Promise<MaterialListResponse> {
    const res = await apiFetch<MaterialListResponse>(
      `/calc/materials${buildQuery({ ...query })}`
    );
    return { ...res, items: res.items.map(materialFromApi) };
  },

  async getMaterial(id: string): Promise<Material> {
    return materialFromApi(await apiFetch<Material>(`/calc/materials/${id}`));
  },

  async createMaterial(payload: MaterialCreatePayload): Promise<Material> {
    return materialFromApi(
      await apiFetch<Material>(
        "/calc/materials",
        jsonOptions("POST", toCentsPayload(payload))
      )
    );
  },

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

  deleteMaterial(id: string): Promise<void> {
    return deleteViaApiFetch(`/calc/materials/${id}`);
  },

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
