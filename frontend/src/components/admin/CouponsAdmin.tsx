"use client";


import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Dialog,
  Flex,
  Field,
  Input,
  NativeSelect,
  Stack,
  Table,
  Text,
  Switch,
  FormatNumber,
} from "@chakra-ui/react";
import { ListCardSkeleton } from "@/components/ui/skeleton";

import { useCallback, useEffect, useState } from "react";
import {
  createCoupon,
  deleteCoupon,
  fetchCoupons,
  setCouponStatus,
} from "@/services/leadsService";
import {
  CouponCreatePayload,
  CouponOut,
} from "@/types/leads";

const EMPTY_FORM: CouponCreatePayload = {
  code: "",
  type: "percent",
  value: "",
  max_uses: null,
  status: "active",
};

function CouponsAdmin() {
  const [coupons, setCoupons] = useState<CouponOut[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<CouponCreatePayload>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const res = await fetchCoupons(1, 50);
      setCoupons(res.items ?? []);
      setTotal(res.total);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudieron cargar los cupones"
      );
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchCoupons(1, 50);
        if (cancelled) return;
        setCoupons(res.items ?? []);
        setTotal(res.total);
      } catch {
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const openDialog = useCallback(() => {
    setForm(EMPTY_FORM);
    setFormError(null);
    setDialogOpen(true);
  }, []);

  const submit = useCallback(async () => {
    setBusy(true);
    setFormError(null);
    try {
      const payload: CouponCreatePayload = {
        ...form,
        value: form.value.trim(),
        max_uses: form.max_uses ?? null,
      };
      await createCoupon(payload);
      setDialogOpen(false);
      await reload();
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : "No se pudo crear el cupón"
      );
    } finally {
      setBusy(false);
    }
  }, [form, reload]);

  const toggleStatus = useCallback(
    async (coupon: CouponOut) => {
      setBusy(true);
      try {
        await setCouponStatus(
          coupon.id,
          coupon.status === "active" ? "paused" : "active"
        );
        await reload();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "No se pudo actualizar"
        );
      } finally {
        setBusy(false);
      }
    },
    [reload]
  );

  const remove = useCallback(
    async (couponId: string) => {
      setBusy(true);
      setError(null);
      try {
        await deleteCoupon(couponId);
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
    return (
      <Card.Root>
        <Card.Body>
          <ListCardSkeleton
            titleWidth="26%"
            buttonWidth="110px"
            cols={["30%", "22%", "22%", "18%", "8%"]}
            rows={5}
          />
        </Card.Body>
      </Card.Root>
    );
  }

  return (
    <Card.Root>
      <Card.Body>
        <Stack gap={4}>
          <Flex justify="space-between" align="center">
            <Text fontWeight="semibold">
              Cupones ({total})
            </Text>
            <Button size="xs" colorPalette="brand" onClick={openDialog}>
              Nuevo cupón
            </Button>
          </Flex>

          {error && (
            <Alert.Root status="error">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Description>{error}</Alert.Description>
              </Alert.Content>
            </Alert.Root>
          )}

          {coupons.length === 0 ? (
            <Text fontSize="sm" color="fg.muted">
              Todavía no hay cupones.
            </Text>
          ) : (
            <Table.ScrollArea rounded="md">
              <Table.Root size="sm" variant="outline">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeader>Código</Table.ColumnHeader>
                    <Table.ColumnHeader>Valor</Table.ColumnHeader>
                    <Table.ColumnHeader>Usos</Table.ColumnHeader>
                    <Table.ColumnHeader>Estado</Table.ColumnHeader>
                    <Table.ColumnHeader />
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {coupons.map((coupon) => (
                    <Table.Row key={coupon.id}>
                      <Table.Cell>
                        <Text fontWeight="medium">{coupon.code}</Text>
                      </Table.Cell>
                      <Table.Cell fontVariantNumeric="tabular-nums">
                        {coupon.type === "percent" ? `${coupon.value}%` : <FormatNumber value={Number(coupon.value)} style="currency" currency="ARS" />}
                      </Table.Cell>
                      <Table.Cell fontVariantNumeric="tabular-nums">
                        {coupon.uses}
                        {coupon.max_uses !== null && `/${coupon.max_uses}`}
                      </Table.Cell>
                      <Table.Cell>
                        <Flex align="center" gap={2}>
                          <Switch.Root
                            checked={coupon.status === "active"}
                            onCheckedChange={() => void toggleStatus(coupon)}
                            disabled={busy}
                            aria-label={`Activar/pausar ${coupon.code}`}
                          >
                            <Switch.Control />
                            <Switch.Indicator />
                          </Switch.Root>
                          <Badge
                            colorPalette={
                              coupon.status === "active" ? "green" : "gray"
                            }
                            variant="subtle"
                          >
                            {coupon.status === "active" ? "Activo" : "Pausado"}
                          </Badge>
                        </Flex>
                      </Table.Cell>
                      <Table.Cell textAlign="end">
                        <Button
                          size="xs"
                          variant="ghost"
                          colorPalette="red"
                          disabled={busy}
                          onClick={() => void remove(coupon.id)}
                        >
                          Eliminar
                        </Button>
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </Table.ScrollArea>
          )}
        </Stack>
      </Card.Body>

      <Dialog.Root
        open={dialogOpen}
        onOpenChange={(details) => {
          if (!details.open) setDialogOpen(false);
        }}
        size="sm"
      >
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content maxW="sm" overscrollBehavior="contain">
            <Dialog.Header>
              <Dialog.Title>Nuevo cupón</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Stack gap={4}>
                <Field.Root invalid={formError !== null}>
                  <Field.Label>Código</Field.Label>
                  <Input
                    name="code"
                    autoComplete="off"
                    spellCheck={false}
                    placeholder="VERANO20…"
                    value={form.code}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, code: e.target.value }))
                    }
                  />
                </Field.Root>
                <Flex gap={3}>
                  <Box flex="1">
                    <Field.Root>
                      <Field.Label>Tipo</Field.Label>
                      <NativeSelect.Root>
                        <NativeSelect.Field
                          value={form.type}
                          onChange={(e) =>
                            setForm((f) => ({
                              ...f,
                              type: e.target.value as CouponCreatePayload["type"],
                            }))
                          }
                        >
                          <option value="percent">Porcentaje</option>
                          <option value="fixed">Monto fijo</option>
                        </NativeSelect.Field>
                        <NativeSelect.Indicator />
                      </NativeSelect.Root>
                    </Field.Root>
                  </Box>
                  <Box flex="1">
                    <Field.Root>
                      <Field.Label>
                        {form.type === "percent" ? "Porcentaje (0-100)" : "Monto (ARS)"}
                      </Field.Label>
                      <Input
                        name="value"
                        autoComplete="off"
                        type="number"
                        inputMode="decimal"
                        min="0"
                        placeholder={form.type === "percent" ? "10…" : "5000…"}
                        value={form.value}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, value: e.target.value }))
                        }
                      />
                    </Field.Root>
                  </Box>
                </Flex>
                <Field.Root>
                  <Field.Label>Máximo de usos (opcional)</Field.Label>
                  <Input
                    name="max_uses"
                    autoComplete="off"
                    type="number"
                    inputMode="numeric"
                    min="1"
                    placeholder="Sin límite…"
                    value={form.max_uses ?? ""}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        max_uses: e.target.value
                          ? Number(e.target.value)
                          : null,
                      }))
                    }
                  />
                </Field.Root>
                {formError && (
                  <Alert.Root status="error" py={2}>
                    <Alert.Indicator />
                    <Alert.Content>
                      <Alert.Description>{formError}</Alert.Description>
                    </Alert.Content>
                  </Alert.Root>
                )}
              </Stack>
            </Dialog.Body>
            <Dialog.Footer>
              <Dialog.CloseTrigger asChild>
                <Button variant="ghost">Cancelar</Button>
              </Dialog.CloseTrigger>
              <Button
                colorPalette="brand"
                loading={busy}
                disabled={form.code.trim() === "" || form.value.trim() === ""}
                onClick={() => void submit()}
              >
                Crear
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </Card.Root>
  );
}

export default CouponsAdmin;
