import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "@/providers/ChakraProvider";
import { BudgetWizard } from "./BudgetWizard";

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  list: vi.fn(),
  push: vi.fn(),
  createWithAdoption: vi.fn(),
  updateAddress: vi.fn(),
}));

vi.mock("../service", () => ({ budgetsService: { create: mocks.create } }));
vi.mock("@/modules/orders/service", () => ({
  customersService: {
    create: mocks.create,
    createWithAdoption: mocks.createWithAdoption,
    updateAddress: mocks.updateAddress,
  },
}));
vi.mock("@/modules/products/service", () => ({ productsService: { list: mocks.list } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

const row = (key: number, product_id = "", price = "") => ({ key, product_id, qty: "1", price });

function seedDraft(
  mode: "manual" | "cost_plus",
  rows: ReturnType<typeof row>[],
  step = 2,
  deliveryAddress = "",
  customerAddress: string | null = null,
) {
  window.sessionStorage.setItem(
    "budget_wizard_draft",
    JSON.stringify({
      step,
      name: "Ana",
      phone: "1",
      deliveryAddress,
      customer: { id: "c1", name: "Ana", phone: "1", delivery_address: customerAddress },
      mode,
      margin: "",
      rows,
    }),
  );
}

function renderWizard() {
  return render(
    <Provider>
      <BudgetWizard />
    </Provider>,
  );
}

beforeEach(() => {
  window.sessionStorage.clear();
  mocks.list.mockResolvedValue({
    items: [{ id: "p1", name: "Prod 1", price_final: 1000 }],
    total: 1,
    page: 1,
    page_size: 100,
  });
  mocks.create.mockResolvedValue({ id: "b1" });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("BudgetWizard", () => {
  it("gives new rows a monotonic key after removing a middle row", async () => {
    const user = userEvent.setup();
    seedDraft("cost_plus", [row(1), row(2), row(3)]);
    renderWizard();
    await user.click(await screen.findByLabelText("Quitar línea 1"));
    await user.click(screen.getByRole("button", { name: "+ Agregar producto" }));
    const qty3 = screen.getByLabelText("Cantidad de la línea 3");
    await user.clear(qty3);
    await user.type(qty3, "7");
    expect(screen.getByLabelText("Cantidad de la línea 1")).toHaveValue(1);
    expect(screen.getByLabelText("Cantidad de la línea 2")).toHaveValue(1);
    expect(qty3).toHaveValue(7);
  });

  it("does not send price_override in cost_plus even if the draft kept prices", async () => {
    const user = userEvent.setup();
    seedDraft("cost_plus", [row(1, "p1", "25")], 3);
    renderWizard();
    await user.click(await screen.findByRole("button", { name: "Guardar presupuesto" }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalled());
    expect(mocks.create.mock.calls[0][0].items[0].price_override).toBeNull();
  });

  it("sends price_override in cents in manual mode", async () => {
    const user = userEvent.setup();
    seedDraft("manual", [row(1, "p1", "25")], 3);
    renderWizard();
    await user.click(await screen.findByRole("button", { name: "Guardar presupuesto" }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalled());
    expect(mocks.create.mock.calls[0][0].items[0].price_override).toBe(2500);
  });
});

describe("BudgetWizard — dirección de entrega (RF-P7-03/06/07)", () => {
  it("paso 1: envía la dirección al crear el cliente", async () => {
    const user = userEvent.setup();
    mocks.createWithAdoption.mockResolvedValue({
      customer: { id: "c1", name: "Ana", phone: "112233", delivery_address: "Calle 1" },
      adopted: false,
    });
    renderWizard();

    await user.type(screen.getByLabelText("Nombre del cliente"), "Ana");
    await user.type(screen.getByLabelText("Teléfono del cliente"), "112233");
    await user.type(screen.getByLabelText("Dirección de entrega del cliente"), "Calle 1");
    await user.click(screen.getByRole("button", { name: "Continuar" }));

    await waitFor(() => expect(mocks.createWithAdoption).toHaveBeenCalledTimes(1));
    expect(mocks.createWithAdoption).toHaveBeenCalledWith({
      name: "Ana",
      phone: "112233",
      delivery_address: "Calle 1",
    });
  });

  it("paso 1: cliente duplicado → sugerencia 'Usar datos existentes' con prellenado editable", async () => {
    const user = userEvent.setup();
    mocks.createWithAdoption.mockResolvedValue({
      customer: { id: "c9", name: "Ana", phone: "112233", delivery_address: "Av. Rivadavia 100" },
      adopted: true,
    });
    renderWizard();

    await user.type(screen.getByLabelText("Nombre del cliente"), "Ana");
    await user.type(screen.getByLabelText("Teléfono del cliente"), "112233");
    await user.click(screen.getByRole("button", { name: "Continuar" }));

    const btn = await screen.findByRole("button", { name: "Usar datos existentes" });
    expect(screen.getByLabelText("Dirección de entrega del cliente")).toHaveValue("Av. Rivadavia 100");
    await user.click(btn);

    await screen.findByText("Modo de cálculo");
  });

  it("resumen: muestra la dirección y la envía al presupuesto", async () => {
    const user = userEvent.setup();
    seedDraft("cost_plus", [row(1, "p1")], 3, "Av. San Martín 1234");
    renderWizard();

    expect(screen.getByText("Entrega: Av. San Martín 1234")).toBeTruthy();
    await user.click(await screen.findByRole("button", { name: "Guardar presupuesto" }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1));
    expect(mocks.create.mock.calls[0][0].delivery_address).toBe("Av. San Martín 1234");
  });

  it("resumen: persiste la dirección cambiada en el cliente reutilizado (PATCH)", async () => {
    const user = userEvent.setup();
    mocks.updateAddress.mockResolvedValue({ id: "c1", name: "Ana", phone: "1" });
    seedDraft("cost_plus", [row(1, "p1")], 3, "Calle Nueva 456", null);
    renderWizard();

    await user.click(await screen.findByRole("button", { name: "Guardar presupuesto" }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mocks.updateAddress).toHaveBeenCalledWith("c1", "Calle Nueva 456"));
  });

  it("resumen: sin dirección no manda el campo ni hace PATCH al cliente", async () => {
    const user = userEvent.setup();
    seedDraft("cost_plus", [row(1, "p1")], 3);
    renderWizard();

    await user.click(await screen.findByRole("button", { name: "Guardar presupuesto" }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1));
    expect(mocks.create.mock.calls[0][0].delivery_address).toBeUndefined();
    expect(mocks.updateAddress).not.toHaveBeenCalled();
  });
});
