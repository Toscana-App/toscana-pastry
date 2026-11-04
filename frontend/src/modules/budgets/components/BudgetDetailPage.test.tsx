import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Provider } from "@/providers/ChakraProvider";
import { BudgetDetailPage } from "./BudgetDetailPage";

/**
 * Detalle de presupuesto (Fase 8, P9/P10): preview PDF (GET binario →
 * objectURL → iframe), "Enviar por WhatsApp" (wa.me + límite 30/día) y
 * link temporal firmado de 72 h (copiable + vencimiento + regeneración).
 */
const mocks = vi.hoisted(() => ({
  getDetail: vi.fn(),
  send: vi.fn(),
  convertToOrder: vi.fn(),
  remove: vi.fn(),
  recalculate: vi.fn(),
  pdfUrl: vi.fn(),
  sharePdf: vi.fn(),
  whatsappLink: vi.fn(),
  push: vi.fn(),
}));

vi.mock("../service", () => ({
  budgetsService: {
    getDetail: mocks.getDetail,
    send: mocks.send,
    convertToOrder: mocks.convertToOrder,
    remove: mocks.remove,
    recalculate: mocks.recalculate,
    pdfUrl: mocks.pdfUrl,
    sharePdf: mocks.sharePdf,
    whatsappLink: mocks.whatsappLink,
  },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: "u1", role: "admin", email: "admin@toscana.local" } }),
}));

/** Detalle mínimo válido (mismo espejo que service.test.ts). */
function detailBody(over: Record<string, unknown> = {}) {
  return {
    id: "b1",
    seq: "#00001",
    customer: { id: "c1", name: "María", phone: "11 2233 4455" },
    status: "borrador",
    calculation_mode: "cost_plus",
    margin_pct: 30,
    version: 1,
    items: [
      {
        product_id: "p1",
        product_name: "Torta de Limón",
        qty: 1,
        unit_cost: 10000,
        unit_selling: 15000,
        line_cost: 10000,
        line_selling: 15000,
        price_overridden: false,
      },
    ],
    summary: { subtotal: 15000, total_costos: 10000, ganancia: 5000, total_venta: 18150 },
    delivery_address: null,
    created_at: "2026-11-01T12:00:00Z",
    updated_at: "2026-11-01T12:00:00Z",
    sent_at: null,
    ...over,
  };
}

const writeText = vi.hoisted(() => vi.fn());

function renderDetail() {
  return render(
    <Provider>
      <BudgetDetailPage budgetId="b1" />
    </Provider>,
  );
}

async function loadDetail() {
  // Espera a que el detalle termine de cargarse (skeleton → contenido).
  // El h2 divide el texto en nodos ("Presupuesto #" + seq con #).
  await screen.findByRole("heading", { name: /Presupuesto/ });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getDetail.mockResolvedValue(detailBody());
  writeText.mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
});

afterEach(() => {
  cleanup();
});

describe("BudgetDetailPage — PDF (Fase 8, P9)", () => {
  it("Ver PDF: pide el binario y abre el preview con el objectURL", async () => {
    mocks.pdfUrl.mockResolvedValue("blob:obj-1");
    renderDetail();
    await loadDetail();

    await userEvent.click(screen.getByRole("button", { name: "Ver PDF" }));

    expect(mocks.pdfUrl).toHaveBeenCalledWith("b1");
    const frame = await screen.findByTitle("PDF presupuesto #00001");
    expect(frame).toHaveAttribute("src", "blob:obj-1");
  });

  it("Ver PDF: el error de generación se muestra", async () => {
    mocks.pdfUrl.mockRejectedValue(new Error("No se pudo generar el PDF"));
    renderDetail();
    await loadDetail();

    await userEvent.click(screen.getByRole("button", { name: "Ver PDF" }));

    expect(await screen.findByText("No se pudo generar el PDF")).toBeInTheDocument();
  });
});

describe("BudgetDetailPage — WhatsApp (Fase 8, P10)", () => {
  it("Enviar por WhatsApp: abre wa.me y muestra el registro", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    mocks.whatsappLink.mockResolvedValue({
      url: "https://wa.me/5491155550100?text=hola",
      sent_at: "2026-11-04T12:00:00Z",
    });
    renderDetail();
    await loadDetail();

    await userEvent.click(screen.getByRole("button", { name: "Enviar por WhatsApp" }));

    expect(openSpy).toHaveBeenCalledWith(
      "https://wa.me/5491155550100?text=hola",
      "_blank",
      "noopener",
    );
    expect(await screen.findByText(/WhatsApp abierto/)).toBeInTheDocument();
    expect(screen.getByText(/enviado 2026-11-04T12:00:00Z/)).toBeInTheDocument();
  });

  it("Enviar por WhatsApp: 429 muestra el mensaje de límite (RNF-P10-06)", async () => {
    mocks.whatsappLink.mockRejectedValue(
      new Error("Límite diario de links de WhatsApp alcanzado (30/día)"),
    );
    renderDetail();
    await loadDetail();

    await userEvent.click(screen.getByRole("button", { name: "Enviar por WhatsApp" }));

    expect(await screen.findByText(/Límite diario de links de WhatsApp/)).toBeInTheDocument();
  });
});

describe("BudgetDetailPage — link temporal (Fase 8, P9)", () => {
  it("genera el link, muestra el vencimiento y lo copia al portapapeles", async () => {
    const future = new Date(Date.now() + 72 * 3600 * 1000).toISOString();
    mocks.sharePdf.mockResolvedValue({
      url: "https://public.example/api/v1/pdf/tok",
      expires_at: future,
    });
    renderDetail();
    await loadDetail();

    await userEvent.click(screen.getByRole("button", { name: "Link temporal (72 h)" }));

    expect(await screen.findByText("https://public.example/api/v1/pdf/tok")).toBeInTheDocument();
    expect(screen.getByText(/Vence/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Copiar" }));
    expect(writeText).toHaveBeenCalledWith("https://public.example/api/v1/pdf/tok");
    expect(await screen.findByText("Copiado")).toBeInTheDocument();
  });

  it("link vencido: ofrece regenerar y el nuevo reemplaza al viejo", async () => {
    const future = new Date(Date.now() + 72 * 3600 * 1000).toISOString();
    mocks.sharePdf
      .mockResolvedValueOnce({
        url: "https://public.example/api/v1/pdf/old",
        expires_at: "2020-01-01T00:00:00Z",
      })
      .mockResolvedValueOnce({
        url: "https://public.example/api/v1/pdf/new",
        expires_at: future,
      });
    renderDetail();
    await loadDetail();

    await userEvent.click(screen.getByRole("button", { name: "Link temporal (72 h)" }));
    expect(await screen.findByText(/El link venció/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Generar nuevo" }));
    expect(mocks.sharePdf).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("https://public.example/api/v1/pdf/new")).toBeInTheDocument();
  });
});
