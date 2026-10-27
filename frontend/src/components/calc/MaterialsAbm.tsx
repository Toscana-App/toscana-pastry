"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Dialog,
  EmptyState,
  Flex,
  Input,
  Select,
  Spinner,
  Table,
  Tag,
  Text,
} from "@chakra-ui/react";
import { createListCollection } from "@ark-ui/react";
import { calcMaterialsService } from "@/services/calcMaterialsService";
import { calcSettingsService } from "@/services/calcSettingsService";
import { toaster } from "@/lib/toaster";
import MaterialForm from "./MaterialForm";
import CostHistoryDialog from "./CostHistoryDialog";
import type {
  Category,
  Material,
  MaterialCreatePayload,
  MaterialListResponse,
  MaterialUpdatePayload,
  MaterialStatus,
  Supplier,
} from "@/types/calc";

// Tokens de DESIGN.md (hex directo, sin sombras): danger para acciones
// destructivas, success (accent light green) y surface-soft para chips.
const ACCENT_DANGER = "#e23b4a";
const SUCCESS_GREEN = "#428619";
const SURFACE_SOFT = "#f4f4f4";
// page_size fijo (decisión F1 en PREGUNTAS.md): escala admin, sin selector.
const PAGE_SIZE = 50;

// Estado (D1 de B8): solo los 2 valores derivados del servidor.
const STATUS_COLLECTION = createListCollection({
  items: [
    { value: "active", label: "Activo" },
    { value: "incomplete", label: "Incompleto" },
  ],
});

// Chip de estado read-only: nunca se envía al backend.
function StatusChip({ status }: { status: MaterialStatus }) {
  return status === "active" ? (
    <Tag.Root size="sm" bg={SUCCESS_GREEN} color="white">
      <Tag.Label>Activo</Tag.Label>
    </Tag.Root>
  ) : (
    <Tag.Root size="sm" bg={SURFACE_SOFT} color="fg.muted">
      <Tag.Label>Incompleto</Tag.Label>
    </Tag.Root>
  );
}

