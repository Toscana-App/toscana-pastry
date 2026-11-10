"use client";

import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import Papa from "papaparse";
import {
  Alert,
  Box,
  Button,
  Dialog,
  Flex,
  Table,
  Text,
} from "@chakra-ui/react";
import { ShimmerDot } from "@/components/ui/skeleton";

import { trackEvent } from "@/lib/analytics";
import { importsService } from "./service";
import { downloadTemplate } from "./download";
import {
  ENTITY_COLUMNS,
  compareColumns,
  type ColumnDiff,
} from "./validation";
import { ENTITY_LABELS, type ConfirmResponse, type ImportEntity, type ImportRowOut } from "./types";

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const PREVIEW_PAGE_SIZE = 100;

interface ImportDialogV2Props {
  entity: ImportEntity;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => void;
}

interface PreviewState {
  importId: string;
  rows: ImportRowOut[];
  validRows: number;
  invalidRows: number;
  totalRows: number;
}

function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

export function ImportDialogV2(props: ImportDialogV2Props) {
  if (!props.open) return null;
  return <ImportDialogContent {...props} />;
}

function ImportDialogContent({
  entity,
  open,
  onOpenChange,
  onImported,
}: ImportDialogV2Props) {
  const spec = ENTITY_COLUMNS[entity];
  const columnKeys = spec.map((c) => c.key);

  const [expectedHeaders, setExpectedHeaders] = useState<string[]>(columnKeys);
  const [columnError, setColumnError] = useState<ColumnDiff | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmResult, setConfirmResult] = useState<ConfirmResponse | null>(null);

  const label = ENTITY_LABELS[entity];

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const text = await importsService.template(entity);
        if (cancelled) return;
        const parsed = Papa.parse(text, { header: false, skipEmptyLines: true });
        const first = parsed.data[0];
        if (Array.isArray(first) && first.length > 0) {
          const headers = (first as string[])
            .map((h) => h.replace(/^\uFEFF/, "").trim())
            .filter(Boolean);
          if (headers.length > 0) setExpectedHeaders(headers);
        }
      } catch {
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [entity]);

  const onDrop = useCallback(
    async (accepted: File[]) => {
      const file = accepted[0];
      if (!file) return;
      setColumnError(null);
      setClientError(null);
      setConfirmResult(null);
      setPreview(null);

      if (file.size > MAX_FILE_BYTES) {
        setClientError("El archivo supera los 5 MB.");
        return;
      }

      try {
        const text = await readFileText(file);
        const parsed = Papa.parse<Record<string, string>>(text, {
          header: true,
          skipEmptyLines: true,
        });
        const headers = (parsed.meta.fields ?? []).map((h) => h.trim()).filter(Boolean);
        if (headers.length === 0) {
          setClientError("El archivo no tiene un encabezado de columnas.");
          return;
        }

        const diff = compareColumns(expectedHeaders, headers);
        if (!diff.ok) {
          setColumnError(diff);
          return;
        }

        setUploading(true);
        const res = await importsService.upload(file, entity);
        trackEvent("csv_import_started", { entity, rows: res.total_rows });
        const rowsRes = await importsService.rows(
          res.import_id,
          1,
          PREVIEW_PAGE_SIZE,
        );
        setPreview({
          importId: res.import_id,
          rows: rowsRes.rows,
          validRows: rowsRes.valid_rows,
          invalidRows: rowsRes.invalid_rows,
          totalRows: rowsRes.total_rows,
        });
      } catch (e) {
        setClientError(e instanceof Error ? e.message : "No se pudo procesar el archivo");
      } finally {
        setUploading(false);
      }
    },
    [expectedHeaders, entity],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: false,
    noClick: false,
  });

  const canConfirm =
    preview !== null &&
    confirmResult === null &&
    preview.invalidRows === 0 &&
    !confirming &&
    !uploading;

  function close() {
    onOpenChange(false);
  }

  async function doDownloadTemplate() {
    try {
      await downloadTemplate(entity);
      trackEvent("csv_template_downloaded", { entity });
    } catch (e) {
      setClientError(e instanceof Error ? e.message : "No se pudo descargar la plantilla");
    }
  }

  async function doConfirm() {
    if (!preview) return;
    setConfirming(true);
    setClientError(null);
    try {
      const res = await importsService.confirm(preview.importId);
      setConfirmResult(res);
      trackEvent("csv_import_confirmed", {
        entity,
        created: res.created,
        skipped: res.skipped,
      });
      if (res.created > 0 || res.skipped > 0) onImported();
    } catch (e) {
      setClientError(e instanceof Error ? e.message : "No se pudo confirmar la importación");
    } finally {
      setConfirming(false);
    }
  }

  async function doDiscard() {
    if (!preview) return;
    setClientError(null);
    try {
      await importsService.discard(preview.importId);
      onOpenChange(false);
    } catch (e) {
      setClientError(e instanceof Error ? e.message : "No se pudo descartar la importación");
    }
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(e) => (e.open ? onOpenChange(true) : close())}
      size="xl"
    >
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content overscrollBehavior="contain">
          <Dialog.Header>
            <Dialog.Title>Importar {label}</Dialog.Title>
            <Dialog.Description>
              Descargá la plantilla, completala y subila. Las columnas deben
              coincidir exactamente con la plantilla.
            </Dialog.Description>
          </Dialog.Header>
          <Dialog.Body>
            <Flex direction="column" gap={4}>
              {}
              {!preview && (
                <Box
                  {...getRootProps()}
                  borderWidth="2px"
                  borderStyle="dashed"
                  borderColor={isDragActive ? "brand.400" : "gray.300"}
                  rounded="md"
                  p={8}
                  textAlign="center"
                  bg={isDragActive ? "brand.50" : "gray.50"}
                  cursor="pointer"
                  _hover={{ borderColor: "brand.400" }}
                >
                  <input {...getInputProps()} />
                  <Text fontWeight="600">{isDragActive ? "Soltá el archivo acá" : "Arrastrá el CSV acá o"}</Text>
                  <Flex justify="center" mt={3}>
                    <Button colorPalette="brand" size="sm" type="button">
                      Subir archivo
                    </Button>
                  </Flex>
                </Box>
              )}

              <Flex gap={3}>
                <Button variant="outline" onClick={doDownloadTemplate} size="sm">
                  Descargar plantilla
                </Button>
              </Flex>

              {}
              {columnError && (
                <Alert.Root status="error">
                  <Alert.Content>
                    <Alert.Title>Las columnas no coinciden con la plantilla</Alert.Title>
                    <Alert.Description>
                      {columnError.missing.length > 0 && (
                        <Text>
                          Faltan: {columnError.missing.join(", ")}.
                        </Text>
                      )}
                      {columnError.extra.length > 0 && (
                        <Text>
                          Ajenas a la plantilla: {columnError.extra.join(", ")}.
                        </Text>
                      )}
                    </Alert.Description>
                  </Alert.Content>
                </Alert.Root>
              )}

              {}
              {clientError && !columnError && (
                <Alert.Root status="error">
                  <Alert.Content>
                    <Alert.Description>{clientError}</Alert.Description>
                  </Alert.Content>
                </Alert.Root>
              )}

              {uploading && (
                <Flex align="center" gap={3} aria-live="polite">
                  <ShimmerDot />
                  <Text color="fg.muted">Procesando…</Text>
                </Flex>
              )}

              {}
              {preview && (
                <Box>
                  <Text fontWeight="600" mb={2} fontVariantNumeric="tabular-nums">
                    {preview.totalRows} filas ·{" "}
                    <Text as="span" color="green.600">
                      {preview.validRows} válidas
                    </Text>{" "}
                    ·{" "}
                    <Text as="span" color={preview.invalidRows > 0 ? "red.600" : "fg.muted"}>
                      {preview.invalidRows} inválidas
                    </Text>
                  </Text>
                  <Box overflowX="auto" maxH="40vh" overflowY="auto" borderWidth="1px" rounded="md">
                    <Table.Root size="sm">
                      <Table.Header>
                        <Table.Row>
                          <Table.ColumnHeader>Fila</Table.ColumnHeader>
                          {columnKeys.map((key) => (
                            <Table.ColumnHeader key={key}>{key}</Table.ColumnHeader>
                          ))}
                          <Table.ColumnHeader>Estado</Table.ColumnHeader>
                        </Table.Row>
                      </Table.Header>
                      <Table.Body>
                        {preview.rows.map((row) => (
                          <Table.Row
                            key={row.row_number}
                            bg={row.status === "invalid" ? "red.50" : undefined}
                          >
                            <Table.Cell fontVariantNumeric="tabular-nums">{row.row_number}</Table.Cell>
                            {columnKeys.map((key) => (
                              <Table.Cell key={key} overflowWrap="anywhere">{row.values[key] ?? ""}</Table.Cell>
                            ))}
                            <Table.Cell>
                              {row.status === "valid" ? (
                                <Text color="green.600">OK</Text>
                              ) : (
                                <Text color="red.600">
                                  {row.errors.join(" ")}
                                </Text>
                              )}
                            </Table.Cell>
                          </Table.Row>
                        ))}
                      </Table.Body>
                    </Table.Root>
                  </Box>
                </Box>
              )}

              {}
              {confirmResult && (
                <Alert.Root status={confirmResult.errors.length > 0 ? "warning" : "success"} aria-live="polite">
                  <Alert.Content>
                    <Alert.Description>
                      {confirmResult.message ??
                        `Importado: ${confirmResult.created} creados, ${confirmResult.skipped} omitidos (duplicados).`}
                      {confirmResult.errors.length > 0 && (
                        <Text color="red.600">
                          {confirmResult.errors.join(" ")}
                        </Text>
                      )}
                    </Alert.Description>
                  </Alert.Content>
                </Alert.Root>
              )}
            </Flex>
          </Dialog.Body>
          <Dialog.Footer>
            <Button variant="ghost" onClick={close}>
              Cerrar
            </Button>
            {preview && !confirmResult && (
              <>
                <Button variant="outline" onClick={doDiscard} disabled={confirming}>
                  Descartar
                </Button>
                <Button
                  colorPalette="brand"
                  onClick={doConfirm}
                  loading={confirming}
                  disabled={!canConfirm}
                >
                  Confirmar
                </Button>
              </>
            )}
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
