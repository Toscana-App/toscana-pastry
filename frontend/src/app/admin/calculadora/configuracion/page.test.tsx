import type { ReactNode } from "react";
import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../../../test-utils";
import CalculadoraConfigPage from "./page";

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

// El tab General se monta al cargar (ya visitado): mockeamos su fetch.
vi.mock("@/services/calcSettingsService", () => ({
  calcSettingsService: {
    getSettings: vi.fn().mockResolvedValue({
      business_name: "Toscana Pastry",
      main_currency_name: "Peso argentino",
      main_currency_symbol: "$",
      default_margin_percent: "30",
      default_discount_percent: "0",
      default_tax_percent: "19",
      rounding_mode: "none",
    }),
    updateSettings: vi.fn(),
    listCategories: vi.fn(),
    createCategory: vi.fn(),
    updateCategory: vi.fn(),
    deleteCategory: vi.fn(),
    listSuppliers: vi.fn(),
    createSupplier: vi.fn(),
    updateSupplier: vi.fn(),
    deleteSupplier: vi.fn(),
    listDefaultCosts: vi.fn(),
    createDefaultCost: vi.fn(),
    updateDefaultCost: vi.fn(),
    deleteDefaultCost: vi.fn(),
  },
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: vi.fn() },
}));

describe("CalculadoraConfigPage", () => {
  it("renders ProtectedRoute with requiredRole=admin, the heading and the 5 tabs", async () => {
    render(<CalculadoraConfigPage />);

    expect(
      await screen.findByText("Configuración de la calculadora")
    ).toBeInTheDocument();
    expect(capturedProps[0]?.requiredRole).toBe("admin");

    // Los 5 tabs del brief (S7).
    expect(
      screen.getByRole("tab", { name: "General" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Categorías de materiales" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Categorías de productos" })
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Proveedores" })).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Costos por defecto" })
    ).toBeInTheDocument();
  });
});