export default function MaterialsAbm() {
  const [data, setData] = useState<MaterialListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  // Contador para forzar reintento sin cambios de parámetros.
  const [reloadKey, setReloadKey] = useState(0);

  // Búsqueda: input crudo + valor con debounce (~300 ms) que manda ?q.
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  // Filtros ("" = sin parámetro).
  const [categoryFilter, setCategoryFilter] = useState("");
  const [supplierFilter, setSupplierFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<MaterialStatus | "">("");

  // Opciones de categoría/proveedor: se cargan UNA sola vez al montar
  // (endpoints F1). Un error acá no rompe la lista principal: los filtros
  // quedan con solo la opción "todos".
  const [categoryOptions, setCategoryOptions] = useState<Category[]>([]);
  const [supplierOptions, setSupplierOptions] = useState<Supplier[]>([]);

  // Creación (card encima de la tabla); el key remonta el form para
  // limpiarlo tras un 201.
  const [createBusy, setCreateBusy] = useState(false);
  const [createFormKey, setCreateFormKey] = useState(0);

  // Edición en diálogo (mismo form, material precargado).
  const [editing, setEditing] = useState<Material | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);

  // Eliminación con diálogo de confirmación.
  const [deleting, setDeleting] = useState<Material | null>(null);
  const [deletingBusy, setDeletingBusy] = useState(false);

  // Historial de costos (RF-P2CC-04) en diálogo.
  const [historyFor, setHistoryFor] = useState<Material | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!cancelled) {
        setLoading(true);
        setLoadError(false);
      }
      try {
        const response = await calcMaterialsService.listMaterials({
          q: search || undefined,
          category_id: categoryFilter || undefined,
          supplier_id: supplierFilter || undefined,
          status: statusFilter || undefined,
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
  }, [search, categoryFilter, supplierFilter, statusFilter, page, reloadKey]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      // Un cambio de búsqueda vuelve a la primera página.
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    let cancelled = false;

    calcSettingsService
      .listCategories("material-categories", { page: 1, page_size: 100 })
      .then((response) => {
        if (!cancelled) setCategoryOptions(response.items);
      })
      .catch(() => {
        // Un error en estas cargas no rompe la lista principal.
      });
    calcSettingsService
      .listSuppliers({ page: 1, page_size: 100 })
      .then((response) => {
        if (!cancelled) setSupplierOptions(response.items);
      })
      .catch(() => {
        // Un error en estas cargas no rompe la lista principal.
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Id→name maps para las columnas Categoría/Proveedor (el response trae
  // solo ids). Id sin match → "—".
  const categoryNameById = useMemo(
    () => new Map(categoryOptions.map((c) => [c.id, c.name])),
    [categoryOptions]
  );
  const supplierNameById = useMemo(
    () => new Map(supplierOptions.map((s) => [s.id, s.name])),
    [supplierOptions]
  );

  const categoryCollection = createListCollection({
    items: categoryOptions.map((c) => ({ value: c.id, label: c.name })),
  });
  const supplierCollection = createListCollection({
    items: supplierOptions.map((s) => ({ value: s.id, label: s.name })),
  });

  async function handleCreate(payload: MaterialCreatePayload) {
    setCreateBusy(true);
    try {
      const created = await calcMaterialsService.createMaterial(payload);
      setData((prev) =>
        prev
          ? {
              ...prev,
              items: [...prev.items, created],
              total: prev.total + 1,
            }
          : prev
      );
      // Limpia el form (remonte) recién confirmado el 201.
      setCreateFormKey((key) => key + 1);
      toaster.create({ title: "Material creado", type: "success" });
    } catch (error) {
      toaster.create({
        title: "Error al crear",
        description:
          error instanceof Error
            ? error.message
            : "No se pudo crear el material.",
        type: "error",
      });
    } finally {
      setCreateBusy(false);
    }
  }

  async function handleSaveEdit(
    payload: MaterialCreatePayload | MaterialUpdatePayload
  ) {
    if (!editing) return;
    // El form en modo edición siempre construye MaterialUpdatePayload.
    const updatePayload = payload as MaterialUpdatePayload;
    setSavingEdit(true);
    try {
      const updated = await calcMaterialsService.updateMaterial(
        editing.id,
        updatePayload
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
      setEditing(null);
      toaster.create({ title: "Material actualizado", type: "success" });
    } catch (error) {
      // 404/422: toast con el detail y el diálogo NO se cierra.
      toaster.create({
        title: "Error al actualizar",
        description:
          error instanceof Error
            ? error.message
            : "No se pudo actualizar el material.",
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
      await calcMaterialsService.deleteMaterial(deleting.id);
      const removedId = deleting.id;
      setData((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.filter((item) => item.id !== removedId),
              total: Math.max(0, prev.total - 1),
            }
          : prev
      );
      setDeleting(null);
      toaster.create({ title: "Material eliminado", type: "success" });
    } catch (error) {
      // 409 "en uso": el body es {"impacted_products": N} sin `detail`,
      // así que apiFetch cae en su fallback "Network error". Para ese
      // caso usamos un mensaje propio; los demás errores traen su
      // `detail` y se muestran como llegan.
      const inUse =
        error instanceof Error && error.message === "Network error";
      toaster.create({
        title: "Error al eliminar",
        description: inUse
          ? "No se puede eliminar: el material está en uso en productos"
          : error instanceof Error
            ? error.message
            : "No se pudo eliminar el material.",
        type: "error",
      });
      setDeleting(null);
    } finally {
      setDeletingBusy(false);
    }
  }

  if (loading) {
    return (
      <Flex align="center" justify="center" py={16}>
        <Spinner size="xl" />
      </Flex>
    );
  }

  if (loadError) {
    return (
      <Flex align="center" direction="column" gap={4} py={16}>
        <Text color={ACCENT_DANGER}>No se pudo cargar la lista.</Text>
        <Button
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

  return (
    <Flex direction="column" gap={4}>
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
          Nuevo material
        </Text>
        <MaterialForm
          key={createFormKey}
          categories={categoryOptions}
          suppliers={supplierOptions}
          busy={createBusy}
          submitLabel="Crear"
          onSubmit={(payload) => handleCreate(payload as MaterialCreatePayload)}
        />
      </Flex>

      {/* Búsqueda (?q) + 3 filtros + total */}
      <Flex align="center" direction={{ base: "column", md: "row" }} gap={3}>
        <Input
          aria-label="Buscar"
          placeholder="Buscar por nombre o código"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <Select.Root
          collection={categoryCollection}
          value={[categoryFilter]}
          onValueChange={(details) => {
            setCategoryFilter(details.value[0] ?? "");
            // Un cambio de filtro vuelve a la primera página.
            setPage(1);
          }}
        >
          <Select.Trigger aria-label="Filtrar por categoría" minW="10rem">
            <Select.ValueText placeholder="Todas las categorías" />
          </Select.Trigger>
          <Select.Positioner>
            <Select.Content>
              {categoryOptions.map((c) => (
                <Select.Item key={c.id} item={{ value: c.id, label: c.name }}>
                  {c.name}
                </Select.Item>
              ))}
            </Select.Content>
          </Select.Positioner>
        </Select.Root>
        <Select.Root
          collection={supplierCollection}
          value={[supplierFilter]}
          onValueChange={(details) => {
            setSupplierFilter(details.value[0] ?? "");
            setPage(1);
          }}
        >
          <Select.Trigger aria-label="Filtrar por proveedor" minW="10rem">
            <Select.ValueText placeholder="Todos los proveedores" />
          </Select.Trigger>
          <Select.Positioner>
            <Select.Content>
              {supplierOptions.map((s) => (
                <Select.Item key={s.id} item={{ value: s.id, label: s.name }}>
                  {s.name}
                </Select.Item>
              ))}
            </Select.Content>
          </Select.Positioner>
        </Select.Root>
        <Select.Root
          collection={STATUS_COLLECTION}
          value={statusFilter ? [statusFilter] : []}
          onValueChange={(details) => {
            const next = details.value[0];
            setStatusFilter(next ? (next as MaterialStatus) : "");
            setPage(1);
          }}
        >
          <Select.Trigger aria-label="Filtrar por estado" minW="10rem">
            <Select.ValueText placeholder="Todos los estados" />
          </Select.Trigger>
          <Select.Positioner>
            <Select.Content>
              <Select.Item item={{ value: "active", label: "Activo" }}>
                Activo
              </Select.Item>
              <Select.Item item={{ value: "incomplete", label: "Incompleto" }}>
                Incompleto
              </Select.Item>
            </Select.Content>
          </Select.Positioner>
        </Select.Root>
        <Text color="fg.muted">Total: {total}</Text>
      </Flex>

      {items.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Title>Sin materiales</EmptyState.Title>
            <EmptyState.Description>
              No hay materiales para mostrar.
            </EmptyState.Description>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <Table.ScrollArea borderWidth="1px" rounded="md">
          <Table.Root size="sm" stickyHeader>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Nombre</Table.ColumnHeader>
                <Table.ColumnHeader>Categoría</Table.ColumnHeader>
                <Table.ColumnHeader>Proveedor</Table.ColumnHeader>
                <Table.ColumnHeader>Unidad</Table.ColumnHeader>
                <Table.ColumnHeader>Precio paquete</Table.ColumnHeader>
                <Table.ColumnHeader>Ctd paquete</Table.ColumnHeader>
                <Table.ColumnHeader>Costo unitario</Table.ColumnHeader>
                <Table.ColumnHeader>Estado</Table.ColumnHeader>
                <Table.ColumnHeader>Acciones</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {items.map((material) => (
                <Table.Row key={material.id}>
                  <Table.Cell>
                    <Flex direction="column">
                      <Text fontWeight="medium">{material.name}</Text>
                      {material.internal_code && (
                        <Text color="fg.muted" fontSize="xs">
                          {material.internal_code}
                        </Text>
                      )}
                    </Flex>
                  </Table.Cell>
                  <Table.Cell>
                    {material.category_id
                      ? categoryNameById.get(material.category_id) ?? "—"
                      : "—"}
                  </Table.Cell>
                  <Table.Cell>
                    {material.supplier_id
                      ? supplierNameById.get(material.supplier_id) ?? "—"
                      : "—"}
                  </Table.Cell>
                  <Table.Cell>
                    {material.unit_of_measure ?? "—"}
                  </Table.Cell>
                  {/* Montos tal cual el str del servidor (sin formateo). */}
                  <Table.Cell>
                    {material.purchase_total_price ?? "—"}
                  </Table.Cell>
                  <Table.Cell>
                    {material.package_quantity ?? "—"}
                  </Table.Cell>
                  <Table.Cell>{material.unit_cost ?? "—"}</Table.Cell>
                  <Table.Cell>
                    <StatusChip status={material.status} />
                  </Table.Cell>
                  <Table.Cell>
                    <Flex gap={2} wrap="wrap">
                      <Button
                        size="sm"
                        variant="outline"
                        rounded="full"
                        onClick={() => setEditing(material)}
                      >
                        Editar {material.name}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        rounded="full"
                        onClick={() => setHistoryFor(material)}
                      >
                        Historial {material.name}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        color={ACCENT_DANGER}
                        rounded="full"
                        onClick={() => setDeleting(material)}
                      >
                        Eliminar {material.name}
                      </Button>
                    </Flex>
                  </Table.Cell>
                </Table.Row>
              ))}
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

      {/* Edición: diálogo con el mismo form precargado */}
      {editing && (
        <Dialog.Root
          open
          onOpenChange={(details) => {
            if (!details.open) setEditing(null);
          }}
        >
          <Dialog.Backdrop />
          <Dialog.Positioner>
            <Dialog.Content>
              <Dialog.Header>
                <Dialog.Title>Editar material</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <MaterialForm
                  initial={editing}
                  categories={categoryOptions}
                  suppliers={supplierOptions}
                  busy={savingEdit}
                  submitLabel="Guardar"
                  onSubmit={handleSaveEdit}
                />
              </Dialog.Body>
            </Dialog.Content>
          </Dialog.Positioner>
        </Dialog.Root>
      )}

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
              <Dialog.Title>Eliminar material</Dialog.Title>
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
              <Button
                bg={ACCENT_DANGER}
                color="white"
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

      {/* Historial de costos (RF-P2CC-04) */}
      {historyFor && (
        <CostHistoryDialog
          material={historyFor}
          onClose={() => setHistoryFor(null)}
        />
      )}
    </Flex>
  );
}
