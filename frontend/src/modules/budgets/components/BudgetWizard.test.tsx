import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "@/providers/ChakraProvider";
import { BudgetWizard } from "./BudgetWizard";

/** Pins the PR #15 review fixes in the wizard: row keys and override-only-in-manual. */
const mocks = vi.hoisted(() => ({ create: vi.fn(), list: vi.fn(), push: vi.fn() }));

vi.mock("../service", () => ({ budgetsService: { create: mocks.create } }));
vi.mock("@/modules/products/service", () => ({ productsService: { list: mocks.list } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

const row = (key: number, product_id = "", price = "") => ({ key, product_id, qty: "1", price });

function seedDraft(mode: "manual" | "cost_plus", rows: ReturnType<typeof row>[], step = 2) {
  window.sessionStorage.setItem(
    "budget_wizard_draft",
    JSON.stringify({
      step,
      name: "Ana",
      phone: "1",
      customer: { id: "c1", name: "Ana", phone: "1" },
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
