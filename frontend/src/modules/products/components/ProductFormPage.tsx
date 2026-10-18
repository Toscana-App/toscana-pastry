"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Alert,
  Button,
  Center,
  Dialog,
  Field,
  Flex,
  Heading,
  Input,
  Spinner,
  Table,
  Tabs,
  Text,
  Textarea,
} from "@chakra-ui/react";
import { useForm, useWatch, type FieldErrors } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { EnumSelect } from "@/components/ui/enum-select";
import { formatCents } from "@/lib/format";
import { toaster } from "@/lib/toaster";
import { ingredientsService } from "@/modules/ingredients/service";
import type { Ingredient } from "@/modules/ingredients/types";
import { productFormSchema, type ProductFormValues } from "../schema";
import { productsService } from "../service";
import {
  PRODUCT_DIFFICULTIES,
  RECIPE_UNITS,
  type PriceBreakdown,
  type PreviewLineItem,
  type ProductCreateInput,
  type ProductDifficulty,
  type RecipeUnit,
} from "../types";
import { RecipeEditor } from "./RecipeEditor";

interface ProductFormPageProps {
  mode: "create" | "edit";
  /** Solo en modo edit: id del producto a cargar. */
  productId?: string;
}

const CREATE_DEFAULTS: ProductFormValues = {
  name: "",
  category: "",
  description: "",
  prep_time_min: 0,
  servings: 1,
  difficulty: "simple",
  recipe: [],
};

const PREVIEW_DEBOUNCE_MS = 300;
const DRAFT_DEBOUNCE_MS = 500;

/**
 * Alta y edición de producto (Fase 5, P4) — /productos/new y /productos/{id}/edit.
 *
 * Las 4 pestañas de la spec en un solo form (react-hook-form + zod):
 * Información · Ingredientes · Preparación · Costos.
 *
 * - RF-P4-04: el Costos se recalcula con `POST /pricing/preview` (debounce
 *   300 ms) sin guardar; el motor aplica los settings del negocio.
 * - RF-P4-06: errores inline por campo; al enviar, el tab con el primer error
 *   queda seleccionado.
 * - RNF-P4-02: draft en sessionStorage (solo alta) + confirmación al salir
 *   con cambios sin guardar.
 * - RF-P4-07: un insumo sin precio no bloquea el guardado: se advierte.
 */
