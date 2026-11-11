"use client";

import { useEffect, useMemo } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Alert,
  Box,
  Button,
  Dialog,
  Field,
  Flex,
  HStack,
  Input,
  NativeSelect,
  Stack,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react";
import { formatCents } from "@/lib/format";
import {
  invoiceCreateSchema,
  type InvoiceFormValues,
  type InvoicePayload,
} from "../schema";
import {
  CONCEPT_LABELS,
  DOC_TYPE_LABELS,
  INVOICE_CONCEPTS,
  INVOICE_DOC_TYPES,
  type InvoiceCreatePayload,
  type InvoiceItemPayload,
} from "../types";

interface InvoiceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orderId: string;
  orderCode: string;
  total: number;
  receptorNombreInicial: string;
  items: InvoiceItemPayload[];
  issuing: boolean;
  error: string | null;
  onConfirm: (payload: InvoiceCreatePayload) => void;
}

function defaultValue(
  orderId: string,
  receptorNombreInicial: string
): InvoiceFormValues {
  return {
    order_id: orderId,
    concepto: 1,
    fch_serv_desde: null,
    fch_serv_hasta: null,
    doc_tipo: 99,
    doc_nro: 0,
    receptor_nombre: receptorNombreInicial,
  };
}

/**
 * Diálogo de emisión de factura. Muestra la advertencia de irreversibilidad, el
 * resumen del pedido, el formulario (concepto/fechas/receptor) y los ítems
 * pre-cargados (lectura). Sin confirmación NO se emite nada.
 */
