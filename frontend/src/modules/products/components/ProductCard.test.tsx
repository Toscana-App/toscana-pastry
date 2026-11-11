import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { Provider } from "@/providers/ChakraProvider";
import { ProductCard } from "./ProductCard";
import type { ProductListItem } from "../types";

const BASE: ProductListItem = {
  id: "1",
  name: "Torta de chocolate",
  category: "Tortas",
  price_final: 155000,
  price_per_serving: 19375,
  complete: true,
  available: true,
  image_url: null,
};

function renderCard(product: ProductListItem) {
  return render(
    <Provider>
      <ProductCard product={product} />
    </Provider>,
  );
}

afterEach(() => {
  cleanup();
});

describe("ProductCard", () => {
  it("muestra el badge 'En tienda' cuando el producto está publicado", () => {
    renderCard(BASE);

    expect(screen.getByText("En tienda")).toBeInTheDocument();
    expect(screen.queryByText("Oculto")).not.toBeInTheDocument();
    expect(screen.getByText(/\$\s1\.550,00/)).toBeInTheDocument();
  });

  it("muestra 'Oculto' cuando no está publicado", () => {
    renderCard({ ...BASE, available: false });

    expect(screen.getByText("Oculto")).toBeInTheDocument();
    expect(screen.queryByText("En tienda")).not.toBeInTheDocument();
  });

  it("prioriza el badge 'sin precio' en productos incompletos", () => {
    renderCard({
      ...BASE,
      price_final: null,
      price_per_serving: null,
      complete: false,
    });

    expect(screen.getByText("sin precio")).toBeInTheDocument();
    expect(screen.getByText("En tienda")).toBeInTheDocument();
  });
});
