import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import MaterialsAbm from "./MaterialsAbm";
import type {
  Category,
  Material,
  MaterialListResponse,
  Supplier,
} from "@/types/calc";

vi.mock("@/services/calcMaterialsService", () => ({
  calcMaterialsService: {
    listMaterials: vi.fn(),
    getMaterial: vi.fn(),
    createMaterial: vi.fn(),
    updateMaterial: vi.fn(),
    deleteMaterial: vi.fn(),
    listCostHistory: vi.fn(),
  },
}));
vi.mock("@/services/calcSettingsService", () => ({
  calcSettingsService: {
    listCategories: vi.fn(),
    listSuppliers: vi.fn(),
  },
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: vi.fn() },
}));

import { calcMaterialsService } from "@/services/calcMaterialsService";
import { calcSettingsService } from "@/services/calcSettingsService";
import { toaster } from "@/lib/toaster";

const masa: Category = {
  id: "cat1",
  name: "Masa",
  description: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
const distribuidora: Supplier = {
  id: "s1",
  name: "Distribuidora X",
  contact_name: null,
  phone: null,
  email: null,
  notes: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const harina: Material = {
  id: "m1",
  name: "Harina 000",
  internal_code: "HAR-001",
  category_id: "cat1",
  supplier_id: "s1",
  unit_of_measure: "kg",
  purchase_total_price: "2500",
  package_quantity: "25",
  unit_cost: "100.00",
  notes: null,
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
const manteca: Material = {
  id: "m2",
  name: "Manteca",
  internal_code: null,
  category_id: null,
  supplier_id: null,
  unit_of_measure: null,
  purchase_total_price: null,
  package_quantity: null,
  unit_cost: null,
  notes: null,
  status: "incomplete",
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

function listResponse(
  items: Material[],
  total = items.length,
  page = 1
): MaterialListResponse {
  return { items, total, page, page_size: 50 };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(calcMaterialsService.listMaterials).mockResolvedValue(
    listResponse([harina, manteca])
  );
  vi.mocked(calcMaterialsService.createMaterial).mockResolvedValue(harina);
  vi.mocked(calcMaterialsService.updateMaterial).mockResolvedValue(harina);
  vi.mocked(calcMaterialsService.deleteMaterial).mockResolvedValue(undefined);
  vi.mocked(calcSettingsService.listCategories).mockResolvedValue({
    items: [masa],
    total: 1,
    page: 1,
    page_size: 100,
  });
  vi.mocked(calcSettingsService.listSuppliers).mockResolvedValue({
    items: [distribuidora],
    total: 1,
    page: 1,
    page_size: 100,
  });
});

async function openDeleteConfirm(name: string) {
  fireEvent.click(screen.getByRole("button", { name: `Eliminar ${name}` }));
  return screen.findByRole("dialog");
}

describe("MaterialsAbm", () => {
  it("renders the items fetched from the API with resolved category/supplier names", async () => {
    render(<MaterialsAbm />);

    expect(await screen.findByText("Harina 000")).toBeInTheDocument();
    expect(screen.getByText("HAR-001")).toBeInTheDocument();
    expect(screen.getByText("100.00")).toBeInTheDocument();
    expect(screen.getByText("Manteca")).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByText("Masa")).toBeInTheDocument();
    expect(within(table).getByText("Distribuidora X")).toBeInTheDocument();
    expect(calcMaterialsService.listMaterials).toHaveBeenCalledWith({
      q: undefined,
      category_id: undefined,
      supplier_id: undefined,
      status: undefined,
      page: 1,
      page_size: 50,
    });
  });

  it("shows the Incompleto chip and — for the unit cost of an incomplete material", async () => {
    render(<MaterialsAbm />);

    await screen.findByText("Manteca");
    const table = screen.getByRole("table");
    expect(within(table).getByText("Incompleto")).toBeInTheDocument();
    const mantecaRow = screen
      .getAllByRole("row")
      .find((row) => row.textContent?.includes("Manteca"));
    expect(mantecaRow?.textContent).toContain("—");
    expect(within(table).getByText("Activo")).toBeInTheDocument();
  });

  it("refetches with ?q when the search input is debounced, resetting page", async () => {
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");
    expect(calcMaterialsService.listMaterials).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByLabelText("Buscar"), {
      target: { value: "har" },
    });

    await waitFor(() =>
      expect(calcMaterialsService.listMaterials).toHaveBeenLastCalledWith({
        q: "har",
        category_id: undefined,
        supplier_id: undefined,
        status: undefined,
        page: 1,
        page_size: 50,
      })
    );
  });

  it("sends category_id when the category filter changes", async () => {
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");
    await waitFor(() =>
      expect(
        screen.getByRole("combobox", { name: "Filtrar por categoría" })
      ).toHaveTextContent("Todas")
    );

    fireEvent.click(
      screen.getByRole("combobox", { name: "Filtrar por categoría" })
    );
    fireEvent.click(
      await screen.findByRole("option", { name: "Masa" })
    );

    await waitFor(() =>
      expect(calcMaterialsService.listMaterials).toHaveBeenLastCalledWith(
        expect.objectContaining({ category_id: "cat1", page: 1 })
      )
    );
  });

  it.each([
    ["Filtrar por categoría", "Masa", "Todas", "category_id", "cat1"],
    ["Filtrar por proveedor", "Distribuidora X", "Todos", "supplier_id", "s1"],
    ["Filtrar por estado", "Incompleto", "Todos", "status", "incomplete"],
  ])(
    "drops the param when %s is set back to the all option",
    async (label, option, allLabel, param, value) => {
      render(<MaterialsAbm />);
      await screen.findByText("Harina 000");

      fireEvent.click(screen.getByRole("combobox", { name: label }));
      fireEvent.click(await screen.findByRole("option", { name: option }));
      await waitFor(() =>
        expect(calcMaterialsService.listMaterials).toHaveBeenLastCalledWith(
          expect.objectContaining({ [param]: value })
        )
      );

      fireEvent.click(screen.getByRole("combobox", { name: label }));
      fireEvent.click(await screen.findByRole("option", { name: allLabel }));
      await waitFor(() =>
        expect(calcMaterialsService.listMaterials).toHaveBeenLastCalledWith(
          expect.objectContaining({ [param]: undefined, page: 1 })
        )
      );
    }
  );

  it("sends supplier_id when the supplier filter changes", async () => {
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");

    fireEvent.click(
      screen.getByRole("combobox", { name: "Filtrar por proveedor" })
    );
    fireEvent.click(
      await screen.findByRole("option", { name: "Distribuidora X" })
    );

    await waitFor(() =>
      expect(calcMaterialsService.listMaterials).toHaveBeenLastCalledWith(
        expect.objectContaining({ supplier_id: "s1", page: 1 })
      )
    );
  });

  it("sends status when the status filter changes (solo active|incomplete, D1)", async () => {
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");

    fireEvent.click(
      screen.getByRole("combobox", { name: "Filtrar por estado" })
    );
    fireEvent.click(
      await screen.findByRole("option", { name: "Incompleto" })
    );

    await waitFor(() =>
      expect(calcMaterialsService.listMaterials).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: "incomplete", page: 1 })
      )
    );
  });

  it("paginates with next and disables it on the last page", async () => {
    vi.mocked(calcMaterialsService.listMaterials).mockResolvedValue(
      listResponse([harina, manteca], 120)
    );
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");
    expect(screen.getByText("Total: 120")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));

    await waitFor(() =>
      expect(calcMaterialsService.listMaterials).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 2 })
      )
    );
    vi.mocked(calcMaterialsService.listMaterials).mockResolvedValue(
      listResponse([harina, manteca], 120, 3)
    );
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() =>
      expect(calcMaterialsService.listMaterials).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 3 })
      )
    );
    expect(
      screen.getByRole("button", { name: "Siguiente" })
    ).toBeDisabled();
  });

  it("creates a material via POST without unit_cost/status and shows the new row", async () => {
    const nuevo: Material = {
      ...harina,
      id: "m9",
      name: "Rúcula",
    };
    vi.mocked(calcMaterialsService.createMaterial).mockResolvedValue(nuevo);
    vi.mocked(calcMaterialsService.listMaterials)
      .mockResolvedValueOnce(listResponse([]))
      .mockResolvedValue(listResponse([nuevo]));

    render(<MaterialsAbm />);
    await screen.findByText("Sin materiales");

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Rúcula" },
    });
    fireEvent.change(screen.getByLabelText("Precio del paquete"), {
      target: { value: "800" },
    });
    fireEvent.change(screen.getByLabelText("Cantidad por paquete"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() =>
      expect(calcMaterialsService.createMaterial).toHaveBeenCalledWith(
        { name: "Rúcula", purchase_total_price: 800, package_quantity: 2 }
      )
    );
    expect(await screen.findByText("Rúcula")).toBeInTheDocument();
    expect(calcMaterialsService.listMaterials).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText("Nombre")).toHaveValue("");
    expect(toaster.create).toHaveBeenCalledWith(
      expect.objectContaining({ type: "success" })
    );
  });

  it("does not send a POST when the package quantity is 0", async () => {
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Rúcula" },
    });
    fireEvent.change(screen.getByLabelText("Cantidad por paquete"), {
      target: { value: "0" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear" }));

    expect(calcMaterialsService.createMaterial).not.toHaveBeenCalled();
  });

  it("edits via PATCH with only the touched fields and null when the price is emptied", async () => {
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");

    fireEvent.click(
      screen.getByRole("button", { name: "Editar Harina 000" })
    );
    const dialog = await screen.findByRole("dialog");

    fireEvent.change(within(dialog).getByLabelText("Precio del paquete"), {
      target: { value: "" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Guardar" }));

    await waitFor(() =>
      expect(calcMaterialsService.updateMaterial).toHaveBeenCalledWith(
        "m1",
        { purchase_total_price: null }
      )
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
    expect(toaster.create).toHaveBeenCalledWith(
      expect.objectContaining({ type: "success" })
    );
  });

  it("keeps the edit dialog open and shows the 422 detail toast when PATCH fails", async () => {
    vi.mocked(calcMaterialsService.updateMaterial).mockRejectedValue(
      new Error("precio debe ser mayor o igual a 0")
    );
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");

    fireEvent.click(
      screen.getByRole("button", { name: "Editar Harina 000" })
    );
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Código interno"), {
      target: { value: "HAR-999" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Guardar" }));

    await waitFor(() =>
      expect(toaster.create).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "error",
          description: "precio debe ser mayor o igual a 0",
        })
      )
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("removes the row after a confirmed DELETE returns 204 by refetching", async () => {
    vi.mocked(calcMaterialsService.listMaterials)
      .mockResolvedValueOnce(listResponse([harina, manteca]))
      .mockResolvedValue(listResponse([manteca]));
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");

    await openDeleteConfirm("Harina 000");
    fireEvent.click(screen.getByRole("button", { name: "Eliminar" }));

    await waitFor(() =>
      expect(calcMaterialsService.deleteMaterial).toHaveBeenCalledWith("m1")
    );
    await waitFor(() =>
      expect(screen.queryByText("Harina 000")).not.toBeInTheDocument()
    );
    expect(screen.getByText("Manteca")).toBeInTheDocument();
    expect(calcMaterialsService.listMaterials).toHaveBeenCalledTimes(2);
    expect(toaster.create).toHaveBeenCalledWith(
      expect.objectContaining({ type: "success" })
    );
  });

  it("goes back one page when deleting the last row of a page > 1", async () => {
    vi.mocked(calcMaterialsService.listMaterials).mockImplementation(
      async (query) =>
        query?.page === 2
          ? listResponse([harina], 51, 2)
          : listResponse([manteca], 51, 1)
    );
    render(<MaterialsAbm />);
    await screen.findByText("Manteca");

    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await screen.findByText("Harina 000");

    vi.mocked(calcMaterialsService.listMaterials).mockImplementation(
      async (query) =>
        query?.page === 2
          ? listResponse([], 50, 2)
          : listResponse([manteca], 51, 1)
    );
    await openDeleteConfirm("Harina 000");
    fireEvent.click(screen.getByRole("button", { name: "Eliminar" }));

    await waitFor(() =>
      expect(calcMaterialsService.listMaterials).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 1 })
      )
    );
    expect(await screen.findByText("Manteca")).toBeInTheDocument();
  });

  it("keeps the row and shows the in-use danger toast when DELETE returns 409", async () => {
    vi.mocked(calcMaterialsService.deleteMaterial).mockRejectedValue(
      new Error("Network error")
    );
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");

    await openDeleteConfirm("Harina 000");
    fireEvent.click(screen.getByRole("button", { name: "Eliminar" }));

    await waitFor(() =>
      expect(toaster.create).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "error",
          description:
            "No se puede eliminar: el material está en uso en productos",
        })
      )
    );
    expect(screen.getByText("Harina 000")).toBeInTheDocument();
  });

  it("shows an empty state when there are no items", async () => {
    vi.mocked(calcMaterialsService.listMaterials).mockResolvedValue(
      listResponse([])
    );
    render(<MaterialsAbm />);

    expect(await screen.findByText("Sin materiales")).toBeInTheDocument();
  });

  it("shows an error toast with a retry action when the list fails to load", async () => {
    vi.mocked(calcMaterialsService.listMaterials)
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue(listResponse([harina, manteca]));
    render(<MaterialsAbm />);

    await waitFor(() =>
      expect(toaster.create).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error", description: "boom" })
      )
    );
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await waitFor(() =>
      expect(calcMaterialsService.listMaterials).toHaveBeenCalledTimes(2)
    );
    expect(await screen.findByText("Harina 000")).toBeInTheDocument();
  });

  it("loads the category/supplier filter options once on mount (not per render)", async () => {
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");

    expect(calcSettingsService.listCategories).toHaveBeenCalledTimes(1);
    expect(calcSettingsService.listCategories).toHaveBeenCalledWith(
      "material-categories",
      { page: 1, page_size: 100 }
    );
    expect(calcSettingsService.listSuppliers).toHaveBeenCalledTimes(1);
    expect(calcSettingsService.listSuppliers).toHaveBeenCalledWith({
      page: 1,
      page_size: 100,
    });

    fireEvent.change(screen.getByLabelText("Buscar"), {
      target: { value: "x" },
    });
    await waitFor(() =>
      expect(calcMaterialsService.listMaterials).toHaveBeenCalledTimes(2)
    );
    expect(calcSettingsService.listCategories).toHaveBeenCalledTimes(1);
    expect(calcSettingsService.listSuppliers).toHaveBeenCalledTimes(1);
  });

  it("opens the cost history dialog for a row", async () => {
    vi.mocked(calcMaterialsService.listCostHistory).mockResolvedValue({
      items: [
        {
          previous_unit_cost: "90",
          new_unit_cost: "100.00",
          changed_at: "2026-03-10T15:30:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
    });
    render(<MaterialsAbm />);
    await screen.findByText("Harina 000");

    fireEvent.click(
      screen.getByRole("button", { name: "Historial Harina 000" })
    );

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Historial de costos");
    await waitFor(() =>
      expect(
        calcMaterialsService.listCostHistory
      ).toHaveBeenCalledWith("m1", { page: 1, page_size: 50 })
    );
    expect(await within(dialog).findByText("100.00")).toBeInTheDocument();
  });
});
