import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import DashboardCharts from "./DashboardCharts";
import type { DashboardResponse } from "@/types/calc";

const data: DashboardResponse = {
  active_materials: 4,
  active_products: 3,
  draft_products: 1,
  incomplete_materials: 2,
  avg_product_cost: 150000,
  avg_final_price: 310000,
  top_by_price: [
    { id: "p1", name: "Torta", final_sale_price: 310000, margin_percent: "35.00" },
  ],
  bottom_by_margin: [
    { id: "p2", name: "Alfajor", product_total_cost: 120000, margin_percent: "5.00" },
  ],
};

const empty: DashboardResponse = {
  ...data,
  active_materials: 0,
  active_products: 0,
  draft_products: 0,
  incomplete_materials: 0,
  avg_product_cost: 0,
  avg_final_price: 0,
  top_by_price: [],
  bottom_by_margin: [],
};

describe("DashboardCharts", () => {
  it("exposes each chart as an image with a textual summary", () => {
    render(<DashboardCharts dashboard={data} />);
    expect(screen.getAllByRole("img")).toHaveLength(5);
    expect(
      screen.getByRole("img", { name: "Productos: 3 activos y 1 en borrador" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Materiales: 4 activos y 2 incompletos" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Margen de los 1 productos con menor margen: Alfajor 5%/ })
    ).toBeInTheDocument();
  });

  it("shows an empty state instead of charts when there is no data", () => {
    render(<DashboardCharts dashboard={empty} />);
    expect(screen.queryAllByRole("img")).toHaveLength(0);
    expect(screen.getAllByText("Sin datos para mostrar")).toHaveLength(5);
  });
});
