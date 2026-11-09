import { describe, expect, it, vi } from "vitest";
import { fetchStoreDetail, fetchStoreList } from "./storeService";

const fetchMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", () => ({ apiFetch: fetchMock }));

describe("storeService (contrato T3)", () => {
  it("fetchStoreList pide /products?audience= sin búsqueda", async () => {
    const body = {
      audience: "consumidor_final",
      products: [],
      total: 0,
      categories: [],
    };
    fetchMock.mockResolvedValueOnce(body);

    const result = await fetchStoreList("consumidor_final");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls.at(-1)![0]).toBe(
      "/products?audience=consumidor_final",
    );
    expect(result).toBe(body);
  });

  it("fetchStoreList agrega q cuando hay búsqueda", async () => {
    fetchMock.mockResolvedValueOnce({
      audience: "revendedores",
      products: [],
      total: 0,
      categories: [],
    });

    await fetchStoreList("revendedores", "torta");

    expect(fetchMock.mock.calls.at(-1)![0]).toBe(
      "/products?audience=revendedores&q=torta",
    );
  });

  it("fetchStoreDetail pide /products/{id}?audience=", async () => {
    const detail = {
      id: "p1",
      name: "Torta",
      category: "Tortas",
      description: "",
      image_url: null,
      price: "17500",
      servings: 12,
      prep_time_min: 90,
    };
    fetchMock.mockResolvedValueOnce(detail);

    const result = await fetchStoreDetail("p1", "consumidor_final");

    expect(fetchMock.mock.calls.at(-1)![0]).toBe(
      "/products/p1?audience=consumidor_final",
    );
    expect(result).toBe(detail);
  });
});
