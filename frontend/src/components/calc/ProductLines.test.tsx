import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ProductLines, { computeLinePreviews } from "./ProductLines";
import { renderWithProviders } from "@/test-utils";
import type { Material } from "@/types/calc";

const HARINA: Material = {
  id: "m1",
  name: "Harina 000",
  internal_code: null,
  category_id: null,
  supplier_id: null,
  notes: null,
  purchase_total_price: "1500.00",
  unit_cost: "1500.00",
  package_quantity: "1",
  unit_of_measure: "kg",
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("computeLinePreviews (F2)", () => {
  it("material: qty x unit_cost del catalogo", () => {
    const p = computeLinePreviews(
      [HARINA],
      [{ material_id: "m1", quantity_used: "2" }],
      [],
      []
    );
    expect(p.materialTotals).toEqual([3000]);
    expect(p.grandTotal).toBe(3000);
  });

  it("trabajo: tarifa x minutos / 60", () => {
    const p = computeLinePreviews(
      [],
      [],
      [{ activity_name: "Coccion", hourly_rate: "3000", minutes_required: "120" }],
      []
    );
    expect(p.laborTotals).toEqual([6000]);
  });

  it("extra: costo x cantidad", () => {
    const p = computeLinePreviews(
      [],
      [],
      [],
      [{ concept_name: "Gas", unit_cost: "800", quantity: "1" }]
    );
    expect(p.extraTotals).toEqual([800]);
    expect(p.grandTotal).toBe(800);
  });

  it("material sin unit_cost no fabrica montos (0, no NaN)", () => {
    const p = computeLinePreviews(
      [{ ...HARINA, id: "m2", unit_cost: null }],
      [{ material_id: "m2", quantity_used: "2" }],
      [],
      []
    );
    expect(p.materialTotals).toEqual([0]);
  });
});

describe("ProductLines preview (F2)", () => {
  it("sin toggle: no muestra columnas de total", () => {
    renderWithProviders(
      <ProductLines
        materials={[HARINA]}
        materialLines={[{ material_id: "m1", quantity_used: "2" }]}
        laborLines={[]}
        extraCostLines={[]}
        showPreview={false}
      />
    );
    expect(screen.queryByText(/Total estimado/)).not.toBeInTheDocument();
    expect(screen.queryByText("Total")).not.toBeInTheDocument();
  });

  it("con toggle: muestra total por fila y total general en pesos", () => {
    renderWithProviders(
      <ProductLines
        materials={[HARINA]}
        materialLines={[{ material_id: "m1", quantity_used: "2" }]}
        laborLines={[
          { activity_name: "Coccion", hourly_rate: "3000", minutes_required: "120" },
        ]}
        extraCostLines={[]}
        showPreview
      />
    );
    expect(screen.getAllByText("3.000").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Total estimado: 9.000")).toBeInTheDocument();
  });
});
