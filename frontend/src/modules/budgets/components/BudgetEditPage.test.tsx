import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "@/providers/ChakraProvider";
import { BudgetEditPage } from "./BudgetEditPage";
import type { BudgetDetail } from "../types";

const mocks = vi.hoisted(() => ({
  getDetail: vi.fn(),
  update: vi.fn(),
  list: vi.fn(),
  push: vi.fn(),
}));

vi.mock("../service", () => ({
  budgetsService: { getDetail: mocks.getDetail, update: mocks.update },
}));
vi.mock("@/modules/products/service", () => ({
  productsService: { list: mocks.list },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

function item(i: number, overridden: boolean) {
  return {
    id: `i${i}`,
    product_id: `p${i}`,
    product_name: `Prod ${i}`,
    qty: 1,
    unit_cost: 100,
    unit_selling: 1500,
    line_cost: 100,
    line_selling: 1500,
    price_overridden: overridden,
  };
}

function budget(over: Partial<BudgetDetail> = {}): BudgetDetail {
  return {
    id: "b1",
    seq: 1,
    status: "borrador",
    calculation_mode: "manual",
    margin_pct: null,
    items: [item(1, true), item(2, false), item(3, false)],
    ...over,
  } as unknown as BudgetDetail;
}

function renderPage() {
  return render(
    <Provider>
      <BudgetEditPage budgetId="b1" />
    </Provider>,
  );
}

beforeEach(() => {
  mocks.list.mockResolvedValue({
    items: [1, 2, 3].map((n) => ({ id: `p${n}`, name: `Prod ${n}`, price_final: 1000 })),
    total: 3,
    page: 1,
    page_size: 100,
  });
  mocks.update.mockResolvedValue(budget());
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("BudgetEditPage", () => {
  it("preloads price only for lines with price_overridden in manual mode", async () => {
    mocks.getDetail.mockResolvedValue(budget());
    renderPage();
    expect(await screen.findByLabelText("Precio de la línea 1")).toHaveValue(15);
    expect(screen.getByLabelText("Precio de la línea 2")).toHaveValue(null);
    expect(screen.getByLabelText("Precio de la línea 3")).toHaveValue(null);
  });

  it("gives new rows a monotonic key after removing a middle row", async () => {
    const user = userEvent.setup();
    mocks.getDetail.mockResolvedValue(budget());
    renderPage();
    await screen.findByLabelText("Cantidad de la línea 1");
    await user.click(screen.getByLabelText("Quitar línea 1"));
    await user.click(screen.getByRole("button", { name: "+ Agregar producto" }));
    const qty3 = screen.getByLabelText("Cantidad de la línea 3");
    await user.clear(qty3);
    await user.type(qty3, "7");
    expect(screen.getByLabelText("Cantidad de la línea 1")).toHaveValue(1);
    expect(screen.getByLabelText("Cantidad de la línea 2")).toHaveValue(1);
    expect(qty3).toHaveValue(7);
  });

  it("sends price_override null for every line in cost_plus mode", async () => {
    const user = userEvent.setup();
    mocks.getDetail.mockResolvedValue(budget());
    renderPage();
    await screen.findByLabelText("Precio de la línea 1");
    await user.click(screen.getByRole("button", { name: "Costo + margen" }));
    await user.click(screen.getByRole("button", { name: "Guardar cambios" }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalled());
    const payload = mocks.update.mock.calls[0][1];
    expect(payload.items.map((i: { price_override: unknown }) => i.price_override)).toEqual([null, null, null]);
  });

  it("allows editing a sent budget and warns it needs resending", async () => {
    mocks.getDetail.mockResolvedValue(budget({ status: "enviado" }));
    renderPage();
    expect(await screen.findByRole("button", { name: "Guardar cambios" })).toBeInTheDocument();
    expect(screen.getByText(/hay que reenviarlo/)).toBeInTheDocument();
  });
});
