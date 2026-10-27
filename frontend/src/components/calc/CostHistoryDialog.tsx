"use client";

import { useEffect, useState } from "react";
import {
  Button,
  Dialog,
  Flex,
  Spinner,
  Table,
  Text,
} from "@chakra-ui/react";
import { calcMaterialsService } from "@/services/calcMaterialsService";
import { toaster } from "@/lib/toaster";
import type { CostHistoryListResponse, Material } from "@/types/calc";

// Diálogo de historial de costos unitarios de un material (RF-P2CC-04):
// GET /calc/materials/{id}/cost-history, más recientes primero (desc,
// como el endpoint). Montos tal cual el str del servidor (sin aritmética).
// Paginación prev/next si hay más de 50 registros.
const PAGE_SIZE = 50;

interface CostHistoryDialogProps {
  material: Material;
  onClose: () => void;
}

// changed_at → fecha legible en es-AR (p.ej. "10/03/2026, 15:30").
function formatChangedAt(iso: string): string {
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function CostHistoryDialog({
  material,
  onClose,
}: CostHistoryDialogProps) {
  const [data, setData] = useState<CostHistoryListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [page, setPage] = useState(1);
  // Contador para forzar reintento sin cambios de parámetros.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!cancelled) {
        setLoading(true);
        setLoadError(false);
      }
      try {
        const response =
          await calcMaterialsService.listCostHistory(material.id, {
            page,
            page_size: PAGE_SIZE,
          });
        if (!cancelled) setData(response);
      } catch (error) {
        if (cancelled) return;
        setLoadError(true);
        toaster.create({
          title: "Error al cargar el historial",
          description:
            error instanceof Error
              ? error.message
              : "No se pudo cargar el historial.",
          type: "error",
        });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [material.id, page, reloadKey]);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Dialog.Root
      open
      onOpenChange={(details) => {
        if (!details.open) onClose();
      }}
    >
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content>
          <Dialog.Header>
            <Dialog.Title>
              Historial de costos · {material.name}
            </Dialog.Title>
          </Dialog.Header>
          <Dialog.Body>
            {loading ? (
              <Flex align="center" justify="center" py={10}>
                <Spinner size="lg" />
              </Flex>
            ) : loadError ? (
              <Flex align="center" direction="column" gap={3} py={6}>
                <Text>No se pudo cargar el historial.</Text>
                <Button
                  size="sm"
                  rounded="full"
                  onClick={() => setReloadKey((key) => key + 1)}
                >
                  Reintentar
                </Button>
              </Flex>
            ) : items.length === 0 ? (
              <Text color="fg.muted" py={4}>
                Sin cambios de costo registrados.
              </Text>
            ) : (
              <Flex direction="column" gap={4}>
                <Table.ScrollArea borderWidth="1px" rounded="md">
                  <Table.Root size="sm">
                    <Table.Header>
                      <Table.Row>
                        <Table.ColumnHeader>Anterior</Table.ColumnHeader>
                        <Table.ColumnHeader>Nuevo</Table.ColumnHeader>
                        <Table.ColumnHeader>Fecha</Table.ColumnHeader>
                      </Table.Row>
                    </Table.Header>
                    <Table.Body>
                      {items.map((entry, index) => (
                        <Table.Row key={`${entry.changed_at}-${index}`}>
                          <Table.Cell>
                            {entry.previous_unit_cost ?? "—"}
                          </Table.Cell>
                          <Table.Cell>
                            {entry.new_unit_cost ?? "—"}
                          </Table.Cell>
                          <Table.Cell>
                            {formatChangedAt(entry.changed_at)}
                          </Table.Cell>
                        </Table.Row>
                      ))}
                    </Table.Body>
                  </Table.Root>
                </Table.ScrollArea>
                {total > PAGE_SIZE && (
                  <Flex align="center" gap={3}>
                    <Button
                      size="sm"
                      variant="outline"
                      rounded="full"
                      disabled={page <= 1}
                      onClick={() => setPage((current) => current - 1)}
                    >
                      Anterior
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      rounded="full"
                      disabled={page * PAGE_SIZE >= total}
                      onClick={() => setPage((current) => current + 1)}
                    >
                      Siguiente
                    </Button>
                  </Flex>
                )}
              </Flex>
            )}
          </Dialog.Body>
          <Dialog.Footer>
            <Dialog.ActionTrigger asChild>
              <Button variant="outline" rounded="full">
                Cerrar
              </Button>
            </Dialog.ActionTrigger>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
