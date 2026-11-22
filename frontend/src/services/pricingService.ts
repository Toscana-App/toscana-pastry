import { downloadEndpoint } from "@/lib/download";
import { Audience } from "@/types/pricing";

export async function downloadPricelistCSV(audience: Audience): Promise<void> {
  await downloadEndpoint(
    `/products/pricelist/csv?audience=${audience}`,
    `pricelist_${audience}.csv`,
  );
}

export async function downloadPricelistPDF(audience: Audience): Promise<void> {
  await downloadEndpoint(
    `/products/pricelist/pdf?audience=${audience}`,
    `pricelist_${audience}.pdf`,
  );
}
