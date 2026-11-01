import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));

import { apiFetch } from "@/lib/api";
import { calcMaterialsService } from "./calcMaterialsService";
import { calcSettingsService } from "./calcSettingsService";

const mocked = vi.mocked(apiFetch);

describe("calc services money boundary (pesos in the UI, integer cents on the wire)", () => {
  beforeEach(() => mocked.mockReset());

  it("sends purchase_total_price as cents and returns pesos strings", async () => {
    mocked.mockResolvedValue({
      id: "m1",
      purchase_total_price: 10050,
      unit_cost: 5025,
    });
    const material = await calcMaterialsService.createMaterial({
      name: "Harina",
      purchase_total_price: 100.5,
    });
    const body = JSON.parse(String((mocked.mock.calls[0][1] as RequestInit).body));
    expect(body.purchase_total_price).toBe(10050);
    expect(material.purchase_total_price).toBe("100.50");
    expect(material.unit_cost).toBe("50.25");
  });

  it("keeps null purchase_total_price (removes the datum) and null unit_cost", async () => {
    mocked.mockResolvedValue({ id: "m1", purchase_total_price: null, unit_cost: null });
    const material = await calcMaterialsService.updateMaterial("m1", {
      purchase_total_price: null,
    });
    const body = JSON.parse(String((mocked.mock.calls[0][1] as RequestInit).body));
    expect(body.purchase_total_price).toBeNull();
    expect(material.unit_cost).toBeNull();
  });

  it("converts cost-history entries to pesos strings", async () => {
    mocked.mockResolvedValue({
      items: [{ previous_unit_cost: null, new_unit_cost: 5000, changed_at: "x" }],
      total: 1,
      page: 1,
      page_size: 20,
    });
    const res = await calcMaterialsService.listCostHistory("m1");
    expect(res.items[0].previous_unit_cost).toBeNull();
    expect(res.items[0].new_unit_cost).toBe("50.00");
  });

  it("sends default_unit_cost_or_rate as cents and returns pesos", async () => {
    mocked.mockResolvedValue({ id: "d1", default_unit_cost_or_rate: 150000 });
    const cost = await calcSettingsService.createDefaultCost({
      name: "Hora",
      type: "labor",
      default_unit_cost_or_rate: "1500",
      default_quantity_or_minutes: "60",
    });
    const body = JSON.parse(String((mocked.mock.calls[0][1] as RequestInit).body));
    expect(body.default_unit_cost_or_rate).toBe(150000);
    expect(body.default_quantity_or_minutes).toBe("60");
    expect(cost.default_unit_cost_or_rate).toBe("1500.00");
  });
});
