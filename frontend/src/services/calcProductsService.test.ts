import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));

import { apiFetch } from "@/lib/api";
import { calcProductsService } from "./calcProductsService";

const mocked = vi.mocked(apiFetch);

describe("calcProductsService money boundary (S1/S3)", () => {
  beforeEach(() => mocked.mockReset());

  it("createProduct: labor/extra money pesos -> integer cents on the wire", async () => {
    mocked.mockResolvedValue({
      product: { id: "p1", name: "Torta", margin_percent: "30" },
      product_lines: { materials: [], labor: [], extra_costs: [] },
      costs: {
        product_total_cost: 1688000,
        profit_amount: 723429,
        discount_amount: 0,
        adjusted_profit_amount: 723429,
        tax_amount: 506400,
        final_sale_price: 2917829,
      },
    });
    await calcProductsService.createProduct({
      name: "Torta corazon",
      margin_percent: "30",
      discount_percent: "0",
      tax_percent: "21",
      status: "draft",
      materials: [{ material_id: "m1", quantity_used: "1" }],
      labor: [
        { activity_name: "Decoracion", hourly_rate: "3000", minutes_required: "120" },
      ],
      extra_costs: [{ concept_name: "Gas y luz", unit_cost: "800", quantity: "1" }],
    });

    const body = JSON.parse(String((mocked.mock.calls[0][1] as RequestInit).body));
    expect(body.labor[0].hourly_rate).toBe(300000);
    expect(body.extra_costs[0].unit_cost).toBe(80000);
    // Qty no se toca.
    expect(body.materials[0].quantity_used).toBe("1");
    expect(body.labor[0].minutes_required).toBe("120");
  });

  it("updateProduct: convierte igual (mismo borde)", async () => {
    mocked.mockResolvedValue({
      product: { id: "p1", name: "Torta", margin_percent: "30" },
      product_lines: { materials: [], labor: [], extra_costs: [] },
      costs: {
        product_total_cost: 0,
        profit_amount: 0,
        discount_amount: 0,
        adjusted_profit_amount: 0,
        tax_amount: 0,
        final_sale_price: 0,
      },
    });
    await calcProductsService.updateProduct("p1", {
      name: "Torta corazon",
      margin_percent: "30",
      discount_percent: "0",
      tax_percent: "21",
      status: "draft",
      labor: [
        { activity_name: "Coccion", hourly_rate: "600.5", minutes_required: "60" },
      ],
    } as never);

    const body = JSON.parse(String((mocked.mock.calls[0][1] as RequestInit).body));
    expect(body.labor[0].hourly_rate).toBe(60050);
  });

  it("createProduct: decimales de pesos -> ctvs (pesosToCents trunca, comportamiento existente)", async () => {
    mocked.mockResolvedValue({
      product: { id: "p1", name: "T", margin_percent: "30" },
      product_lines: { materials: [], labor: [], extra_costs: [] },
      costs: {
        product_total_cost: 0,
        profit_amount: 0,
        discount_amount: 0,
        adjusted_profit_amount: 0,
        tax_amount: 0,
        final_sale_price: 0,
      },
    });
    await calcProductsService.createProduct({
      name: "T",
      margin_percent: "30",
      discount_percent: "0",
      tax_percent: "21",
      status: "draft",
      materials: [],
      labor: [],
      extra_costs: [{ concept_name: "X", unit_cost: "0.125", quantity: "1" }],
    });
    const body = JSON.parse(String((mocked.mock.calls[0][1] as RequestInit).body));
    // "0.125" -> 12 ctvs: pesosToCents usa aritmética entera y trunca
    // el tercer decimal (comportamiento existente del helper compartido).
    expect(body.extra_costs[0].unit_cost).toBe(12);
  });

  it("getProduct: devuelve el shape real del GET (lineas a nivel superior, ctvs)", async () => {
    const detail = {
      product: { id: "p1", name: "Torta", margin_percent: "30" },
      materials: [
        { material_id: "m1", material_name: "Harina", quantity_used: "2", unit_of_measure_snapshot: "kg", unit_cost_snapshot: 150000, line_total_cost: 300000, sort_order: 0 },
      ],
      labor: [],
      extra_costs: [],
      costs: {
        product_total_cost: 300000,
        profit_amount: 128571,
        discount_amount: 0,
        adjusted_profit_amount: 128571,
        tax_amount: 0,
        final_sale_price: 428571,
      },
    };
    mocked.mockResolvedValue(detail);
    const res = await calcProductsService.getProduct("p1");
    expect(mocked.mock.calls[0][0]).toBe("/calc/products/p1");
    expect(res.materials[0].unit_cost_snapshot).toBe(150000);
    expect(res.costs.product_total_cost).toBe(300000);
  });
});
