import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import MaterialForm from "./MaterialForm";
import type { Category, Material, Supplier } from "@/types/calc";

// Seams: el form emite payloads vía onSubmit (publico); no hay service ni
// toaster acá — la validación y la construcción del payload son su contrato.
const categories: Category[] = [
  {
    id: "cat1",
    name: "Masa",
    description: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];
const suppliers: Supplier[] = [
  {
    id: "s1",
    name: "Distribuidora X",
    contact_name: null,
    phone: null,
    email: null,
    notes: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];
const manteca: Material = {
  id: "m1",
  name: "Manteca",
  internal_code: "MAN-001",
  category_id: "cat1",
  supplier_id: "s1",
  unit_of_measure: "kg",
  purchase_total_price: "1000",
  package_quantity: "10",
  unit_cost: "100.00",
  notes: "De primera calidad",
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("MaterialForm", () => {
  it("builds a full create payload without unit_cost/status and calls onSubmit", async () => {
    const onSubmit = vi.fn();
    render(
      <MaterialForm
        categories={categories}
        suppliers={suppliers}
        onSubmit={onSubmit}
      />
    );

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Harina 000" },
    });
    fireEvent.change(screen.getByLabelText("Código interno"), {
      target: { value: "HAR-001" },
    });
    fireEvent.click(screen.getByRole("combobox", { name: "Categoría" }));
    fireEvent.click(await screen.findByRole("option", { name: "Masa" }));
    // Un tick para que el dropdown de categoría cierre antes de abrir el
    // de proveedor (dos listboxes simultáneos confunden el click en jsdom).
    await new Promise((resolve) => setTimeout(resolve, 50));
    fireEvent.click(screen.getByRole("combobox", { name: "Proveedor" }));
    fireEvent.click(
      await screen.findByRole("option", { name: "Distribuidora X" })
    );
    // La selección del listbox aterriza asincrónicamente (Ark UI): se
    // espera un tick antes de los cambios siguientes.
    await new Promise((resolve) => setTimeout(resolve, 50));
    fireEvent.change(screen.getByLabelText("Unidad de medida"), {
      target: { value: "kg" },
    });
    fireEvent.change(screen.getByLabelText("Precio del paquete"), {
      target: { value: "2500" },
    });
    fireEvent.change(screen.getByLabelText("Cantidad por paquete"), {
      target: { value: "25" },
    });
    fireEvent.change(screen.getByLabelText("Notas"), {
      target: { value: "Sin levadura" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({
      name: "Harina 000",
      internal_code: "HAR-001",
      category_id: "cat1",
      supplier_id: "s1",
      unit_of_measure: "kg",
      purchase_total_price: 2500,
      package_quantity: 25,
      notes: "Sin levadura",
    });
    const payload = onSubmit.mock.calls[0][0] as Record<string, unknown>;
    // RF-P2CC-02/03 + extra="forbid": unit_cost/status nunca en el payload.
    expect("unit_cost" in payload).toBe(false);
    expect("status" in payload).toBe(false);
  });

  it("sends a minimal payload with only the name when the rest is empty", () => {
    const onSubmit = vi.fn();
    render(
      <MaterialForm
        categories={categories}
        suppliers={suppliers}
        onSubmit={onSubmit}
      />
    );

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Manteca" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onSubmit).toHaveBeenCalledWith({ name: "Manteca" });
  });

  it("preloads the initial material values when editing", () => {
    render(
      <MaterialForm
        initial={manteca}
        categories={categories}
        suppliers={suppliers}
        onSubmit={vi.fn()}
      />
    );

    expect(screen.getByLabelText("Nombre")).toHaveValue("Manteca");
    expect(screen.getByLabelText("Código interno")).toHaveValue("MAN-001");
    expect(screen.getByLabelText("Unidad de medida")).toHaveValue("kg");
    // Inputs number: jsdom expone el value ya convertido a number.
    expect(screen.getByLabelText("Precio del paquete")).toHaveValue(1000);
    expect(screen.getByLabelText("Cantidad por paquete")).toHaveValue(10);
    expect(screen.getByLabelText("Notas")).toHaveValue(
      "De primera calidad"
    );
    expect(
      screen.getByRole("combobox", { name: "Categoría" })
    ).toHaveTextContent("Masa");
    expect(
      screen.getByRole("combobox", { name: "Proveedor" })
    ).toHaveTextContent("Distribuidora X");
  });

  it("does not call onSubmit when the name is empty", () => {
    const onSubmit = vi.fn();
    render(
      <MaterialForm
        categories={categories}
        suppliers={suppliers}
        onSubmit={onSubmit}
      />
    );

    fireEvent.change(screen.getByLabelText("Precio del paquete"), {
      target: { value: "10" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("does not call onSubmit when the package price is negative", () => {
    const onSubmit = vi.fn();
    render(
      <MaterialForm
        categories={categories}
        suppliers={suppliers}
        onSubmit={onSubmit}
      />
    );

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Harina" },
    });
    fireEvent.change(screen.getByLabelText("Precio del paquete"), {
      target: { value: "-5" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "El precio del paquete no puede ser negativo."
    );
  });

  it("shows an error when the package quantity is 0 or less", () => {
    const onSubmit = vi.fn();
    render(
      <MaterialForm
        categories={categories}
        suppliers={suppliers}
        onSubmit={onSubmit}
      />
    );

    fireEvent.change(screen.getByLabelText("Nombre"), {
      target: { value: "Harina" },
    });
    fireEvent.change(screen.getByLabelText("Cantidad por paquete"), {
      target: { value: "0" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "La cantidad por paquete debe ser mayor a 0."
    );
  });

  it("shows an error instead of submitting an edit with no changes", () => {
    const onSubmit = vi.fn();
    render(
      <MaterialForm
        initial={manteca}
        categories={categories}
        suppliers={suppliers}
        onSubmit={onSubmit}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "No hay cambios para guardar."
    );
  });

  it("sends null for category_id and supplier_id when cleared while editing", async () => {
    const onSubmit = vi.fn();
    render(
      <MaterialForm
        initial={manteca}
        categories={categories}
        suppliers={suppliers}
        onSubmit={onSubmit}
      />
    );

    fireEvent.click(screen.getByRole("combobox", { name: "Categoría" }));
    fireEvent.click(
      await screen.findByRole("option", { name: "Sin categoría" })
    );
    await waitFor(() =>
      expect(
        screen.getByRole("combobox", { name: "Categoría" })
      ).toHaveTextContent("Sin categoría")
    );
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    expect(onSubmit).toHaveBeenLastCalledWith({ category_id: null });

    fireEvent.click(screen.getByRole("combobox", { name: "Proveedor" }));
    fireEvent.click(
      await screen.findByRole("option", { name: "Sin proveedor" })
    );
    await waitFor(() =>
      expect(
        screen.getByRole("combobox", { name: "Proveedor" })
      ).toHaveTextContent("Sin proveedor")
    );
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    expect(onSubmit).toHaveBeenLastCalledWith({
      category_id: null,
      supplier_id: null,
    });
  });
});
