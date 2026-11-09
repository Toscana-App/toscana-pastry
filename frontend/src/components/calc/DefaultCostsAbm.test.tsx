import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import DefaultCostsAbm from "./DefaultCostsAbm";

vi.mock("@/services/calcSettingsService", () => ({
  calcSettingsService: {
    listDefaultCosts: vi.fn(),
    createDefaultCost: vi.fn(),
    updateDefaultCost: vi.fn(),
    deleteDefaultCost: vi.fn(),
  },
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: vi.fn() },
}));

import { calcSettingsService } from "@/services/calcSettingsService";
import type { DefaultCost, DefaultCostListResponse } from "@/types/calc";

const manoDeObra: DefaultCost = {
  id: "d1",
  name: "Mano de obra",
  type: "labor",
  default_unit_cost_or_rate: "250.00",
  default_quantity_or_minutes: "30",
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function setupList(items: DefaultCost[] = [manoDeObra]) {
  const response: DefaultCostListResponse = {
    items,
    total: items.length,
    page: 1,
    page_size: 50,
  };
  vi.mocked(calcSettingsService.listDefaultCosts).mockResolvedValue(response);
}

beforeEach(() => {
  vi.clearAllMocks();
  setupList();
});

describe("DefaultCostsAbm", () => {
  it("renders the default costs fetched from the API", async () => {
    render(<DefaultCostsAbm />);

    expect(await screen.findByText("250.00")).toBeInTheDocument();
  });

  it("creates a default cost with allow-list type/status and non-negative amounts", async () => {
    const nuevo: DefaultCost = {
      id: "d2",
      name: "Embalaje",
      type: "extra_cost",
      default_unit_cost_or_rate: "12.50",
      default_quantity_or_minutes: "1",
      status: "active",
      created_at: "2026-02-01T00:00:00Z",
      updated_at: "2026-02-01T00:00:00Z",
    };
    vi.mocked(calcSettingsService.createDefaultCost).mockResolvedValue(nuevo);

    render(<DefaultCostsAbm />);
    await screen.findByText("250.00");

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Embalaje" },
    });
    fireEvent.click(screen.getByRole("combobox", { name: /Tipo/ }));
    fireEvent.click(await screen.findByRole("option", { name: "Costo extra" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("option", { name: "Costo extra" })
      ).not.toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("combobox", { name: /Estado/ }));
    fireEvent.click(await screen.findByRole("option", { name: "Inactivo" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("option", { name: "Inactivo" })
      ).not.toBeInTheDocument()
    );

    fireEvent.change(screen.getByLabelText("Costo unitario o tarifa"), {
      target: { value: "12.50" },
    });
    fireEvent.change(screen.getByLabelText("Cantidad o minutos"), {
      target: { value: "1" },
    });
    setupList([manoDeObra, nuevo]);
    fireEvent.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() =>
      expect(calcSettingsService.createDefaultCost).toHaveBeenCalledWith({
        name: "Embalaje",
        type: "extra_cost",
        default_unit_cost_or_rate: "12.50",
        default_quantity_or_minutes: "1",
        status: "inactive",
      })
    );
    expect(await screen.findByText("Embalaje")).toBeInTheDocument();
  });

  it("does not send the request when an amount is negative", async () => {
    render(<DefaultCostsAbm />);
    await screen.findByText("250.00");

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Costo inválido" },
    });
    fireEvent.change(screen.getByLabelText("Costo unitario o tarifa"), {
      target: { value: "-5" },
    });
    fireEvent.change(screen.getByLabelText("Cantidad o minutos"), {
      target: { value: "1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear" }));

    expect(calcSettingsService.createDefaultCost).not.toHaveBeenCalled();
  });

  it("keeps the search input mounted and focused after the debounce refetch", async () => {
    render(<DefaultCostsAbm />);
    await screen.findByText("250.00");

    const input = screen.getByLabelText("Buscar");
    input.focus();
    fireEvent.change(input, { target: { value: "x" } });

    await waitFor(() =>
      expect(calcSettingsService.listDefaultCosts).toHaveBeenCalledTimes(2)
    );
    await screen.findByText("250.00");
    expect(screen.getByLabelText("Buscar")).toBe(input);
    expect(input).toHaveFocus();
  });
});
