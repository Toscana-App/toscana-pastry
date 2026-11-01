"use client";

import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  Flex,
  Text,
  Textarea,
} from "@chakra-ui/react";
import { ingredientsService } from "../service";
import type { ImportErrorItem } from "../types";

const MAX_LINES = 500;

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Se llama cuando la importación creó registros (para re-fetchar la lista). */
  onImported: () => void;
}

interface ImportResult {
  created: number;
  errors: ImportErrorItem[];
}

/**
 * Importación de ingredientes (Fase 4, WU4, RF-P2-06).
 *
 * Formato por línea: `name;unit;price` (p. ej. `Harina;kg;1200`). El parsing
 * de formato es responsabilidad del backend (422 con el detalle por línea);
 * acá solo se filtran líneas vacías y se valida el límite de 500.
 * El resultado muestra los creados y los errores línea por línea.
 */
export function ImportDialog({ open, onOpenChange, onImported }: ImportDialogProps) {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  function close() {
    setText("");
    setResult(null);
    setClientError(null);
    onOpenChange(false);
  }

  async function submit() {
    const lines = text
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0);

    setClientError(null);
    if (lines.length === 0) {
      setClientError("Pegá al menos una línea (formato: name;unit;price).");
      return;
    }
    if (lines.length > MAX_LINES) {
      setClientError(`Máximo ${MAX_LINES} líneas por importación.`);
      return;
    }

    setSubmitting(true);
    try {
      const res = await ingredientsService.importLines(lines);
      setResult({ created: res.created, errors: res.errors });
      if (res.created > 0) onImported();
    } catch (e) {
      setClientError(e instanceof Error ? e.message : "No se pudo importar");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(e) => (e.open ? onOpenChange(true) : close())} size="lg">
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content>
          <Dialog.Header>
            <Dialog.Title>Import ingredients</Dialog.Title>
            <Dialog.Description>
              One line per ingredient: <Text as="span" fontWeight="600">name;unit;price</Text> (p.
              ej. <Text as="span" fontWeight="600">Harina;kg;1200</Text>).
            </Dialog.Description>
          </Dialog.Header>
          <Dialog.Body>
            <Flex direction="column" gap={4}>
              <Textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={"Harina;kg;1200\nLeche;L;150\nHuevo;unidad;45"}
                rows={8}
                disabled={submitting}
                aria-label="Líneas a importar"
              />
              {clientError ? (
                <Alert.Root status="error">
                  <Alert.Content>
                    <Alert.Description>{clientError}</Alert.Description>
                  </Alert.Content>
                </Alert.Root>
              ) : null}
              {result ? (
                <Flex direction="column" gap={2}>
                  <Text fontWeight="600">{result.created} created</Text>
                  {result.errors.length > 0 ? (
                    <Box>
                      {result.errors.map((err) => (
                        <Text key={err.line} fontSize="sm" color="red.600">
                          Line {err.line}: {err.message}
                        </Text>
                      ))}
                    </Box>
                  ) : null}
                </Flex>
              ) : null}
            </Flex>
          </Dialog.Body>
          <Dialog.Footer>
            <Button variant="ghost" onClick={close} disabled={submitting}>
              Close
            </Button>
            <Button
              colorPalette="brand"
              onClick={submit}
              loading={submitting}
              disabled={result !== null}
            >
              {result ? "Done" : "Import"}
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