export function ProductFormPage({ mode, productId }: ProductFormPageProps) {
  const router = useRouter();
  const isEdit = mode === "edit";
  const backHref =
    isEdit && productId ? `/productos/${productId}` : "/productos";
  const draftKey = `product-draft:${isEdit ? productId : "new"}`;

  const [tab, setTab] = useState("info");
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [loadingIngredients, setLoadingIngredients] = useState(true);
  const [loadingInitial, setLoadingInitial] = useState(isEdit);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [draftRestored, setDraftRestored] = useState(false);
  const [breakdown, setBreakdown] = useState<PriceBreakdown | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const draftTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    control,
    formState: { errors, isDirty },
  } = useForm<ProductFormValues>({
    resolver: zodResolver(productFormSchema),
    defaultValues: CREATE_DEFAULTS,
  });

  // El efecto de draft necesita saber si hay cambios sin mirar el render.
  const isDirtyRef = useRef(isDirty);
  useEffect(() => {
    isDirtyRef.current = isDirty;
  }, [isDirty]);

  // --- Insumos para el editor de receta (catalogo completo) ---------------
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const all: Ingredient[] = [];
        let page = 1;
        for (;;) {
          const data = await ingredientsService.list({ page, page_size: 100 });
          all.push(...data.items);
          if (data.items.length === 0 || all.length >= data.total) break;
          page += 1;
        }
        if (!cancelled) setIngredients(all);
      } catch {
        if (!cancelled) {
          setLoadError("No se pudieron cargar los insumos del catálogo.");
        }
      } finally {
        if (!cancelled) setLoadingIngredients(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // --- Carga inicial en edicion -------------------------------------------
  useEffect(() => {
    if (!isEdit || !productId) return;
    let cancelled = false;

    async function load() {
      try {
        const detail = await productsService.getDetail(productId as string);
        if (cancelled) return;
        reset({
          name: detail.name,
          category: detail.category,
          description: detail.description,
          prep_time_min: detail.prep_time_min,
          servings: detail.servings,
          difficulty: (PRODUCT_DIFFICULTIES as readonly string[]).includes(
            detail.difficulty,
          )
            ? (detail.difficulty as ProductDifficulty)
            : "simple",
          recipe: detail.recipe.map((item) => ({
            ingredient_id: item.ingredient_id,
            qty: Number(item.qty),
            unit: (RECIPE_UNITS as readonly string[]).includes(item.unit)
              ? (item.unit as RecipeUnit)
              : "g",
          })),
        });
      } catch (e) {
        if (!cancelled) {
          setLoadError(
            e instanceof Error ? e.message : "No se pudo cargar el producto",
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
  }, [isEdit, productId, reset]);

  // --- Draft local (solo alta): sesion interrumpida no pierde datos -------
  useEffect(() => {
    if (isEdit) return;
    try {
      const raw = sessionStorage.getItem(draftKey);
      if (!raw) return;
      const parsed = productFormSchema.safeParse(JSON.parse(raw));
      if (parsed.success) {
        reset(parsed.data);
        setDraftRestored(true);
      }
    } catch {
      // Draft corrupto: se ignora y el formulario arranca vacio.
    }
  }, [isEdit, draftKey, reset]);

  useEffect(() => {
    const subscription = watch((values) => {
      if (!isDirtyRef.current) return;
      if (draftTimer.current) clearTimeout(draftTimer.current);
      draftTimer.current = setTimeout(() => {
        try {
          sessionStorage.setItem(draftKey, JSON.stringify(values));
        } catch {
          // sessionStorage lleno o bloqueado: el draft es best-effort.
        }
      }, DRAFT_DEBOUNCE_MS);
    });
    return () => {
      subscription.unsubscribe();
      if (draftTimer.current) clearTimeout(draftTimer.current);
    };
  }, [watch, draftKey]);

  // --- Salida con cambios sin guardar -------------------------------------
  useEffect(() => {
    if (!isDirty) return;
    function onBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [isDirty]);

  // --- Preview del costo en vivo (RF-P4-04) -------------------------------
  const recipeValues = useWatch({ control, name: "recipe" });
  const prepMinutes = useWatch({ control, name: "prep_time_min" });
  const servings = useWatch({ control, name: "servings" });
  const ingredientById = useMemo(
    () => new Map(ingredients.map((item) => [item.id, item])),
    [ingredients],
  );

  const missingPrices = useMemo(() => {
    const names = new Set<string>();
    for (const row of recipeValues ?? []) {
      const ingredient = ingredientById.get(row.ingredient_id);
      if (ingredient && ingredient.price_per_unit === 0) {
        names.add(ingredient.name);
      }
    }
    return Array.from(names);
  }, [recipeValues, ingredientById]);

  useEffect(() => {
    const lines: PreviewLineItem[] = [];
    for (const row of recipeValues ?? []) {
      const ingredient = ingredientById.get(row.ingredient_id);
      if (!ingredient) continue;
      if (!Number.isFinite(row.qty) || row.qty <= 0) continue;
      lines.push({
        qty: row.qty,
        unit: row.unit,
        price_per_purchase_unit: ingredient.price_per_unit,
        purchase_unit: ingredient.unit,
      });
    }

    if (lines.length === 0) {
      setBreakdown(null);
      setPreviewError(null);
      setPreviewing(false);
      return;
    }

    const prep = Number.isFinite(prepMinutes)
      ? Math.min(Math.max(prepMinutes, 0), 1440)
      : 0;
    let cancelled = false;
    setPreviewing(true);

    const timer = setTimeout(async () => {
      try {
        const result = await productsService.preview(lines, prep);
        if (cancelled) return;
        setBreakdown(result);
        setPreviewError(null);
      } catch (e) {
        if (cancelled) return;
        setBreakdown(null);
        setPreviewError(
          e instanceof Error ? e.message : "No se pudo calcular el costo",
        );
      } finally {
        if (!cancelled) setPreviewing(false);
      }
    }, PREVIEW_DEBOUNCE_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [recipeValues, prepMinutes, ingredientById]);

  async function onSubmit(values: ProductFormValues) {
    setSaving(true);
    setServerError(null);
    const payload: ProductCreateInput = {
      name: values.name.trim(),
      category: values.category.trim(),
      description: values.description?.trim() ?? "",
      prep_time_min: values.prep_time_min,
      servings: values.servings,
      difficulty: values.difficulty,
      recipe: values.recipe.map((item) => ({
        ingredient_id: item.ingredient_id,
        qty: item.qty,
        unit: item.unit,
      })),
    };

    try {
      if (isEdit && productId) {
        await productsService.update(productId, payload);
        sessionStorage.removeItem(draftKey);
        toaster.create({ title: "Cambios guardados", type: "success" });
        router.push(`/productos/${productId}`);
      } else {
        const created = await productsService.create(payload);
        sessionStorage.removeItem(draftKey);
        toaster.create({ title: "Producto creado", type: "success" });
        router.push(`/productos/${created.id}`);
      }
    } catch (e) {
      setServerError(
        e instanceof Error ? e.message : "No se pudo guardar el producto",
      );
    } finally {
      setSaving(false);
    }
  }

  function onInvalid(nextErrors: FieldErrors<ProductFormValues>) {
    if (nextErrors.name || nextErrors.category || nextErrors.description) {
      setTab("info");
    } else if (nextErrors.recipe) {
      setTab("recipe");
    } else {
      setTab("prep");
    }
  }

  function requestCancel() {
    if (isDirty) setConfirmDiscard(true);
    else router.push(backHref);
  }

  function discardDraft() {
    sessionStorage.removeItem(draftKey);
    reset(CREATE_DEFAULTS);
    setDraftRestored(false);
  }

  if (loadingInitial) {
    return (
      <Center py={16}>
        <Spinner size="xl" />
      </Center>
    );
  }

  return (
    <Flex direction="column" gap={5} pb={{ base: "7rem", md: 4 }}>
      <Flex align="flex-start" justify="space-between" gap={3} flexWrap="wrap">
        <Flex direction="column" gap={1}>
          <Heading fontSize="2xl">
            {isEdit ? "Editar producto" : "Nuevo producto"}
          </Heading>
          <Text fontSize="sm" color="fg.muted">
            El precio de venta se calcula solo con la receta y la configuración
            del negocio.
          </Text>
        </Flex>
        <Button variant="ghost" onClick={requestCancel} type="button">
          Cancelar
        </Button>
      </Flex>

      {loadError ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Title>No se pudo cargar</Alert.Title>
            <Alert.Description>{loadError}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {serverError ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Title>No se pudo guardar</Alert.Title>
            <Alert.Description>{serverError}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {draftRestored ? (
        <Alert.Root status="info">
          <Alert.Content>
            <Alert.Title>Borrador restaurado</Alert.Title>
            <Alert.Description>
              Recuperamos lo que estabas cargando en esta sesión.{" "}
              <Button variant="plain" size="xs" onClick={discardDraft}>
                Descartar borrador
              </Button>
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      <form onSubmit={handleSubmit(onSubmit, onInvalid)} noValidate>
        <Tabs.Root value={tab} onValueChange={(e) => setTab(e.value ?? "info")}>
          <Tabs.List overflowX="auto">
            <Tabs.Trigger value="info">Información</Tabs.Trigger>
            <Tabs.Trigger value="recipe">Ingredientes</Tabs.Trigger>
            <Tabs.Trigger value="prep">Preparación</Tabs.Trigger>
            <Tabs.Trigger value="costs">Costos</Tabs.Trigger>
          </Tabs.List>

          <Tabs.Content value="info" pt={4}>
            <Flex direction="column" gap={4}>
              <Field.Root invalid={Boolean(errors.name)} required>
                <Field.Label>Nombre</Field.Label>
                <Input placeholder="Torta de chocolate" {...register("name")} />
                <Field.ErrorText>{errors.name?.message}</Field.ErrorText>
              </Field.Root>

              <Field.Root invalid={Boolean(errors.category)} required>
                <Field.Label>Categoría</Field.Label>
                <Input placeholder="Tortas" {...register("category")} />
                <Field.ErrorText>{errors.category?.message}</Field.ErrorText>
              </Field.Root>

              <Field.Root invalid={Boolean(errors.description)}>
                <Field.Label>Descripción</Field.Label>
                <Textarea
                  rows={3}
                  placeholder="Opcional"
                  {...register("description")}
                />
                <Field.ErrorText>{errors.description?.message}</Field.ErrorText>
              </Field.Root>
            </Flex>
          </Tabs.Content>

          <Tabs.Content value="recipe" pt={4}>
            <RecipeEditor
              control={control}
              register={register}
              errors={errors}
              ingredients={ingredients}
              ingredientsLoading={loadingIngredients}
            />
          </Tabs.Content>

          <Tabs.Content value="prep" pt={4}>
            <Flex direction="column" gap={4}>
              <Field.Root invalid={Boolean(errors.prep_time_min)} required>
                <Field.Label>Tiempo de preparación (minutos)</Field.Label>
                <Input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  {...register("prep_time_min", { valueAsNumber: true })}
                />
                <Field.ErrorText>
                  {errors.prep_time_min?.message}
                </Field.ErrorText>
              </Field.Root>

              <Field.Root invalid={Boolean(errors.servings)} required>
                <Field.Label>Porciones</Field.Label>
                <Input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  {...register("servings", { valueAsNumber: true })}
                />
                <Field.ErrorText>{errors.servings?.message}</Field.ErrorText>
              </Field.Root>

              <Field.Root invalid={Boolean(errors.difficulty)}>
                <Field.Label>Dificultad</Field.Label>
                <EnumSelect
                  options={PRODUCT_DIFFICULTIES}
                  {...register("difficulty")}
                />
                <Field.ErrorText>
                  {errors.difficulty?.message}
                </Field.ErrorText>
              </Field.Root>

              <Text fontSize="sm" color="fg.muted">
                La mano de obra se deriva del tiempo de preparación según la
                hora de trabajo cargada en Configuración.
              </Text>
            </Flex>
          </Tabs.Content>

          <Tabs.Content value="costs" pt={4}>
            <CostsPreview
              breakdown={breakdown}
              previewing={previewing}
              previewError={previewError}
              missingPrices={missingPrices}
              servings={Number.isFinite(servings) ? servings : 1}
            />
          </Tabs.Content>
        </Tabs.Root>

        <Flex
          gap={3}
          justify="flex-end"
          align="center"
          mt={6}
          position={{ base: "fixed", md: "static" }}
          bottom={{ base: 0, md: "auto" }}
          left={{ base: 0, md: "auto" }}
          right={{ base: 0, md: "auto" }}
          bg={{ base: "bg.panel", md: "transparent" }}
          borderTopWidth={{ base: "1px", md: "0" }}
          px={{ base: 4, md: 0 }}
          py={{ base: 3, md: 0 }}
          pb={{ base: "calc(0.75rem + env(safe-area-inset-bottom))", md: 0 }}
          zIndex={10}
        >
          <Button variant="outline" type="button" onClick={requestCancel}>
            Cancelar
          </Button>
          <Button colorPalette="brand" type="submit" loading={saving}>
            Guardar producto
          </Button>
        </Flex>
      </form>

      <Dialog.Root
        open={confirmDiscard}
        onOpenChange={(e) => setConfirmDiscard(e.open)}
        role="alertdialog"
      >
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <Dialog.Header>
              <Dialog.Title>¿Descartar los cambios?</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Text>
                Hay cambios sin guardar. Si salís ahora se pierden
                {isEdit ? "" : " (el borrador local se conserva)"}.
              </Text>
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="ghost" onClick={() => setConfirmDiscard(false)}>
                Seguir editando
              </Button>
              <Button colorPalette="red" onClick={() => router.push(backHref)}>
                Descartar
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </Flex>
  );
}

interface CostsPreviewProps {
  breakdown: PriceBreakdown | null;
  previewing: boolean;
  previewError: string | null;
  missingPrices: string[];
  servings: number;
}

/**
 * Costos en vivo (RF-P4-04/05) con el mismo desglose que el detalle.
 * Mientras no hay líneas válidas muestra una guía, no un total en cero.
 */
function CostsPreview({
  breakdown,
  previewing,
  previewError,
  missingPrices,
  servings,
}: CostsPreviewProps) {
  if (previewError) {
    return (
      <Alert.Root status="warning">
        <Alert.Content>
          <Alert.Title>No se pudo calcular</Alert.Title>
          <Alert.Description>{previewError}</Alert.Description>
        </Alert.Content>
      </Alert.Root>
    );
  }

  if (!breakdown) {
    return (
      <Text fontSize="sm" color="fg.muted">
        Agregá insumos a la receta para ver el desglose de costos.
      </Text>
    );
  }

  const rows: Array<{ label: string; value: string }> = [
    { label: "Materiales", value: formatCents(breakdown.materials) },
    { label: "Merma", value: formatCents(breakdown.waste) },
    {
      label: "Materiales con merma",
      value: formatCents(breakdown.materials_con_merma),
    },
    { label: "Mano de obra", value: formatCents(breakdown.labor) },
    { label: "Gas / energía", value: formatCents(breakdown.gas) },
    { label: "Subtotal", value: formatCents(breakdown.base) },
    { label: "Margen", value: `${Number(breakdown.margin_pct)}%` },
  ];

  return (
    <Flex direction="column" gap={4}>
      {missingPrices.length > 0 ? (
        <Alert.Root status="warning">
          <Alert.Content>
            <Alert.Title>Hay insumos sin precio</Alert.Title>
            <Alert.Description>
              {missingPrices.join(", ")}. El costo calculado no los incluye hasta
              que cargues su precio en Ingredientes.
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {previewing ? (
        <Text fontSize="xs" color="fg.muted">
          Calculando…
        </Text>
      ) : null}

      <Table.Root size="sm">
        <Table.Body>
          {rows.map((row) => (
            <Table.Row key={row.label}>
              <Table.Cell color="fg.muted">{row.label}</Table.Cell>
              <Table.Cell
                textAlign="end"
                fontVariantNumeric="tabular-nums"
                w="40%"
              >
                {row.value}
              </Table.Cell>
            </Table.Row>
          ))}
          <Table.Row>
            <Table.Cell fontWeight="600">Precio final</Table.Cell>
            <Table.Cell
              textAlign="end"
              fontSize="xl"
              fontWeight="600"
              fontVariantNumeric="tabular-nums"
            >
              {formatCents(breakdown.rounded)}
            </Table.Cell>
          </Table.Row>
        </Table.Body>
      </Table.Root>

      {servings > 1 ? (
        <Flex justify="space-between" color="fg.muted">
          <Text>Precio por porción (aprox.)</Text>
          <Text fontVariantNumeric="tabular-nums">
            {formatCents(breakdown.rounded / servings)}
          </Text>
        </Flex>
      ) : null}

      {Number(breakdown.final) !== Number(breakdown.rounded) ? (
        <Text fontSize="sm" color="fg.muted">
          Redondeo aplicado: de {formatCents(breakdown.final)} a{" "}
          {formatCents(breakdown.rounded)}.
        </Text>
      ) : null}
    </Flex>
  );
}