export function InvoiceDialog({
  open,
  onOpenChange,
  orderId,
  orderCode,
  total,
  receptorNombreInicial,
  items,
  issuing,
  error,
  onConfirm,
}: InvoiceDialogProps) {
  const defaults = useMemo(
    () => defaultValue(orderId, receptorNombreInicial),
    [orderId, receptorNombreInicial],
  );

  const {
    register,
    handleSubmit,
    setValue,
    control,
    reset,
    formState: { errors },
  } = useForm<InvoiceFormValues, unknown, InvoicePayload>({
    resolver: zodResolver(invoiceCreateSchema),
    defaultValues: defaults,
  });

  const docTipo = useWatch({ control, name: "doc_tipo" });
  const concepto = useWatch({ control, name: "concepto" });
  const isConsumidorFinal = docTipo === 99;
  const needsDates = concepto === 2 || concepto === 3;

  // Al abrir, reinicia al estado inicial (por si se cerró sin enviar).
  useEffect(() => {
    if (open) reset(defaults);
  }, [open, reset, defaults]);

  // Consumidor Final: el número queda fijo en 0 (y deshabilitado).
  useEffect(() => {
    if (isConsumidorFinal) setValue("doc_nro", 0, { shouldValidate: false });
  }, [isConsumidorFinal, setValue]);

  const onSubmit = (values: InvoicePayload) => {
    onConfirm({
      ...values,
      items: items.length > 0 ? items : undefined,
    });
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(e) => onOpenChange(e.open)}
      role="alertdialog"
    >
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content maxW="560px">
          <Dialog.Header>
            <Dialog.Title>Emitir factura</Dialog.Title>
            <Dialog.Description>
              Resumen del pedido {orderCode}
            </Dialog.Description>
          </Dialog.Header>

          <form
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              void handleSubmit(onSubmit)();
            }}
          >
            <Dialog.Body>
              <VStack align="stretch" gap={4}>
                <Alert.Root status="warning">
                  <Alert.Indicator />
                  <Alert.Content>
                    <Alert.Title>Acción irreversible</Alert.Title>
                    <Alert.Description>
                      La factura queda registrada en ARCA con su CAE y no puede
                      cancelarse; solo podría revertirse con una nota de crédito.
                    </Alert.Description>
                  </Alert.Content>
                </Alert.Root>

                <Box
                  borderWidth="1px"
                  borderColor="border.muted"
                  rounded="md"
                  p={3}
                >
                  <Stack gap={1} fontSize="sm">
                    <HStack justify="space-between">
                      <Text color="fg.muted">Total</Text>
                      <Text fontWeight="600" fontVariantNumeric="tabular-nums">
                        {formatCents(total)}
                      </Text>
                    </HStack>
                    <HStack justify="space-between">
                      <Text color="fg.muted">Receptor por defecto</Text>
                      <Text fontWeight="600">
                        {receptorNombreInicial || "—"}
                      </Text>
                    </HStack>
                  </Stack>
                </Box>

                <Field.Root>
                  <Field.Label>Concepto</Field.Label>
                  <NativeSelect.Root>
                    <NativeSelect.Field
                      {...register("concepto", { valueAsNumber: true })}
                    >
                      {INVOICE_CONCEPTS.map((c) => (
                        <option key={c} value={c}>
                          {CONCEPT_LABELS[c]}
                        </option>
                      ))}
                    </NativeSelect.Field>
                    <NativeSelect.Indicator />
                  </NativeSelect.Root>
                </Field.Root>

                {needsDates ? (
                  <Flex gap={3}>
                    <Field.Root
                      invalid={Boolean(errors.fch_serv_desde)}
                      required
                    >
                      <Field.Label>Desde</Field.Label>
                      <Input
                        type="date"
                        {...register("fch_serv_desde", {
                          setValueAs: (v: string) => (v === "" ? null : v),
                        })}
                      />
                      <Field.ErrorText>
                        {errors.fch_serv_desde?.message}
                      </Field.ErrorText>
                    </Field.Root>
                    <Field.Root
                      invalid={Boolean(errors.fch_serv_hasta)}
                      required
                    >
                      <Field.Label>Hasta</Field.Label>
                      <Input
                        type="date"
                        {...register("fch_serv_hasta", {
                          setValueAs: (v: string) => (v === "" ? null : v),
                        })}
                      />
                      <Field.ErrorText>
                        {errors.fch_serv_hasta?.message}
                      </Field.ErrorText>
                    </Field.Root>
                  </Flex>
                ) : null}

                <Flex gap={3}>
                  <Field.Root flex="1">
                    <Field.Label>Tipo de documento</Field.Label>
                    <NativeSelect.Root>
                      <NativeSelect.Field
                        {...register("doc_tipo", { valueAsNumber: true })}
                      >
                        {INVOICE_DOC_TYPES.map((d) => (
                          <option key={d} value={d}>
                            {DOC_TYPE_LABELS[d]}
                          </option>
                        ))}
                      </NativeSelect.Field>
                      <NativeSelect.Indicator />
                    </NativeSelect.Root>
                  </Field.Root>
                  <Field.Root flex="1" invalid={Boolean(errors.doc_nro)}>
                    <Field.Label>Número</Field.Label>
                    <Input
                      type="number"
                      min={0}
                      placeholder="0"
                      disabled={isConsumidorFinal}
                      {...register("doc_nro", { valueAsNumber: true })}
                    />
                    <Field.ErrorText>{errors.doc_nro?.message}</Field.ErrorText>
                  </Field.Root>
                </Flex>

                <Field.Root
                  invalid={Boolean(errors.receptor_nombre)}
                  required
                >
                  <Field.Label>Nombre del receptor</Field.Label>
                  <Input
                    placeholder="Nombre del cliente"
                    {...register("receptor_nombre")}
                  />
                  <Field.ErrorText>
                    {errors.receptor_nombre?.message}
                  </Field.ErrorText>
                </Field.Root>

                <Box>
                  <Text fontSize="sm" fontWeight="600" mb={2}>
                    Ítems (desde el pedido)
                  </Text>
                  <Box
                    borderWidth="1px"
                    borderColor="border.muted"
                    rounded="md"
                    overflowX="auto"
                  >
                    <Table.Root size="sm" variant="line">
                      <Table.Header>
                        <Table.Row>
                          <Table.ColumnHeader>Descripción</Table.ColumnHeader>
                          <Table.ColumnHeader textAlign="right">
                            Cant.
                          </Table.ColumnHeader>
                          <Table.ColumnHeader textAlign="right">
                            Precio unit.
                          </Table.ColumnHeader>
                        </Table.Row>
                      </Table.Header>
                      <Table.Body>
                        {items.map((item, i) => (
                          <Table.Row key={i}>
                            <Table.Cell>{item.descripcion}</Table.Cell>
                            <Table.Cell
                              textAlign="right"
                              fontVariantNumeric="tabular-nums"
                            >
                              {item.cantidad}
                            </Table.Cell>
                            <Table.Cell
                              textAlign="right"
                              fontVariantNumeric="tabular-nums"
                            >
                              {formatCents(item.precio_unit)}
                            </Table.Cell>
                          </Table.Row>
                        ))}
                      </Table.Body>
                    </Table.Root>
                  </Box>
                </Box>

                {error ? (
                  <Alert.Root status="error">
                    <Alert.Indicator />
                    <Alert.Content>
                      <Alert.Description>{error}</Alert.Description>
                    </Alert.Content>
                  </Alert.Root>
                ) : null}
              </VStack>
            </Dialog.Body>

            <Dialog.Footer>
              <Button
                variant="ghost"
                type="button"
                onClick={() => onOpenChange(false)}
              >
                Cancelar
              </Button>
              <Button type="submit" colorPalette="brand" loading={issuing}>
                Emitir factura
              </Button>
            </Dialog.Footer>
          </form>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
