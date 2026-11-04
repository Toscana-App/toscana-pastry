import { importsService } from "./service";
import type { ImportEntity } from "./types";

/**
 * Descarga la plantilla CSV de la entidad como archivo (T-CSV-8).
 *
 * Se usa desde la página (botón "Descargar plantilla") y desde el diálogo.
 * Lanza si el backend no responde; el caller decide cómo mostrar el error.
 */
export async function downloadTemplate(entity: ImportEntity): Promise<void> {
  const text = await importsService.template(entity);
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${entity}_plantilla.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
