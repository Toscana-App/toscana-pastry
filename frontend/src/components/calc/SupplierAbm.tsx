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
  Supplier,
  SupplierCreatePayload,
  SupplierListResponse,
  SupplierUpdatePayload,
} from "@/types/calc";

// Tokens de DESIGN.md: danger para acciones destructivas (hex directo).
const ACCENT_DANGER = "#e23b4a";
// page_size fijo (decisión F1 en PREGUNTAS.md): escala admin, sin selector.
const PAGE_SIZE = 50;

interface SupplierFormValues {
  name: string;
  contact_name: string;
  phone: string;
  email: string;
  notes: string;
}

const EMPTY_FORM: SupplierFormValues = {
  name: "",
  contact_name: "",
  phone: "",
  email: "",
  notes: "",
};

export default function SupplierAbm() {
  const [data, setData] = useState<SupplierListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  // Contador para forzar reintento sin cambios de parámetros.
  const [reloadKey, setReloadKey] = useState(0);

  // Búsqueda: input crudo + valor con debounce (~300 ms) que manda ?q.
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  // Creación (formulario card encima de la tabla).
  const [form, setForm] = useState<SupplierFormValues>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);

  // Edición inline por fila.
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<SupplierFormValues>(EMPTY_FORM);
  const [savingEdit, setSavingEdit] = useState(false);

  // Eliminación con diálogo de confirmación.
  const [deleting, setDeleting] = useState<Supplier | null>(null);
  const [deletingBusy, setDeletingBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!cancelled) {
        setLoading(true);
        setLoadError(false);
      }
      try {
        const response = await calcSettingsService.listSuppliers({
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

  const setCreateField =
    (field: keyof SupplierFormValues) =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
    };

  async function handleCreate() {
    const name = form.name.trim();
    if (!name || creating) return;
    setCreating(true);
    try {
      // Solo se mandan los campos opcionales con contenido.
      const payload: SupplierCreatePayload = { name };
      if (form.contact_name.trim()) payload.contact_name = form.contact_name.trim();
      if (form.phone.trim()) payload.phone = form.phone.trim();
      if (form.email.trim()) payload.email = form.email.trim();
      if (form.notes.trim()) payload.notes = form.notes.trim();

      const created = await calcSettingsService.createSupplier(payload);
      // Refetch de la página actual: respeta filtro, orden y PAGE_SIZE del server.
      setReloadKey((key) => key + 1);
      setForm(EMPTY_FORM);
      toaster.create({ title: "Proveedor creado", type: "success" });
    } catch (error) {
      toaster.create({
        title: "Error al crear",
        description:
          error instanceof Error
            ? error.message
            : "No se pudo crear el proveedor.",
        type: "error",
      });
    } finally {
      setCreating(false);
    }
  }

  function startEditing(supplier: Supplier) {
    setEditingId(supplier.id);
    setEditForm({
      name: supplier.name,
      contact_name: supplier.contact_name ?? "",
      phone: supplier.phone ?? "",
      email: supplier.email ?? "",
      notes: supplier.notes ?? "",
    });
  }

  async function handleSaveEdit() {
    const original = data?.items.find((item) => item.id === editingId);
    if (!original) return;

    // PATCH con SOLO los campos tocados (el backend usa exclude_unset);
    // vaciar un campo envía null para limpiarlo.
    const payload: SupplierUpdatePayload = {};
    const fields: (keyof SupplierFormValues)[] = [
      "name",
      "contact_name",
      "phone",
      "email",
      "notes",
    ];
    for (const field of fields) {
      const next = editForm[field].trim();
      const originalValue = (original[field] ?? "").trim();
      if (next !== originalValue) {
        // name es obligatorio en el backend (1-120): nunca se limpia con
        // null; los otros campos sí admiten null para vaciarlos.
        if (field === "name") {
          payload.name = next;
        } else {
          payload[field] = next || null;
        }
      }
    }
    if (Object.keys(payload).length === 0) {
      setEditingId(null);
      return;
    }

    setSavingEdit(true);
    try {
      const updated = await calcSettingsService.updateSupplier(
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
      toaster.create({ title: "Proveedor actualizado", type: "success" });
    } catch (error) {
      toaster.create({
        title: "Error al actualizar",
        description:
          error instanceof Error
            ? error.message
            : "No se pudo actualizar el proveedor.",
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
      await calcSettingsService.deleteSupplier(deleting.id);
      setReloadKey((key) => key + 1);
      setDeleting(null);
      toaster.create({ title: "Proveedor eliminado", type: "success" });
    } catch (error) {
      // 409 "en uso": el body es {"in_use_by": N}. Se detecta por status y
      // body tipados (ApiError), no por el texto del mensaje.
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
            : "No se pudo eliminar el proveedor.",
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

  const createInputs = (
    <>
      <Input
        aria-label="Nombre"
        placeholder="Nombre"
        maxLength={120}
        value={form.name}
        onChange={setCreateField("name")}
      />
      <Input
        aria-label="Contacto"
        placeholder="Contacto"
        maxLength={120}
        value={form.contact_name}
        onChange={setCreateField("contact_name")}
      />
      <Input
        aria-label="Teléfono"
        placeholder="Teléfono"
        maxLength={30}
        value={form.phone}
        onChange={setCreateField("phone")}
      />
      <Input
        aria-label="Email"
        placeholder="Email"
        maxLength={120}
        value={form.email}
        onChange={setCreateField("email")}
      />
      <Input
        aria-label="Notas"
        placeholder="Notas"
        maxLength={500}
        value={form.notes}
        onChange={setCreateField("notes")}
      />
    </>
  );

  const setEditField =
    (field: keyof SupplierFormValues) =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setEditForm((prev) => ({ ...prev, [field]: e.target.value }));
    };

  return (
    <Flex direction="column" gap={4}>
      <Heading size="md">Proveedores</Heading>

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
          Nuevo proveedor
        </Text>
        <Flex
          direction={{ base: "column", lg: "row" }}
          gap={3}
          wrap="wrap"
          align="center"
        >
          {createInputs}
          <Button
            rounded="full"
            loading={creating}
            disabled={!form.name.trim()}
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
        <SkeletonTable rows={6} cols={["22%", "15%", "15%", "25%", "16%", "7%"]} />
      ) : items.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Title>Sin proveedores</EmptyState.Title>
            <EmptyState.Description>
              No hay proveedores para mostrar.
            </EmptyState.Description>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <Table.ScrollArea borderWidth="1px" rounded="md">
          <Table.Root size="sm" stickyHeader>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Nombre</Table.ColumnHeader>
                <Table.ColumnHeader>Contacto</Table.ColumnHeader>
                <Table.ColumnHeader>Teléfono</Table.ColumnHeader>
                <Table.ColumnHeader>Email</Table.ColumnHeader>
                <Table.ColumnHeader>Notas</Table.ColumnHeader>
                <Table.ColumnHeader>Acciones</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {items.map((supplier) =>
                editingId === supplier.id ? (
                  <Table.Row key={supplier.id}>
                    <Table.Cell>
                      <Input
                        aria-label="Editar nombre"
                        maxLength={120}
                        value={editForm.name}
                        onChange={setEditField("name")}
                      />
                    </Table.Cell>
                    <Table.Cell>
                      <Input
                        aria-label="Editar contacto"
                        maxLength={120}
                        value={editForm.contact_name}
                        onChange={setEditField("contact_name")}
                      />
                    </Table.Cell>
                    <Table.Cell>
                      <Input
                        aria-label="Editar teléfono"
                        maxLength={30}
                        value={editForm.phone}
                        onChange={setEditField("phone")}
                      />
                    </Table.Cell>
                    <Table.Cell>
                      <Input
                        aria-label="Editar email"
                        maxLength={120}
                        value={editForm.email}
                        onChange={setEditField("email")}
                      />
                    </Table.Cell>
                    <Table.Cell>
                      <Input
                        aria-label="Editar notas"
                        maxLength={500}
                        value={editForm.notes}
                        onChange={setEditField("notes")}
                      />
                    </Table.Cell>
                    <Table.Cell>
                      <Flex gap={2}>
                        <Button
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
                  <Table.Row key={supplier.id}>
                    <Table.Cell>{supplier.name}</Table.Cell>
                    <Table.Cell>{supplier.contact_name ?? "—"}</Table.Cell>
                    <Table.Cell>{supplier.phone ?? "—"}</Table.Cell>
                    <Table.Cell>{supplier.email ?? "—"}</Table.Cell>
                    <Table.Cell>{supplier.notes ?? "—"}</Table.Cell>
                    <Table.Cell>
                      <Flex gap={2}>
                        <Button
                          size="sm"
                          variant="outline"
                          rounded="full"
                          onClick={() => startEditing(supplier)}
                        >
                          Editar {supplier.name}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          color={ACCENT_DANGER}
                          rounded="full"
                          onClick={() => setDeleting(supplier)}
                        >
                          Eliminar {supplier.name}
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
              <Dialog.Title>Eliminar proveedor</Dialog.Title>
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
    </Flex>
  );
}
