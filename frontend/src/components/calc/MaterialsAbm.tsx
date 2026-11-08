"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Dialog,
  EmptyState,
  Flex,
  Input,
  Select,
  Table,
  Tag,
  Text,
} from "@chakra-ui/react";
import { AbmListSkeleton } from "@/components/ui/skeleton";

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

const PAGE_SIZE = 50;

const ALL = "__all__";

const STATUS_COLLECTION = createListCollection({
  items: [
    { value: ALL, label: "Todos" },
    { value: "active", label: "Activo" },
    { value: "incomplete", label: "Incompleto" },
  ],
});

function StatusChip({ status }: { status: MaterialStatus }) {
  return status === "active" ? (
    <Tag.Root size="sm" colorPalette="green" variant="subtle">
      <Tag.Label>Activo</Tag.Label>
    </Tag.Root>
  ) : (
    <Tag.Root size="sm" bg="bg.muted" color="fg.muted">
      <Tag.Label>Incompleto</Tag.Label>
    </Tag.Root>
  );
}

export default function MaterialsAbm() {
  const [data, setData] = useState<MaterialListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const [categoryFilter, setCategoryFilter] = useState("");
  const [supplierFilter, setSupplierFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<MaterialStatus | "">("");

  const [categoryOptions, setCategoryOptions] = useState<Category[]>([]);
  const [supplierOptions, setSupplierOptions] = useState<Supplier[]>([]);

  const [createBusy, setCreateBusy] = useState(false);
  const [createFormKey, setCreateFormKey] = useState(0);

  const [editing, setEditing] = useState<Material | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);

  const [deleting, setDeleting] = useState<Material | null>(null);
  const [deletingBusy, setDeletingBusy] = useState(false);

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
      });
    calcSettingsService
      .listSuppliers({ page: 1, page_size: 100 })
      .then((response) => {
        if (!cancelled) setSupplierOptions(response.items);
      })
      .catch(() => {
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const categoryNameById = useMemo(
    () => new Map(categoryOptions.map((c) => [c.id, c.name])),
    [categoryOptions]
  );
  const supplierNameById = useMemo(
    () => new Map(supplierOptions.map((s) => [s.id, s.name])),
    [supplierOptions]
  );

  const categoryCollection = createListCollection({
    items: [
      { value: ALL, label: "Todas" },
      ...categoryOptions.map((c) => ({ value: c.id, label: c.name })),
    ],
  });
  const supplierCollection = createListCollection({
    items: [
      { value: ALL, label: "Todos" },
      ...supplierOptions.map((s) => ({ value: s.id, label: s.name })),
    ],
  });

  async function handleCreate(payload: MaterialCreatePayload) {
    setCreateBusy(true);
    try {
      await calcMaterialsService.createMaterial(payload);
      setReloadKey((key) => key + 1);
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
      if (page > 1 && (data?.items.length ?? 0) <= 1) {
        setPage(page - 1);
      }
      setReloadKey((key) => key + 1);
      setDeleting(null);
      toaster.create({ title: "Material eliminado", type: "success" });
    } catch (error) {
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
      <AbmListSkeleton
        cols={["14%", "20%", "14%", "10%", "14%", "12%", "8%", "8%"]}
        withCreate
        selects={2}
      />
    );
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

  return (
    <Flex direction="column" gap={4}>
      {}
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

      {}
      <Flex align="center" direction={{ base: "column", md: "row" }} gap={3}>
        <Input
          aria-label="Buscar"
          placeholder="Buscar por nombre o código"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <Select.Root
          collection={categoryCollection}
          value={[categoryFilter || ALL]}
          onValueChange={(details) => {
            const next = details.value[0];
            setCategoryFilter(!next || next === ALL ? "" : next);
            setPage(1);
          }}
        >
          <Select.Trigger aria-label="Filtrar por categoría" minW="10rem">
            <Select.ValueText placeholder="Todas" />
          </Select.Trigger>
          <Select.Positioner>
            <Select.Content>
              <Select.Item item={{ value: ALL, label: "Todas" }}>
                Todas
              </Select.Item>
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
          value={[supplierFilter || ALL]}
          onValueChange={(details) => {
            const next = details.value[0];
            setSupplierFilter(!next || next === ALL ? "" : next);
            setPage(1);
          }}
        >
          <Select.Trigger aria-label="Filtrar por proveedor" minW="10rem">
            <Select.ValueText placeholder="Todos" />
          </Select.Trigger>
          <Select.Positioner>
            <Select.Content>
              <Select.Item item={{ value: ALL, label: "Todos" }}>
                Todos
              </Select.Item>
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
          value={[statusFilter || ALL]}
          onValueChange={(details) => {
            const next = details.value[0];
            setStatusFilter(
              !next || next === ALL ? "" : (next as MaterialStatus)
            );
            setPage(1);
          }}
        >
          <Select.Trigger aria-label="Filtrar por estado" minW="10rem">
            <Select.ValueText placeholder="Todos" />
          </Select.Trigger>
          <Select.Positioner>
            <Select.Content>
              <Select.Item item={{ value: ALL, label: "Todos" }}>
                Todos
              </Select.Item>
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
                  {}
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
                        color="red.fg"
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

      {}
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

      {}
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

      {}
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

      {}
      {historyFor && (
        <CostHistoryDialog
          material={historyFor}
          onClose={() => setHistoryFor(null)}
        />
      )}
    </Flex>
  );
}
