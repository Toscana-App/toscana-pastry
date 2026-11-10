"use client";

import { useState } from "react";
import {
  Alert,
  Button,
  Drawer,
  Field,
  Flex,
  Input,
} from "@chakra-ui/react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { EnumSelect } from "@/components/ui/enum-select";
import { stockAdjustSchema, type StockAdjustValues } from "../schema";
import { STOCK_REASONS, type StockReason } from "../types";

interface StockDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ingredientName: string;
  unit: string;
  onSubmit: (
    delta: number,
    reason: StockReason,
    ref?: string,
  ) => Promise<{ ok: boolean; message?: string }>;
}

const DEFAULTS: StockAdjustValues = { delta: 0, reason: "compra" };

export function StockDrawer({
  open,
  onOpenChange,
  ingredientName,
  unit,
  onSubmit,
}: StockDrawerProps) {
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<StockAdjustValues>({
    resolver: zodResolver(stockAdjustSchema),
    defaultValues: DEFAULTS,
  });

  function close() {
    reset(DEFAULTS);
    setServerError(null);
    onOpenChange(false);
  }

  async function submit(values: StockAdjustValues) {
    setSubmitting(true);
    setServerError(null);
    const result = await onSubmit(values.delta, values.reason, values.ref || undefined);
    setSubmitting(false);
    if (result.ok) {
      close();
    } else {
      setServerError(result.message ?? "No se pudo aplicar el ajuste.");
    }
  }

  return (
    <Drawer.Root
      open={open}
      onOpenChange={(e) => (e.open ? onOpenChange(true) : close())}
      placement="end"
    >
      <Drawer.Backdrop />
      <Drawer.Positioner>
        <Drawer.Content maxW="26rem" overscrollBehavior="contain">
          <Drawer.Header>
            <Drawer.Title>Ajustar stock</Drawer.Title>
            <Drawer.Description>{ingredientName}</Drawer.Description>
          </Drawer.Header>
          <Drawer.Body>
            <form id="stock-adjust-form" onSubmit={handleSubmit(submit)} noValidate>
              <Flex direction="column" gap={5}>
                {serverError ? (
                  <Alert.Root status="error">
                    <Alert.Content>
                      <Alert.Description>{serverError}</Alert.Description>
                    </Alert.Content>
                  </Alert.Root>
                ) : null}

                <Field.Root invalid={!!errors.delta}>
                  <Field.Label>Cantidad ({unit})</Field.Label>
                  <Input
                    type="number"
                    step="0.01"
                    inputMode="decimal"
                    autoComplete="off"
                    placeholder="2 o −1,5…"
                    autoFocus
                    {...register("delta", {
                      valueAsNumber: true,
                      onChange: (e) => {
                        if (Number.isNaN(e.target.valueAsNumber)) setValue("delta", 0);
                      },
                    })}
                  />
                  <Field.HelperText>
                    Positivo entra stock, negativo lo descuenta.
                  </Field.HelperText>
                  <Field.ErrorText>{errors.delta?.message}</Field.ErrorText>
                </Field.Root>

                <Field.Root invalid={!!errors.reason}>
                  <Field.Label>Motivo</Field.Label>
                  <EnumSelect options={STOCK_REASONS} {...register("reason")} />
                  <Field.ErrorText>{errors.reason?.message}</Field.ErrorText>
                </Field.Root>

                <Field.Root invalid={!!errors.ref}>
                  <Field.Label>Referencia (opcional)</Field.Label>
                  <Input
                    autoComplete="off"
                    placeholder="Proveedor, factura, motivo del descarte…"
                    {...register("ref")}
                  />
                  <Field.ErrorText>{errors.ref?.message}</Field.ErrorText>
                </Field.Root>
              </Flex>
            </form>
          </Drawer.Body>
          <Drawer.Footer>
            <Button variant="ghost" onClick={close} disabled={submitting}>
              Cancelar
            </Button>
            <Button
              type="submit"
              form="stock-adjust-form"
              colorPalette="brand"
              loading={submitting}
            >
              Aplicar ajuste
            </Button>
          </Drawer.Footer>
        </Drawer.Content>
      </Drawer.Positioner>
    </Drawer.Root>
  );
}
