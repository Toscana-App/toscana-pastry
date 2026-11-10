"use client";

import { useEffect, useState } from "react";
import {
  Button,
  Dialog,
  EmptyState,
  Flex,
  Heading,
  Input,
  Table,
  Text,
} from "@chakra-ui/react";
import { SkeletonTable } from "@/components/ui/skeleton";

import { calcSettingsService } from "@/services/calcSettingsService";
import { toaster } from "@/lib/toaster";
import { ApiError } from "@/lib/api";
import type {
  Category,
  CategoryCreatePayload,
  CategoryKind,
  CategoryListResponse,
  CategoryUpdatePayload,
} from "@/types/calc";

const PAGE_SIZE = 50;

interface CategoryAbmProps {
  endpoint: CategoryKind;
  title: string;
}

export default function CategoryAbm({ endpoint, title }: CategoryAbmProps) {
  const [data, setData] = useState<CategoryListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

  const [deleting, setDeleting] = useState<Category | null>(null);
  const [deletingBusy, setDeletingBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!cancelled) {
        setLoading(true);
        setLoadError(false);
      }
      try {
        const response = await calcSettingsService.listCategories(endpoint, {
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
  }, [endpoint, search, page, reloadKey]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  async function handleCreate() {
    const name = newName.trim();
    if (!name || creating) return;
    setCreating(true);
    try {
      const payload: CategoryCreatePayload = { name };
      if (newDescription.trim()) payload.description = newDescription.trim();
      await calcSettingsService.createCategory(endpoint, payload);
      setReloadKey((key) => key + 1);
      setNewName("");
      setNewDescription("");
      toaster.create({ title: "Categoría creada", type: "success" });
    } catch (error) {
      toaster.create({
        title: "Error al crear",
        description:
          error instanceof Error
            ? error.message
            : "No se pudo crear la categoría.",
        type: "error",
      });
    } finally {
      setCreating(false);
    }
  }

  function startEditing(category: Category) {
    setEditingId(category.id);
    setEditName(category.name);
    setEditDescription(category.description ?? "");
  }

  async function handleSaveEdit() {
    const original = data?.items.find((item) => item.id === editingId);
    if (!original) return;

    const payload: CategoryUpdatePayload = {};
    const nextName = editName.trim();
    if (nextName !== original.name) payload.name = nextName;
    const nextDescription = editDescription.trim();
    if (nextDescription !== (original.description ?? "")) {
      payload.description = nextDescription || null;
    }
    if (Object.keys(payload).length === 0) {
      setEditingId(null);
      return;
    }

    setSavingEdit(true);
    try {
      const updated = await calcSettingsService.updateCategory(
        endpoint,
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
      toaster.create({ title: "Categoría actualizada", type: "success" });
    } catch (error) {
      toaster.create({
        title: "Error al actualizar",
        description:
          error instanceof Error
            ? error.message
            : "No se pudo actualizar la categoría.",
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
      await calcSettingsService.deleteCategory(endpoint, deleting.id);
      setReloadKey((key) => key + 1);
      setDeleting(null);
      toaster.create({ title: "Categoría eliminada", type: "success" });
    } catch (error) {
      const inUse =
        error instanceof ApiError &&
        error.status === 409 &&
        typeof error.payload === "object" &&
        error.payload !== null &&
        "in_use_by" in error.payload;
      toaster.create({
        title: "Error al eliminar",
        description: inUse
          ? "No se puede eliminar: está en uso"
          : error instanceof Error
            ? error.message
            : "No se pudo eliminar la categoría.",
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

  return (
    <Flex direction="column" gap={4}>
      <Heading size="md">{title}</Heading>

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
          Nueva categoría
        </Text>
        <Flex align="center" direction={{ base: "column", md: "row" }} gap={3}>
          <Input
            aria-label="Nombre"
            name="name"
            autoComplete="off"
            placeholder="Nombre…"
            maxLength={80}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <Input
            aria-label="Descripción"
            name="description"
            autoComplete="off"
            placeholder="Descripción (opcional)…"
            maxLength={200}
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
          />
          <Button colorPalette="brand"
            rounded="full"
            loading={creating}
            disabled={!newName.trim()}
            onClick={handleCreate}
          >
            Crear
          </Button>
        </Flex>
      </Flex>

      {}
      <Flex align="center" gap={3}>
        <Input
          aria-label="Buscar"
          name="q"
          type="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="Buscar…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <Text color="fg.muted" fontVariantNumeric="tabular-nums" aria-live="polite">
          Total: {total}
        </Text>
      </Flex>

      {loading ? (
        <SkeletonTable rows={6} cols={["40%", "45%", "15%"]} />
      ) : items.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Title>Sin categorías</EmptyState.Title>
            <EmptyState.Description>
              No hay categorías para mostrar.
            </EmptyState.Description>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <Table.ScrollArea borderWidth="1px" rounded="md">
          <Table.Root size="sm" stickyHeader>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Nombre</Table.ColumnHeader>
                <Table.ColumnHeader>Descripción</Table.ColumnHeader>
                <Table.ColumnHeader>Acciones</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {items.map((category) =>
                editingId === category.id ? (
                  <Table.Row key={category.id}>
                    <Table.Cell>
                      <Input
                        aria-label="Editar nombre"
                        name="name"
                        autoComplete="off"
                        maxLength={80}
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                      />
                    </Table.Cell>
                    <Table.Cell>
                      <Input
                        aria-label="Editar descripción"
                        name="description"
                        autoComplete="off"
                        maxLength={200}
                        value={editDescription}
                        onChange={(e) => setEditDescription(e.target.value)}
                      />
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
                  <Table.Row key={category.id}>
                    <Table.Cell>{category.name}</Table.Cell>
                    <Table.Cell>{category.description ?? "—"}</Table.Cell>
                    <Table.Cell>
                      <Flex gap={2}>
                        <Button
                          size="sm"
                          variant="outline"
                          rounded="full"
                          onClick={() => startEditing(category)}
                        >
                          Editar {category.name}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          color="red.fg"
                          rounded="full"
                          onClick={() => setDeleting(category)}
                        >
                          Eliminar {category.name}
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
              <Dialog.Title>Eliminar categoría</Dialog.Title>
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
