import { importsService } from "./service";
import type { ImportEntity } from "./types";

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
