import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "@/providers/ChakraProvider";
import { ProductsPage } from "./ProductsPage";

const mocks = vi.hoisted(() => ({
  setQuery: vi.fn(),
  setCategory: vi.fn(),
  goToPage: vi.fn(),
  reload: vi.fn(),
  state: {
    items: [] as Array<{
      id: string;
      name: string;
      category: string;
      price_final: number | null;
      price_per_serving: number | null;
      complete: boolean;
      available: boolean;
      image_url: string | null;
    }>,
    total: 0,
    page: 1,
    query: "",
    category: null as string | null,
    categories: [] as string[],
    loading: false,
    error: null as string | null,
    setQuery: vi.fn(),
    setCategory: vi.fn(),
    goToPage: vi.fn(),
    reload: vi.fn(),
  },
}));

vi.mock("../hooks/useProducts", () => ({
  useProducts: () => mocks.state,
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: "u1", role: "admin" } }),
}));

function renderPage() {
  return render(
    <Provider>
      <ProductsPage />
    </Provider>,
  );
}

beforeEach(() => {
  mocks.state.items = [];
  mocks.state.total = 0;
  mocks.state.query = "";
  mocks.state.category = null;
  mocks.state.categories = [];
  mocks.state.error = null;
  mocks.state.setQuery = mocks.setQuery;
  mocks.state.setCategory = mocks.setCategory;
  mocks.setQuery.mockClear();
  mocks.setCategory.mockClear();
});

afterEach(() => {
  cleanup();
});

describe("ProductsPage", () => {
  it("muestra 'Todas' presionada y una chip por categoría derivada", () => {
    mocks.state.categories = ["Tortas", "Cupcakes"];
    renderPage();

    const all = screen.getByRole("button", { name: "Todas" });
    expect(all).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Tortas" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByRole("button", { name: "Cupcakes" })).toBeInTheDocument();
  });

  it("al tocar una categoría la filtra (RF-P3-02)", async () => {
    mocks.state.categories = ["Tortas"];
    renderPage();

    await userEvent.click(screen.getByRole("button", { name: "Tortas" }));
    expect(mocks.setCategory).toHaveBeenCalledWith("Tortas");
  });

  it("al tocar la categoría activa la quita", async () => {
    mocks.state.categories = ["Tortas"];
    mocks.state.category = "Tortas";
    renderPage();

    await userEvent.click(screen.getByRole("button", { name: "Tortas" }));
    expect(mocks.setCategory).toHaveBeenCalledWith(null);
  });

  it("la búsqueda escribe en el hook (debounce vive en useProducts)", async () => {
    renderPage();

    await userEvent.type(
      screen.getByLabelText("Buscar productos por nombre"),
      "torta",
    );
    expect(mocks.setQuery).toHaveBeenCalled();
  });

  it("sin productos ni filtros muestra el estado vacío con CTA (RF-P3-06)", () => {
    renderPage();

    expect(screen.getByText("Todavía no hay productos")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Crear tu primer producto" }),
    ).toBeInTheDocument();
  });

  it("con filtros sin resultados no ofrece crear, sugiere cambiarlos", () => {
    mocks.state.query = "xyz";
    renderPage();

    expect(screen.getByText("Sin resultados para «xyz»")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Crear tu primer producto" }),
    ).not.toBeInTheDocument();
  });

  it("renderiza las cards con precio y badge de incompleto (RF-P3-05)", () => {
    mocks.state.total = 2;
    mocks.state.items = [
      {
        id: "1",
        name: "Torta de chocolate",
        category: "Tortas",
        price_final: 155000,
        price_per_serving: 19375,
        complete: true,
        available: true,
        image_url: null,
      },
      {
        id: "2",
        name: "Cheesecake",
        category: "Postres",
        price_final: null,
        price_per_serving: null,
        complete: false,
        available: false,
        image_url: null,
      },
    ];
    renderPage();

    expect(screen.getByText("Torta de chocolate")).toBeInTheDocument();
    expect(screen.getByText("ARS 1.550")).toBeInTheDocument();
    expect(screen.getByText("sin precio")).toBeInTheDocument();
  });

  it("muestra el badge de publicación en cada card (RF-P3-09)", () => {
    mocks.state.total = 2;
    mocks.state.items = [
      {
        id: "1",
        name: "Torta de chocolate",
        category: "Tortas",
        price_final: 155000,
        price_per_serving: 19375,
        complete: true,
        available: true,
        image_url: null,
      },
      {
        id: "2",
        name: "Cheesecake",
        category: "Postres",
        price_final: 90000,
        price_per_serving: null,
        complete: true,
        available: false,
        image_url: null,
      },
    ];
    renderPage();

    expect(screen.getByText("En tienda")).toBeInTheDocument();
    expect(screen.getByText("Oculto")).toBeInTheDocument();
  });
});
