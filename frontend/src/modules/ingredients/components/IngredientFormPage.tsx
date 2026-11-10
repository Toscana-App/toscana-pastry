"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Alert,
  Button,
  Dialog,
  Field,
  Flex,
  Heading,
  Input,
  Text,
} from "@chakra-ui/react";
import { FormSkeleton } from "@/components/ui/skeleton";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { EnumSelect } from "@/components/ui/enum-select";
import { centsToPesos, pesosToCents } from "@/lib/format";
import { toaster } from "@/lib/toaster";
import { ingredientCreateSchema, type IngredientCreateValues } from "../schema";
import { ingredientsService } from "../service";
import { INGREDIENT_UNITS } from "../types";

interface IngredientFormPageProps {
  mode: "create" | "edit";
  ingredientId?: string;
}

const CREATE_DEFAULTS: IngredientCreateValues = {
  name: "",
  unit: "kg",
  price_per_unit: 0,
  stock_qty: 0,
  low_stock_threshold: 0,
};

export function IngredientFormPage({ mode, ingredientId }: IngredientFormPageProps) {
  const router = useRouter();
  const isEdit = mode === "edit";
  const backHref =
    isEdit && ingredientId
      ? `/admin/ingredients/${ingredientId}`
      : "/admin/ingredients";

  const [initialName, setInitialName] = useState<string | null>(null);
  const [loadingInitial, setLoadingInitial] = useState(isEdit);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isDirty },
  } = useForm<IngredientCreateValues>({
    resolver: zodResolver(ingredientCreateSchema),
    defaultValues: CREATE_DEFAULTS,
  });

  useEffect(() => {
    if (!isEdit || !ingredientId) return;
    const id = ingredientId;
    let cancelled = false;

    async function load() {
      try {
        const data = await ingredientsService.getDetail(id, false);
        const ingredient = data.ingredient;
        if (cancelled) return;
        setInitialName(ingredient.name);
        reset({
          name: ingredient.name,
          unit: ingredient.unit,
          price_per_unit: centsToPesos(ingredient.price_per_unit),
          stock_qty: 0,
          low_stock_threshold: Number(ingredient.low_stock_threshold),
        });
      } catch (e) {
        if (!cancelled) {
          setLoadError(
            e instanceof Error ? e.message : "No se pudo cargar el ingrediente",
          );
        }
      } finally {
        if (!cancelled) setLoadingInitial(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [isEdit, ingredientId, reset]);

  function zeroOnNaN(
    event: React.ChangeEvent<HTMLInputElement>,
    field: "stock_qty" | "low_stock_threshold",
  ) {
    if (Number.isNaN(event.target.valueAsNumber)) setValue(field, 0);
  }

  async function onSubmit(values: IngredientCreateValues) {
    setSaving(true);
    setServerError(null);
    try {
      if (isEdit && ingredientId) {
        await ingredientsService.update(ingredientId, {
          name: values.name,
          unit: values.unit,
          price_per_unit: pesosToCents(values.price_per_unit),
          low_stock_threshold: values.low_stock_threshold,
        });
        toaster.create({ title: "Changes saved", type: "success" });
        router.push(`/admin/ingredients/${ingredientId}`);
      } else {
        await ingredientsService.create({
          name: values.name,
          unit: values.unit,
          price_per_unit: pesosToCents(values.price_per_unit),
          stock_qty: values.stock_qty,
          low_stock_threshold: values.low_stock_threshold,
        });
        toaster.create({ title: "Ingredient created", type: "success" });
        router.push("/admin/ingredients");
      }
    } catch (e) {
      setServerError(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setSaving(false);
    }
  }

  function requestCancel() {
    if (isDirty) {
      setConfirmDiscard(true);
      return;
    }
    router.push(backHref);
  }

  if (loadingInitial) {
    return <FormSkeleton fields={6} />;
  }

  if (loadError) {
    return (
      <Alert.Root status="error">
        <Alert.Content>
          <Alert.Title>No se pudo cargar el ingrediente</Alert.Title>
          <Alert.Description>{loadError}</Alert.Description>
        </Alert.Content>
      </Alert.Root>
    );
  }

  return (
    <Flex direction="column" gap={6}>
      <Flex direction="column" gap={1}>
        <Heading fontSize="2xl" textWrap="balance" overflowWrap="anywhere">
          {isEdit ? `Editar: ${initialName ?? ""}` : "Nuevo ingrediente"}
        </Heading>
        <Text color="fg.muted">
          {isEdit
            ? "El stock se ajusta desde el detalle, para que cada cambio quede registrado como movimiento."
            : "El stock inicial queda registrado como movimiento de compra con referencia “inicial”."}
        </Text>
      </Flex>

      {serverError ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Title>No se pudo guardar</Alert.Title>
            <Alert.Description>{serverError}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <Flex direction="column" gap={5} maxW="36rem">
          <Field.Root invalid={!!errors.name}>
            <Field.Label>Nombre</Field.Label>
            <Input
              autoComplete="off"
              placeholder="Harina 0000…"
              {...register("name")}
            />
            <Field.ErrorText>{errors.name?.message}</Field.ErrorText>
          </Field.Root>

          <Flex gap={4} flexWrap="wrap">
            <Field.Root invalid={!!errors.unit} flex="1 1 12rem">
              <Field.Label>Unidad</Field.Label>
              <EnumSelect options={INGREDIENT_UNITS} {...register("unit")} />
              <Field.ErrorText>{errors.unit?.message}</Field.ErrorText>
            </Field.Root>

            <Field.Root invalid={!!errors.price_per_unit} flex="1 1 12rem">
              <Field.Label>Precio por unidad (ARS)</Field.Label>
              <Input
                type="number"
                min={0}
                step="0.01"
                inputMode="decimal"
                autoComplete="off"
                placeholder="1200…"
                {...register("price_per_unit", { valueAsNumber: true })}
              />
              <Field.ErrorText>{errors.price_per_unit?.message}</Field.ErrorText>
            </Field.Root>
          </Flex>

          <Flex gap={4} flexWrap="wrap">
            {!isEdit ? (
              <Field.Root invalid={!!errors.stock_qty} flex="1 1 12rem">
                <Field.Label>Stock inicial</Field.Label>
                <Input
                  type="number"
                  min={0}
                  step="0.01"
                  inputMode="decimal"
                  autoComplete="off"
                  {...register("stock_qty", {
                    valueAsNumber: true,
                    onChange: (e) => zeroOnNaN(e, "stock_qty"),
                  })}
                />
                <Field.ErrorText>{errors.stock_qty?.message}</Field.ErrorText>
              </Field.Root>
            ) : null}

            <Field.Root invalid={!!errors.low_stock_threshold} flex="1 1 12rem">
              <Field.Label>Umbral de stock bajo</Field.Label>
              <Input
                type="number"
                min={0}
                step="0.01"
                inputMode="decimal"
                autoComplete="off"
                {...register("low_stock_threshold", {
                  valueAsNumber: true,
                  onChange: (e) => zeroOnNaN(e, "low_stock_threshold"),
                })}
              />
              <Field.ErrorText>{errors.low_stock_threshold?.message}</Field.ErrorText>
            </Field.Root>
          </Flex>

          <Flex gap={3}>
            <Button type="submit" colorPalette="brand" loading={saving}>
              {isEdit ? "Guardar cambios" : "Crear ingrediente"}
            </Button>
            <Button
              variant="outline"
              type="button"
              onClick={requestCancel}
              disabled={saving}
            >
              Cancelar
            </Button>
          </Flex>
        </Flex>
      </form>

      <Dialog.Root open={confirmDiscard} onOpenChange={(e) => setConfirmDiscard(e.open)}>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content overscrollBehavior="contain">
            <Dialog.Header>
              <Dialog.Title>¿Descartar los cambios?</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Text>
                El formulario tiene cambios sin guardar. Si salís ahora se pierden.
              </Text>
            </Dialog.Body>
            <Dialog.Footer>
              <Dialog.CloseTrigger asChild>
                <Button variant="ghost">Quedarme</Button>
              </Dialog.CloseTrigger>
              <Button
                colorPalette="red"
                onClick={() => {
                  setConfirmDiscard(false);
                  router.push(backHref);
                }}
              >
                Descartar
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </Flex>
  );
}
