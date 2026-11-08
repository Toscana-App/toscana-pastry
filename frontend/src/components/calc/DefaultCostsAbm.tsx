"use client";

import { useEffect, useState } from "react";
import { createListCollection } from "@ark-ui/react";
import {
  Button,
  Dialog,
  EmptyState,
  Flex,
  Heading,
  Input,
  Select,
  Table,
  Text,
} from "@chakra-ui/react";
import { SkeletonTable } from "@/components/ui/skeleton";

import { calcSettingsService } from "@/services/calcSettingsService";
import { toaster } from "@/lib/toaster";
import type {
  DefaultCost,
  DefaultCostCreatePayload,
  DefaultCostListResponse,
  DefaultCostStatus,
  DefaultCostType,
  DefaultCostUpdatePayload,
} from "@/types/calc";

// page_size fijo (decisión F1 en PREGUNTAS.md): escala admin, sin selector.
const PAGE_SIZE = 50;

// Allow-lists exactas (RF-P5CC-06) con labels en español.
const TYPE_COLLECTION = createListCollection({
  items: [
    { value: "labor", label: "Mano de obra" },
    { value: "extra_cost", label: "Costo extra" },
  ],
});
const STATUS_COLLECTION = createListCollection({
  items: [
    { value: "active", label: "Activo" },
    { value: "inactive", label: "Inactivo" },
  ],
});

const typeLabel = (type: string) =>
  type === "labor" ? "Mano de obra" : "Costo extra";
const statusLabel = (status: string) =>
  status === "active" ? "Activo" : "Inactivo";

// Montos/quantities viajan como str del backend; en pantalla se muestran
// con 2 decimales.
function formatAmount(value: string): string {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(2) : value;
}

function isNonNegativeAmount(value: string): boolean {
  if (value.trim() === "") return false;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0;
}

