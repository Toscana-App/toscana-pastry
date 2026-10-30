import type { ReactNode } from "react";
import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../../../test-utils";
import MaterialesPage from "./page";

// Captura los props que recibe ProtectedRoute (vi.hoisted por el hoisting
// de vi.mock).
const { capturedProps } = vi.hoisted(() => ({
  capturedProps: [] as { requiredRole?: string; children?: ReactNode }[],
}));

vi.mock("@/components/auth/ProtectedRoute", () => ({
  ProtectedRoute: (props: { requiredRole?: string; children?: ReactNode }) => {
    capturedProps.push(props);
    return <div>{props.children}</div>;
  },
}));
vi.mock("@/services/calcMaterialsService", () => ({
  calcMaterialsService: {
    listMaterials: vi.fn().mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
    }),
    getMaterial: vi.fn(),
    createMaterial: vi.fn(),
    updateMaterial: vi.fn(),
    deleteMaterial: vi.fn(),
    listCostHistory: vi.fn(),
  },
}));
vi.mock("@/services/calcSettingsService", () => ({
  calcSettingsService: {
    listCategories: vi.fn().mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 100,
    }),
    listSuppliers: vi.fn().mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 100,
    }),
  },
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: vi.fn() },
}));

describe("MaterialesPage", () => {
  it("renders ProtectedRoute with requiredRole=admin, the heading and MaterialsAbm", async () => {
    render(<MaterialesPage />);

    expect(await screen.findByText("Materiales")).toBeInTheDocument();
    expect(capturedProps[0]?.requiredRole).toBe("admin");
    // El listado (vía MaterialsAbm) llega montado: estado vacío visible.
    expect(
      await screen.findByText("Sin materiales")
    ).toBeInTheDocument();
  });
});
