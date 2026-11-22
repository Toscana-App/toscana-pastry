import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import Dashboard from "./Dashboard";
import type { DashboardResponse } from "@/types/calc";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("@/services/calcProductsService", () => ({
  calcProductsService: { getDashboard: vi.fn() },
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: vi.fn() },
}));
vi.mock("./DashboardCharts", () => ({
  default: () => <div data-testid="dashboard-charts" />,
}));

import { calcProductsService } from "@/services/calcProductsService";

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

describe("Dashboard", () => {
  beforeEach(() => {
    vi.mocked(calcProductsService.getDashboard).mockResolvedValue(data);
  });

  it("formats money amounts as ARS currency", async () => {
    render(<Dashboard />);
    await waitFor(() => expect(screen.getByText("Productos Activos")).toBeInTheDocument());
    expect(screen.getAllByText(/3[.,]100[.,]00/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/1[.,]500[.,]00/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/1[.,]200[.,]00/).length).toBeGreaterThan(0);
  });

  it("renders the charts section with the dashboard data", async () => {
    render(<Dashboard />);
    expect(await screen.findByTestId("dashboard-charts")).toBeInTheDocument();
  });
});
