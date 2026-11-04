import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import { ImportDialogV2 } from "./ImportDialogV2";
import { importsService } from "./service";

vi.mock("./service", () => ({
  importsService: {
    template: vi.fn(),
    upload: vi.fn(),
    rows: vi.fn(),
    confirm: vi.fn(),
    discard: vi.fn(),
  },
}));

vi.mock("@/lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

const ING_HEADER = "nombre;unidad;precio_por_unidad;cantidad_inicial;stock_minimo";

function dropCsv(container: HTMLElement, csvText: string, name = "archivo.csv") {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement | null;
  if (!input) throw new Error("input de archivo no encontrado");
  const file = new File([csvText], name, { type: "text/csv" });
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  fireEvent.change(input);
}

function openDialog() {
  const onOpenChange = vi.fn();
  const onImported = vi.fn();
  const utils = render(
    <ImportDialogV2
      entity="ingredients"
      open
      onOpenChange={onOpenChange}
      onImported={onImported}
    />,
  );
  return { ...utils, onImported };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("ImportDialogV2", () => {
  it("muestra el botón de subir y el de descargar plantilla", () => {
    vi.mocked(importsService.template).mockResolvedValue(ING_HEADER + "\n");
    openDialog();
    expect(
      screen.getByRole("button", { name: /Subir archivo/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Descargar plantilla/i }),
    ).toBeInTheDocument();
  });

  it("descargar plantilla llama al service y arma la descarga", async () => {
    vi.mocked(importsService.template).mockResolvedValue(ING_HEADER + "\n");
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:fake");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    openDialog();
    fireEvent.click(screen.getByRole("button", { name: /Descargar plantilla/i }));

    await waitFor(() =>
      expect(importsService.template).toHaveBeenCalledWith("ingredients"),
    );
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:fake");
  });

  it("rechaza columnas ajenas a la plantilla y NO sube (RF-CSV-13)", async () => {
    vi.mocked(importsService.template).mockResolvedValue(ING_HEADER + "\n");
    vi.mocked(importsService.upload).mockResolvedValue({
      import_id: "x",
      total_rows: 0,
      valid_rows: 0,
      invalid_rows: 0,
    });

    const { container } = openDialog();
    const bad = "nombre;unidad;precio_por_unidad;columna_extra\n1;kg;1;2";
    dropCsv(container, bad);

    await waitFor(() =>
      expect(screen.getByText(/Las columnas no coinciden/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/columna_extra/)).toBeInTheDocument();
    expect(importsService.upload).not.toHaveBeenCalled();
  });

  it("sube un archivo válido y muestra la preview con Confirmar habilitado", async () => {
    vi.mocked(importsService.template).mockResolvedValue(ING_HEADER + "\n");
    vi.mocked(importsService.upload).mockResolvedValue({
      import_id: "imp1",
      total_rows: 1,
      valid_rows: 1,
      invalid_rows: 0,
    });
    vi.mocked(importsService.rows).mockResolvedValue({
      import_id: "imp1",
      total_rows: 1,
      valid_rows: 1,
      invalid_rows: 0,
      rows: [
        {
          row_number: 1,
          values: {
            nombre: "Harina",
            unidad: "kg",
            precio_por_unidad: "1000",
            cantidad_inicial: "5",
            stock_minimo: "1",
          },
          status: "valid",
          errors: [],
        },
      ],
      page: 1,
      page_size: 100,
    });

    const { container } = openDialog();
    dropCsv(container, ING_HEADER + "\nHarina;kg;1000;5;1");

    await waitFor(() => expect(importsService.upload).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("Harina")).toBeInTheDocument());

    const confirmBtn = screen.getByRole("button", { name: /Confirmar/i });
    expect(confirmBtn).toBeEnabled();
  });

  it("deshabilita Confirmar cuando el backend reporta filas inválidas", async () => {
    vi.mocked(importsService.template).mockResolvedValue(ING_HEADER + "\n");
    vi.mocked(importsService.upload).mockResolvedValue({
      import_id: "imp1",
      total_rows: 1,
      valid_rows: 0,
      invalid_rows: 1,
    });
    vi.mocked(importsService.rows).mockResolvedValue({
      import_id: "imp1",
      total_rows: 1,
      valid_rows: 0,
      invalid_rows: 1,
      rows: [
        {
          row_number: 1,
          values: { nombre: "", unidad: "kg", precio_por_unidad: "abc" },
          status: "invalid",
          errors: ["El nombre es obligatorio."],
        },
      ],
      page: 1,
      page_size: 100,
    });

    const { container } = openDialog();
    dropCsv(container, ING_HEADER + "\n;kg;abc");

    await waitFor(() => expect(importsService.upload).toHaveBeenCalled());
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Confirmar/i }),
      ).toBeDisabled(),
    );
  });

  it("confirmar llama al service, refresca la lista y muestra el resultado", async () => {
    vi.mocked(importsService.template).mockResolvedValue(ING_HEADER + "\n");
    vi.mocked(importsService.upload).mockResolvedValue({
      import_id: "imp1",
      total_rows: 1,
      valid_rows: 1,
      invalid_rows: 0,
    });
    vi.mocked(importsService.rows).mockResolvedValue({
      import_id: "imp1",
      total_rows: 1,
      valid_rows: 1,
      invalid_rows: 0,
      rows: [
        {
          row_number: 1,
          values: {
            nombre: "Harina",
            unidad: "kg",
            precio_por_unidad: "1000",
            cantidad_inicial: "5",
            stock_minimo: "1",
          },
          status: "valid",
          errors: [],
        },
      ],
      page: 1,
      page_size: 100,
    });
    vi.mocked(importsService.confirm).mockResolvedValue({
      created: 1,
      skipped: 0,
      errors: [],
    });

    const { container, onImported } = openDialog();
    dropCsv(container, ING_HEADER + "\nHarina;kg;1000;5;1");

    const confirmBtn = await screen.findByRole("button", { name: /Confirmar/i });
    await waitFor(() => expect(confirmBtn).toBeEnabled());
    fireEvent.click(confirmBtn);

    await waitFor(() =>
      expect(importsService.confirm).toHaveBeenCalledWith("imp1"),
    );
    expect(onImported).toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByText(/1 creados/)).toBeInTheDocument(),
    );
  });
});
