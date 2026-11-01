import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Provider } from "@/providers/ChakraProvider";
import { StockBadge } from "./StockBadge";

/**
 * Tests del badge de stock (RF-P2-04): el texto y el color dependen del status
 * que computa el servidor.
 */
function renderBadge(status: "OK" | "LOW" | "EMPTY", stockQty: string, unit = "kg") {
  return render(
    <Provider>
      <StockBadge status={status} stockQty={stockQty} unit={unit} />
    </Provider>,
  );
}

describe("StockBadge", () => {
  it("OK muestra la cantidad disponible", () => {
    renderBadge("OK", "12", "kg");
    expect(screen.getByText("12 kg disponibles")).toBeInTheDocument();
  });

  it("LOW muestra los restantes", () => {
    renderBadge("LOW", "2", "kg");
    expect(screen.getByText("2 kg restantes")).toBeInTheDocument();
  });

  it("EMPTY dice Agotado sin mostrar cantidad", () => {
    renderBadge("EMPTY", "0", "kg");
    expect(screen.getByText("Agotado")).toBeInTheDocument();
  });

  it("formatea decimales con coma (es-AR)", () => {
    renderBadge("LOW", "1.5", "L");
    expect(screen.getByText("1,5 L restantes")).toBeInTheDocument();
  });
});
