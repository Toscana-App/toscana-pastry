import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import CostHistoryDialog from "./CostHistoryDialog";
import type {
  CostHistoryListResponse,
  Material,
} from "@/types/calc";

// Seams: el service (fetch del endpoint) y el toaster.
vi.mock("@/services/calcMaterialsService", () => ({
  calcMaterialsService: {
    listCostHistory: vi.fn(),
  },
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: vi.fn() },
}));

import { calcMaterialsService } from "@/services/calcMaterialsService";
import { toaster } from "@/lib/toaster";

const harina: Material = {
  id: "m1",
  name: "Harina 000",
  internal_code: null,
  category_id: null,
  supplier_id: null,
  unit_of_measure: null,
  purchase_total_price: null,
  package_quantity: null,
  unit_cost: null,
  notes: null,
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function historyResponse(
  items: CostHistoryListResponse["items"],
  total = items.length
): CostHistoryListResponse {
  return { items, total, page: 1, page_size: 50 };
}

// El backend devuelve el historial en orden desc (más recientes primero);
// el diálogo lo muestra tal cual.
const historyItems: CostHistoryListResponse["items"] = [
  {
    previous_unit_cost: "95.00",
    new_unit_cost: "100.00",
    changed_at: "2026-03-10T15:30:00Z",
  },
  {
    previous_unit_cost: null,
    new_unit_cost: "95.00",
    changed_at: "2026-01-05T09:00:00Z",
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(calcMaterialsService.listCostHistory).mockResolvedValue(
    historyResponse(historyItems)
  );
});

describe("CostHistoryDialog", () => {
  it("fetches the history for the material id and renders rows desc with previous/new/fecha", async () => {
    render(<CostHistoryDialog material={harina} onClose={vi.fn()} />);

    await waitFor(() =>
      expect(calcMaterialsService.listCostHistory).toHaveBeenCalledWith(
        "m1",
        { page: 1, page_size: 50 }
      )
    );

    const rows = await screen.findAllByRole("row");
    // rows[0] = header; los datos llegan del endpoint ya en desc.
    expect(rows[1]).toHaveTextContent("95.00");
    expect(rows[1]).toHaveTextContent("100.00");
    expect(rows[2]).toHaveTextContent("95.00");
    // previous_unit_cost null → "—"
    expect(rows[2].textContent).toContain("—");
  });

  it("shows the empty message when there are no changes", async () => {
    vi.mocked(calcMaterialsService.listCostHistory).mockResolvedValue(
      historyResponse([])
    );
    render(<CostHistoryDialog material={harina} onClose={vi.fn()} />);

    expect(
      await screen.findByText("Sin cambios de costo registrados.")
    ).toBeInTheDocument();
  });

  it("shows an error toast with a retry action when the fetch fails", async () => {
    vi.mocked(calcMaterialsService.listCostHistory)
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue(historyResponse(historyItems));
    render(<CostHistoryDialog material={harina} onClose={vi.fn()} />);

    await waitFor(() =>
      expect(toaster.create).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error", description: "boom" })
      )
    );
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await waitFor(() =>
      expect(
        calcMaterialsService.listCostHistory
      ).toHaveBeenCalledTimes(2)
    );
    expect(await screen.findByText("100.00")).toBeInTheDocument();
  });

  it("paginates with prev/next when there is more than one page", async () => {
    vi.mocked(calcMaterialsService.listCostHistory)
      .mockResolvedValueOnce(
        historyResponse(historyItems, 120) // total 120 → 3 páginas
      )
      .mockResolvedValueOnce(
        historyResponse([{ previous_unit_cost: "10", new_unit_cost: "12", changed_at: "2025-12-01T00:00:00Z" }], 120)
      );
    render(<CostHistoryDialog material={harina} onClose={vi.fn()} />);

    await screen.findByText("100.00");
    // Página 1: "Anterior" deshabilitado, "Siguiente" habilitado.
    expect(
      screen.getByRole("button", { name: "Anterior" })
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));

    await waitFor(() =>
      expect(calcMaterialsService.listCostHistory).toHaveBeenLastCalledWith(
        "m1",
        { page: 2, page_size: 50 }
      )
    );
    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Anterior" })
    ).toBeEnabled();
  });
});
