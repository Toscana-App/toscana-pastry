import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import CategoryAbm from "./CategoryAbm";

// Seams: el service y el toaster. Se corre contra el endpoint
// "material-categories"; el de productos reusa el mismo componente.
vi.mock("@/services/calcSettingsService", () => ({
  calcSettingsService: {
    listCategories: vi.fn(),
    createCategory: vi.fn(),
    updateCategory: vi.fn(),
    deleteCategory: vi.fn(),
  },
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: vi.fn() },
}));

import { calcSettingsService } from "@/services/calcSettingsService";
import { toaster } from "@/lib/toaster";
import type { Category, CategoryListResponse } from "@/types/calc";

const pasta: Category = {
  id: "c1",
  name: "Pasta",
  description: "Base de pastas",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
const salsa: Category = {
  id: "c2",
  name: "Salsas",
  description: null,
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

function listResponse(items: Category[], total = items.length): CategoryListResponse {
  return { items, total, page: 1, page_size: 50 };
}

function setupList(items: Category[]) {
  vi.mocked(calcSettingsService.listCategories).mockResolvedValue(
    listResponse(items)
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  setupList([pasta, salsa]);
  vi.mocked(calcSettingsService.deleteCategory).mockResolvedValue(undefined);
});

const createNameInput = () => screen.getByLabelText("Nombre");
const createDescInput = () => screen.getByLabelText("Descripción");

async function openDeleteConfirm(name: string) {
  fireEvent.click(screen.getByRole("button", { name: `Eliminar ${name}` }));
  return screen.findByRole("dialog");
}

describe("CategoryAbm (material-categories)", () => {
  it("renders the items fetched from the API", async () => {
    render(<CategoryAbm endpoint="material-categories" title="Categorías de materiales" />);

    expect(await screen.findByText("Pasta")).toBeInTheDocument();
    expect(screen.getByText("Salsas")).toBeInTheDocument();
    expect(calcSettingsService.listCategories).toHaveBeenCalledWith(
      "material-categories",
      { q: undefined, page: 1, page_size: 50 }
    );
  });

  it("shows an empty state when there are no items", async () => {
    setupList([]);
    render(<CategoryAbm endpoint="material-categories" title="Categorías de materiales" />);

    expect(await screen.findByText("Sin categorías")).toBeInTheDocument();
    expect(screen.queryByText("Pasta")).not.toBeInTheDocument();
  });

  it("shows an error toast with a retry action when the list fails to load", async () => {
    vi.mocked(calcSettingsService.listCategories).mockRejectedValue(
      new Error("boom")
    );
    render(<CategoryAbm endpoint="material-categories" title="Categorías de materiales" />);

    await waitFor(() =>
      expect(toaster.create).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error", description: "boom" })
      )
    );
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("sends a POST with name and description and shows the new row", async () => {
    setupList([]);
    const nueva: Category = {
      id: "c3",
      name: "Hojaldres",
      description: "Masa hojaldrada",
      created_at: "2026-02-01T00:00:00Z",
      updated_at: "2026-02-01T00:00:00Z",
    };
    vi.mocked(calcSettingsService.createCategory).mockResolvedValue(nueva);

    render(<CategoryAbm endpoint="material-categories" title="Categorías de materiales" />);
    await screen.findByText("Sin categorías");

    fireEvent.change(createNameInput(), { target: { value: "Hojaldres" } });
    fireEvent.change(createDescInput(), { target: { value: "Masa hojaldrada" } });
    fireEvent.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() =>
      expect(calcSettingsService.createCategory).toHaveBeenCalledWith(
        "material-categories",
        { name: "Hojaldres", description: "Masa hojaldrada" }
      )
    );
    expect(await screen.findByText("Hojaldres")).toBeInTheDocument();
  });

  it("sends a PATCH with only the changed fields when editing a row", async () => {
    vi.mocked(calcSettingsService.updateCategory).mockResolvedValue({
      ...pasta,
      name: "Pasta fresca",
    });

    render(<CategoryAbm endpoint="material-categories" title="Categorías de materiales" />);
    await screen.findByText("Pasta");

    fireEvent.click(screen.getByRole("button", { name: "Editar Pasta" }));
    fireEvent.change(screen.getByLabelText("Editar nombre"), {
      target: { value: "Pasta fresca" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() =>
      expect(calcSettingsService.updateCategory).toHaveBeenCalledWith(
        "material-categories",
        "c1",
        { name: "Pasta fresca" }
      )
    );
  });

  it("removes the row after a confirmed DELETE returns 204", async () => {
    render(<CategoryAbm endpoint="material-categories" title="Categorías de materiales" />);
    await screen.findByText("Pasta");

    await openDeleteConfirm("Pasta");
    fireEvent.click(screen.getByRole("button", { name: "Eliminar" }));

    await waitFor(() =>
      expect(calcSettingsService.deleteCategory).toHaveBeenCalledWith(
        "material-categories",
        "c1"
      )
    );
    await waitFor(() =>
      expect(screen.queryByText("Pasta")).not.toBeInTheDocument()
    );
    expect(screen.getByText("Salsas")).toBeInTheDocument();
    expect(toaster.create).toHaveBeenCalledWith(
      expect.objectContaining({ type: "success" })
    );
  });

  it("keeps the row intact and shows a danger toast when DELETE returns 409 in-use", async () => {
    // El 409 in-use viaja como {"in_use_by": N} sin `detail`: apiFetch cae
    // en su fallback "Network error".
    vi.mocked(calcSettingsService.deleteCategory).mockRejectedValue(
      new Error("Network error")
    );

    render(<CategoryAbm endpoint="material-categories" title="Categorías de materiales" />);
    await screen.findByText("Pasta");

    await openDeleteConfirm("Pasta");
    fireEvent.click(screen.getByRole("button", { name: "Eliminar" }));

    await waitFor(() =>
      expect(toaster.create).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "error",
          description: "No se puede eliminar: está en uso",
        })
      )
    );
    expect(screen.getByText("Pasta")).toBeInTheDocument();
  });

  it("refetches with ?q when the search input is debounced", async () => {
    render(<CategoryAbm endpoint="material-categories" title="Categorías de materiales" />);
    await screen.findByText("Pasta");
    expect(calcSettingsService.listCategories).toHaveBeenCalledTimes(1);

    // Debounce real de 300 ms: waitFor (timeout 1 s) lo cubre.
    fireEvent.change(screen.getByLabelText("Buscar"), {
      target: { value: "sal" },
    });

    await waitFor(() =>
      expect(calcSettingsService.listCategories).toHaveBeenLastCalledWith(
        "material-categories",
        { q: "sal", page: 1, page_size: 50 }
      )
    );
  });
});