export default function DefaultCostsAbm() {
  const [data, setData] = useState<DefaultCostListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  // Contador para forzar reintento sin cambios de parámetros.
  const [reloadKey, setReloadKey] = useState(0);

  // Búsqueda: input crudo + valor con debounce (~300 ms) que manda ?q.
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  // Creación (formulario card encima de la tabla).
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<DefaultCostType>("labor");
  const [newCost, setNewCost] = useState("");
  const [newQuantity, setNewQuantity] = useState("");
  const [newStatus, setNewStatus] = useState<DefaultCostStatus>("active");
  const [creating, setCreating] = useState(false);

  // Edición inline por fila.
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editType, setEditType] = useState<DefaultCostType>("labor");
  const [editCost, setEditCost] = useState("");
  const [editQuantity, setEditQuantity] = useState("");
  const [editStatus, setEditStatus] = useState<DefaultCostStatus>("active");
  const [savingEdit, setSavingEdit] = useState(false);

  // Eliminación con diálogo de confirmación.
  const [deleting, setDeleting] = useState<DefaultCost | null>(null);
  const [deletingBusy, setDeletingBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!cancelled) {
        setLoading(true);
        setLoadError(false);
      }
      try {
        const response = await calcSettingsService.listDefaultCosts({
          q: search || undefined,
          page,
          page_size: PAGE_SIZE,
        });
        if (!cancelled) setData(response);
      } catch (error) {
        if (cancelled) return;
        setLoadError(true);
        toaster.create({
          title: "Error al cargar",
          description:
            error instanceof Error
              ? error.message
              : "No se pudo cargar la lista.",
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
  }, [search, page, reloadKey]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      // Un cambio de búsqueda vuelve a la primera página.
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  async function handleCreate() {
    const name = newName.trim();
    if (!name || !isNonNegativeAmount(newCost) || !isNonNegativeAmount(newQuantity) || creating) {
      return;
    }
    setCreating(true);
    try {
      const payload: DefaultCostCreatePayload = {
        name,
        type: newType,
        default_unit_cost_or_rate: newCost,
        default_quantity_or_minutes: newQuantity,
        status: newStatus,
      };
      await calcSettingsService.createDefaultCost(payload);
      // Refetch de la página actual: respeta filtro, orden y PAGE_SIZE del server.
      setReloadKey((key) => key + 1);
      setNewName("");
      setNewType("labor");
      setNewCost("");
      setNewQuantity("");
      setNewStatus("active");
      toaster.create({ title: "Costo por defecto creado", type: "success" });
    } catch (error) {
      toaster.create({
        title: "Error al crear",
        description:
          error instanceof Error
            ? error.message
            : "No se pudo crear el costo por defecto.",
        type: "error",
      });
    } finally {
      setCreating(false);
    }
  }

  function startEditing(cost: DefaultCost) {
    setEditingId(cost.id);
    setEditName(cost.name);
    setEditType(cost.type);
    setEditCost(cost.default_unit_cost_or_rate);
    setEditQuantity(cost.default_quantity_or_minutes);
    setEditStatus(cost.status);
  }

  async function handleSaveEdit() {
    const original = data?.items.find((item) => item.id === editingId);
    if (
      !original ||
      !editName.trim() ||
      !isNonNegativeAmount(editCost) ||
      !isNonNegativeAmount(editQuantity)
    ) {
      return;
    }

    // PATCH con SOLO los campos tocados (el backend usa exclude_unset).
    // Montos/quantities se comparan numéricamente: el usuario manda el
    // número que escribió, no el str original.
    const payload: DefaultCostUpdatePayload = {};
    if (editName.trim() !== original.name) payload.name = editName.trim();
    if (editType !== original.type) payload.type = editType;
    if (Number(editCost) !== Number(original.default_unit_cost_or_rate)) {
      payload.default_unit_cost_or_rate = editCost;
    }
    if (Number(editQuantity) !== Number(original.default_quantity_or_minutes)) {
      payload.default_quantity_or_minutes = editQuantity;
    }
    if (editStatus !== original.status) payload.status = editStatus;
    if (Object.keys(payload).length === 0) {
      setEditingId(null);
      return;
    }

    setSavingEdit(true);
    try {
      const updated = await calcSettingsService.updateDefaultCost(
        original.id,
        payload
      );
      setData((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.map((item) =>
                item.id === updated.id ? updated : item
              ),
            }
          : prev
      );
      setEditingId(null);
      toaster.create({ title: "Costo por defecto actualizado", type: "success" });
    } catch (error) {
      toaster.create({
        title: "Error al actualizar",
        description:
          error instanceof Error
            ? error.message
            : "No se pudo actualizar el costo por defecto.",
        type: "error",
      });
    } finally {
      setSavingEdit(false);
    }
  }

  async function handleDelete() {
    if (!deleting) return;
    setDeletingBusy(true);
    try {
      await calcSettingsService.deleteDefaultCost(deleting.id);
      setReloadKey((key) => key + 1);
      setDeleting(null);
      toaster.create({ title: "Costo por defecto eliminado", type: "success" });
    } catch (error) {
      toaster.create({
        title: "Error al eliminar",
        description:
          error instanceof Error
            ? error.message
            : "No se pudo eliminar el costo por defecto.",
        type: "error",
      });
      setDeleting(null);
    } finally {
      setDeletingBusy(false);
    }
  }

  if (loadError) {
    return (
      <Flex align="center" direction="column" gap={4} py={16}>
        <Text color="red.fg">No se pudo cargar la lista.</Text>
        <Button variant="outline"
          rounded="full"
          onClick={() => setReloadKey((key) => key + 1)}
        >
          Reintentar
        </Button>
      </Flex>
    );
  }

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const nextDisabled = total === 0 || page * PAGE_SIZE >= total;

  const canCreate =
    !creating &&
    newName.trim().length > 0 &&
    isNonNegativeAmount(newCost) &&
    isNonNegativeAmount(newQuantity);

  return (
    <Flex direction="column" gap={4}>
      <Heading size="md">Costos por defecto</Heading>

      {/* Creación: card encima de la tabla */}
      <Flex
        direction="column"
        gap={3}
        p={4}
        borderWidth="1px"
        borderColor="hairline-light"
        rounded="lg"
      >
        <Text color="fg.muted" fontWeight="medium">
          Nuevo costo por defecto
        </Text>
        <Flex
          direction={{ base: "column", lg: "row" }}
          gap={3}
          wrap="wrap"
          align="center"
        >
          <Input
            aria-label="Nombre"
            placeholder="Nombre"
            maxLength={120}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <Select.Root
            collection={TYPE_COLLECTION}
            value={[newType]}
            onValueChange={(details) => {
              const next = details.value[0];
              if (next) setNewType(next as DefaultCostType);
            }}
          >
            <Select.Trigger aria-label="Tipo" minW="10rem">
              <Select.ValueText placeholder="Tipo" />
            </Select.Trigger>
            <Select.Positioner>
              <Select.Content>
                <Select.Item item={{ value: "labor", label: "Mano de obra" }}>
                  Mano de obra
                </Select.Item>
                <Select.Item item={{ value: "extra_cost", label: "Costo extra" }}>
                  Costo extra
                </Select.Item>
              </Select.Content>
            </Select.Positioner>
          </Select.Root>
          <Input
            aria-label="Costo unitario o tarifa"
            type="number"
            step="0.01"
            min={0}
            placeholder="Costo unitario o tarifa"
            value={newCost}
            onChange={(e) => setNewCost(e.target.value)}
          />
          <Input
            aria-label="Cantidad o minutos"
            type="number"
            step="1"
            min={0}
            placeholder="Cantidad o minutos"
            value={newQuantity}
            onChange={(e) => setNewQuantity(e.target.value)}
          />
          <Select.Root
            collection={STATUS_COLLECTION}
            value={[newStatus]}
            onValueChange={(details) => {
              const next = details.value[0];
              if (next) setNewStatus(next as DefaultCostStatus);
            }}
          >
            <Select.Trigger aria-label="Estado" minW="10rem">
              <Select.ValueText placeholder="Estado" />
            </Select.Trigger>
            <Select.Positioner>
              <Select.Content>
                <Select.Item item={{ value: "active", label: "Activo" }}>
                  Activo
                </Select.Item>
                <Select.Item item={{ value: "inactive", label: "Inactivo" }}>
                  Inactivo
                </Select.Item>
              </Select.Content>
            </Select.Positioner>
          </Select.Root>
          <Button colorPalette="brand"
            rounded="full"
            loading={creating}
            disabled={!canCreate}
            onClick={handleCreate}
          >
            Crear
          </Button>
        </Flex>
      </Flex>

      {/* Búsqueda (?q) + total */}
      <Flex align="center" gap={3}>
        <Input
          aria-label="Buscar"
          placeholder="Buscar"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <Text color="fg.muted">Total: {total}</Text>
      </Flex>

      {loading ? (
        <SkeletonTable rows={6} cols={["22%", "18%", "18%", "16%", "12%", "14%"]} />
      ) : items.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Title>Sin costos por defecto</EmptyState.Title>
            <EmptyState.Description>
              No hay costos por defecto para mostrar.
            </EmptyState.Description>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <Table.ScrollArea borderWidth="1px" rounded="md">
          <Table.Root size="sm" stickyHeader>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Nombre</Table.ColumnHeader>
                <Table.ColumnHeader>Tipo</Table.ColumnHeader>
                <Table.ColumnHeader>Costo unitario o tarifa</Table.ColumnHeader>
                <Table.ColumnHeader>Cantidad o minutos</Table.ColumnHeader>
                <Table.ColumnHeader>Estado</Table.ColumnHeader>
                <Table.ColumnHeader>Acciones</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {items.map((cost) =>
                editingId === cost.id ? (
                  <Table.Row key={cost.id}>
                    <Table.Cell>
                      <Input
                        aria-label="Editar nombre"
                        maxLength={120}
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                      />
                    </Table.Cell>
                    <Table.Cell>
                      <Select.Root
                        collection={TYPE_COLLECTION}
                        value={[editType]}
                        onValueChange={(details) => {
                          const next = details.value[0];
                          if (next) setEditType(next as DefaultCostType);
                        }}
                      >
                        <Select.Trigger aria-label="Editar tipo" minW="9rem">
                          <Select.ValueText placeholder="Tipo" />
                        </Select.Trigger>
                        <Select.Positioner>
                          <Select.Content>
                            <Select.Item
                              item={{ value: "labor", label: "Mano de obra" }}
                            >
                              Mano de obra
                            </Select.Item>
                            <Select.Item
                              item={{ value: "extra_cost", label: "Costo extra" }}
                            >
                              Costo extra
                            </Select.Item>
                          </Select.Content>
                        </Select.Positioner>
                      </Select.Root>
                    </Table.Cell>
                    <Table.Cell>
                      <Input
                        aria-label="Editar costo"
                        type="number"
                        step="0.01"
                        min={0}
                        value={editCost}
                        onChange={(e) => setEditCost(e.target.value)}
                      />
                    </Table.Cell>
                    <Table.Cell>
                      <Input
                        aria-label="Editar cantidad"
                        type="number"
                        step="1"
                        min={0}
                        value={editQuantity}
                        onChange={(e) => setEditQuantity(e.target.value)}
                      />
                    </Table.Cell>
                    <Table.Cell>
                      <Select.Root
                        collection={STATUS_COLLECTION}
                        value={[editStatus]}
                        onValueChange={(details) => {
                          const next = details.value[0];
                          if (next) setEditStatus(next as DefaultCostStatus);
                        }}
                      >
                        <Select.Trigger aria-label="Editar estado" minW="8rem">
                          <Select.ValueText placeholder="Estado" />
                        </Select.Trigger>
                        <Select.Positioner>
                          <Select.Content>
                            <Select.Item
                              item={{ value: "active", label: "Activo" }}
                            >
                              Activo
                            </Select.Item>
                            <Select.Item
                              item={{ value: "inactive", label: "Inactivo" }}
                            >
                              Inactivo
                            </Select.Item>
                          </Select.Content>
                        </Select.Positioner>
                      </Select.Root>
                    </Table.Cell>
                    <Table.Cell>
                      <Flex gap={2}>
                        <Button colorPalette="brand"
                          size="sm"
                          rounded="full"
                          loading={savingEdit}
                          onClick={handleSaveEdit}
                        >
                          Guardar cambios
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          rounded="full"
                          onClick={() => setEditingId(null)}
                        >
                          Cancelar
                        </Button>
                      </Flex>
                    </Table.Cell>
                  </Table.Row>
                ) : (
                  <Table.Row key={cost.id}>
                    <Table.Cell>{cost.name}</Table.Cell>
                    <Table.Cell>{typeLabel(cost.type)}</Table.Cell>
                    <Table.Cell>{formatAmount(cost.default_unit_cost_or_rate)}</Table.Cell>
                    <Table.Cell>{formatAmount(cost.default_quantity_or_minutes)}</Table.Cell>
                    <Table.Cell>{statusLabel(cost.status)}</Table.Cell>
                    <Table.Cell>
                      <Flex gap={2}>
                        <Button
                          size="sm"
                          variant="outline"
                          rounded="full"
                          onClick={() => startEditing(cost)}
                        >
                          Editar {cost.name}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          color="red.fg"
                          rounded="full"
                          onClick={() => setDeleting(cost)}
                        >
                          Eliminar {cost.name}
                        </Button>
                      </Flex>
                    </Table.Cell>
                  </Table.Row>
                )
              )}
            </Table.Body>
          </Table.Root>
        </Table.ScrollArea>
      )}

      {/* Paginación prev/next + total (page_size=50 fijo) */}
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
          disabled={nextDisabled}
          onClick={() => setPage((current) => current + 1)}
        >
          Siguiente
        </Button>
      </Flex>

      {/* Confirmación de borrado */}
      <Dialog.Root
        open={deleting !== null}
        onOpenChange={(details) => {
          if (!details.open) setDeleting(null);
        }}
      >
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <Dialog.Header>
              <Dialog.Title>Eliminar costo por defecto</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Text>
                ¿Seguro que querés eliminar &ldquo;{deleting?.name}&rdquo;?
                Esta acción no se puede deshacer.
              </Text>
            </Dialog.Body>
            <Dialog.Footer>
              <Dialog.ActionTrigger asChild>
                <Button variant="outline" rounded="full">
                  Cancelar
                </Button>
              </Dialog.ActionTrigger>
              <Button colorPalette="red"
                rounded="full"
                loading={deletingBusy}
                onClick={handleDelete}
              >
                Eliminar
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </Flex>
  );
}
