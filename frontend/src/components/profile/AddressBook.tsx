"use client";


import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Field,
  Flex,
  Input,
  Stack,
  Text,
} from "@chakra-ui/react";
import { AddressBookLoadingSkeleton } from "@/components/ui/skeleton";

import { useCallback, useEffect, useState } from "react";
import {
  deleteMyAddress,
  fetchMyAddresses,
  updateMyAddress,
} from "@/services/ordersService";
import { Address, addressToLine } from "@/types/orders";

const MAX_ADDRESSES = 5;

interface AddressForm {
  street_line_1: string;
  street_line_2: string;
  city: string;
  postal_code: string;
  province: string;
  phone: string;
}

const EMPTY_FORM: AddressForm = {
  street_line_1: "",
  street_line_2: "",
  city: "",
  postal_code: "",
  province: "",
  phone: "",
};

function toPayload(form: AddressForm) {
  return {
    street_line_1: form.street_line_1.trim(),
    street_line_2: form.street_line_2.trim() || null,
    city: form.city.trim() || null,
    postal_code: form.postal_code.trim() || null,
    province: form.province.trim() || null,
    phone: form.phone.trim() || null,
  };
}

function AddressBook() {
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editing, setEditing] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<AddressForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const res = await fetchMyAddresses();
      setAddresses(res.items ?? []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo cargar el libro"
      );
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchMyAddresses();
        if (cancelled) return;
        setAddresses(res.items ?? []);
      } catch {
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const startCreate = useCallback(() => {
    setEditing(true);
    setEditId(null);
    setForm(EMPTY_FORM);
    setFormError(null);
  }, []);

  const startEdit = useCallback((address: Address) => {
    setEditing(true);
    setEditId(address.id);
    setForm({
      street_line_1: address.street_line_1,
      street_line_2: address.street_line_2 ?? "",
      city: address.city ?? "",
      postal_code: address.postal_code ?? "",
      province: address.province ?? "",
      phone: address.phone ?? "",
    });
    setFormError(null);
  }, []);

  const save = useCallback(
    async (makeDefault: boolean) => {
      setBusy(true);
      setFormError(null);
      const payload = toPayload(form);
      try {
        if (editId) {
          await updateMyAddress(editId, { ...payload, is_default: makeDefault });
        } else {
          const { createMyAddress } = await import("@/services/ordersService");
          await createMyAddress(payload);
        }
        setEditing(false);
        setForm(EMPTY_FORM);
        await reload();
      } catch (err) {
        setFormError(
          err instanceof Error ? err.message : "No se pudo guardar"
        );
      } finally {
        setBusy(false);
      }
    },
    [editId, form, reload]
  );

  const makeDefault = useCallback(
    async (addressId: string) => {
      setBusy(true);
      try {
        await updateMyAddress(addressId, { is_default: true });
        await reload();
      } catch (err) {
        setFormError(
          err instanceof Error ? err.message : "No se pudo cambiar el default"
        );
      } finally {
        setBusy(false);
      }
    },
    [reload]
  );

  const remove = useCallback(
    async (addressId: string) => {
      setBusy(true);
      setError(null);
      try {
        await deleteMyAddress(addressId);
        await reload();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "No se pudo eliminar"
        );
      } finally {
        setBusy(false);
      }
    },
    [reload]
  );

  if (loading) {
    return <AddressBookLoadingSkeleton />;
  }

  return (
    <Card.Root>
      <Card.Body>
        <Stack gap={4}>
          <Flex justify="space-between" align="center">
            <Text fontWeight="semibold">Libro de direcciones</Text>
            <Text fontSize="xs" color="fg.muted" fontVariantNumeric="tabular-nums">
              {addresses.length}/{MAX_ADDRESSES}
            </Text>
          </Flex>

          {error && (
            <Alert.Root status="error" aria-live="polite">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Description>{error}</Alert.Description>
              </Alert.Content>
            </Alert.Root>
          )}

          {addresses.length === 0 && !editing && (
            <Text fontSize="sm" color="fg.muted">
              Todavía no tenés direcciones guardadas.
            </Text>
          )}

          <Stack gap={3}>
            {addresses.map((address) => (
              <Flex
                key={address.id}
                justify="space-between"
                align="flex-start"
                gap={3}
                flexWrap="wrap"
                borderWidth="1px"
                borderColor="border.muted"
                rounded="md"
                p={3}
              >
                <Box minW="0" flex="1">
                  <Flex align="center" gap={2} mb={1} wrap="wrap">
                    <Text
                      fontWeight="medium"
                      style={{
                        display: "-webkit-box",
                        WebkitLineClamp: 1,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {addressToLine(address)}
                    </Text>
                    {address.is_default && (
                      <Badge colorPalette="brand" variant="solid">
                        Predeterminada
                      </Badge>
                    )}
                  </Flex>
                  {address.phone && (
                    <Text fontSize="xs" color="fg.muted">
                      {address.phone}
                    </Text>
                  )}
                </Box>
                <Stack
                  direction={{ base: "column", sm: "row" }}
                  gap={2}
                  align={{ base: "flex-end", sm: "center" }}
                >
                  {!address.is_default && (
                    <Button
                      size="xs"
                      variant="ghost"
                      disabled={busy}
                      onClick={() => void makeDefault(address.id)}
                    >
                      Hacer predeterminada
                    </Button>
                  )}
                  <Button
                    size="xs"
                    variant="outline"
                    disabled={busy}
                    onClick={() => startEdit(address)}
                  >
                    Editar
                  </Button>
                  <Button
                    size="xs"
                    variant="ghost"
                    colorPalette="red"
                    disabled={busy}
                    onClick={() => void remove(address.id)}
                  >
                    Eliminar
                  </Button>
                </Stack>
              </Flex>
            ))}
          </Stack>

          {editing ? (
            <Stack gap={3}>
              <Text fontWeight="medium">
                {editId ? "Editar dirección" : "Nueva dirección"}
              </Text>
              <Flex gap={2} wrap="wrap">
                <Box flex="1" minW="220px">
                  <Field.Root invalid={formError !== null}>
                    <Field.Label>Calle y número</Field.Label>
                    <Input
                      name="street_line_1"
                      autoComplete="address-line1"
                      placeholder="Calle 123…"
                      value={form.street_line_1}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, street_line_1: e.target.value }))
                      }
                    />
                  </Field.Root>
                </Box>
                <Box flex="1" minW="180px">
                  <Field.Root>
                    <Field.Label>Ciudad</Field.Label>
                    <Input
                      name="city"
                      autoComplete="address-level2"
                      placeholder="Ciudad…"
                      value={form.city}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, city: e.target.value }))
                      }
                    />
                  </Field.Root>
                </Box>
                <Box w="140px">
                  <Field.Root>
                    <Field.Label>Código postal</Field.Label>
                    <Input
                      name="postal_code"
                      autoComplete="postal-code"
                      inputMode="numeric"
                      placeholder="1428…"
                      value={form.postal_code}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          postal_code: e.target.value,
                        }))
                      }
                    />
                  </Field.Root>
                </Box>
              </Flex>
              <Flex gap={2} wrap="wrap">
                <Box flex="1" minW="180px">
                  <Field.Root>
                    <Field.Label>Provincia</Field.Label>
                    <Input
                      name="province"
                      autoComplete="address-level1"
                      placeholder="Buenos Aires…"
                      value={form.province}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, province: e.target.value }))
                      }
                    />
                  </Field.Root>
                </Box>
                <Box flex="1" minW="180px">
                  <Field.Root>
                    <Field.Label>Teléfono</Field.Label>
                    <Input
                      type="tel"
                      inputMode="tel"
                      name="phone"
                      autoComplete="tel"
                      placeholder="11 2345 6789…"
                      value={form.phone}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, phone: e.target.value }))
                      }
                    />
                  </Field.Root>
                </Box>
              </Flex>
              {formError && (
                <Alert.Root status="error" py={2} aria-live="polite">
                  <Alert.Indicator />
                  <Alert.Content>
                    <Alert.Description>{formError}</Alert.Description>
                  </Alert.Content>
                </Alert.Root>
              )}
              <Flex gap={2} wrap="wrap">
                <Button
                  colorPalette="brand"
                  loading={busy}
                  disabled={form.street_line_1.trim() === ""}
                  onClick={() => void save(!addresses.some((a) => a.is_default))}
                >
                  Guardar
                </Button>
                {editId === null && addresses.length === 0 && (
                  <Button
                    variant="outline"
                    loading={busy}
                    onClick={() => void save(true)}
                  >
                    Guardar como predeterminada
                  </Button>
                )}
                <Button
                  variant="ghost"
                  onClick={() => {
                    setEditing(false);
                    setForm(EMPTY_FORM);
                    setFormError(null);
                  }}
                >
                  Cancelar
                </Button>
              </Flex>
            </Stack>
          ) : (
            addresses.length < MAX_ADDRESSES && (
              <Button
                variant="outline"
                onClick={startCreate}
                disabled={busy}
              >
                Agregar dirección
              </Button>
            )
          )}
        </Stack>
      </Card.Body>
    </Card.Root>
  );
}

export default AddressBook;
