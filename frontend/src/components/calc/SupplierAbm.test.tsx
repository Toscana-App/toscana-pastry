import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import SupplierAbm from "./SupplierAbm";

// Seams: el service y el toaster. Sin backend real (PREGUNTAS.md → F1).
vi.mock("@/services/calcSettingsService", () => ({
  calcSettingsService: {
    listSuppliers: vi.fn(),
    createSupplier: vi.fn(),
    updateSupplier: vi.fn(),
    deleteSupplier: vi.fn(),
  },
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: vi.fn() },
}));

import { calcSettingsService } from "@/services/calcSettingsService";
import { toaster } from "@/lib/toaster";
import type { Supplier, SupplierListResponse } from "@/types/calc";

const molino: Supplier = {
  id: "s1",
  name: "Molino del Valle",
  contact_name: "Carla Ruiz",
  phone: "11-5555-0000",
  email: "ventas@molino.com",
  notes: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function setupList(items: Supplier[] = [molino]) {
  const response: SupplierListResponse = {
    items,
    total: items.length,
    page: 1,
    page_size: 50,
  };
  vi.mocked(calcSettingsService.listSuppliers).mockResolvedValue(response);
}

beforeEach(() => {
  vi.clearAllMocks();
  setupList();
});

describe("SupplierAbm", () => {
  it("renders the suppliers fetched from the API", async () => {
    render(<SupplierAbm />);

    expect(await screen.findByText("Molino del Valle")).toBeInTheDocument();
    expect(screen.getByText("ventas@molino.com")).toBeInTheDocument();
  });

  it("creates a supplier with all 5 fields", async () => {
    const nuevo: Supplier = {
      id: "s2",
      name: "Lácteos Sur",
      contact_name: "Pablo Gómez",
      phone: "221-444-3333",
      email: "pedidos@lacteos.com",
      notes: "Envíos los martes",
      created_at: "2026-02-01T00:00:00Z",
      updated_at: "2026-02-01T00:00:00Z",
    };
    vi.mocked(calcSettingsService.createSupplier).mockResolvedValue(nuevo);

    render(<SupplierAbm />);
    await screen.findByText("Molino del Valle");

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Lácteos Sur" },
    });
    fireEvent.change(screen.getByLabelText("Contacto"), {
      target: { value: "Pablo Gómez" },
    });
    fireEvent.change(screen.getByLabelText("Teléfono"), {
      target: { value: "221-444-3333" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "pedidos@lacteos.com" },
    });
    fireEvent.change(screen.getByLabelText("Notas"), {
      target: { value: "Envíos los martes" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() =>
      expect(calcSettingsService.createSupplier).toHaveBeenCalledWith({
        name: "Lácteos Sur",
        contact_name: "Pablo Gómez",
        phone: "221-444-3333",
        email: "pedidos@lacteos.com",
        notes: "Envíos los martes",
      })
    );
    expect(await screen.findByText("Lácteos Sur")).toBeInTheDocument();
  });

  it("shows an error toast with the API detail when the email is invalid", async () => {
    vi.mocked(calcSettingsService.createSupplier).mockRejectedValue(
      new Error("email invalido")
    );

    render(<SupplierAbm />);
    await screen.findByText("Molino del Valle");

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Proveedor" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "no-es-un-email" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() =>
      expect(toaster.create).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "error",
          description: "email invalido",
        })
      )
    );
  });
});
