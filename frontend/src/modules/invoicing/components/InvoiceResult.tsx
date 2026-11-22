"use client";

import { Alert, Button, HStack, Stack, Text } from "@chakra-ui/react";
import { formatCents, formatDateTime } from "@/lib/format";
import { comprobanteLabel, type InvoiceComprobante } from "../types";

interface InvoiceResultProps {
  comprobante: InvoiceComprobante;
  /** Monto total en centavos (presente tras la emisión; puede faltar al recargar). */
  impTotal: number | null;
  downloading: boolean;
  onDownload: () => void;
}

/**
 * Panel de resultado tras emitir (o recargar con) el comprobante. Muestra el
 * comprobante formateado, el CAE, el vencimiento del CAE y la descarga del PDF.
 */
export function InvoiceResult({
  comprobante,
  impTotal,
  downloading,
  onDownload,
}: InvoiceResultProps) {
  return (
    <Alert.Root status="success">
      <Alert.Indicator />
      <Alert.Content>
        <Alert.Title>Factura emitida</Alert.Title>
        <Stack gap={1} mt={1}>
          <Text>
            Comprobante{" "}
            <Text
              as="span"
              fontWeight="700"
              fontFamily="mono"
              fontVariantNumeric="tabular-nums"
            >
              {comprobanteLabel(comprobante)}
            </Text>
          </Text>
          <Text fontSize="sm" color="fg.muted">
            CAE: {comprobante.cae}
          </Text>
          <Text fontSize="sm" color="fg.muted">
            Vence el CAE: {formatDateTime(comprobante.cae_vto)}
          </Text>
          {impTotal != null ? (
            <Text fontSize="sm" color="fg.muted">
              Total: {formatCents(impTotal)}
            </Text>
          ) : null}
        </Stack>
        <HStack mt={3}>
          <Button
            size="sm"
            variant="outline"
            colorPalette="brand"
            loading={downloading}
            onClick={onDownload}
          >
            Descargar PDF
          </Button>
        </HStack>
      </Alert.Content>
    </Alert.Root>
  );
}
