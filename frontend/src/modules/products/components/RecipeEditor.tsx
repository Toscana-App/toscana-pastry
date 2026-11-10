"use client";

import {
  Button,
  chakra,
  Field,
  Flex,
  IconButton,
  Input,
  Text,
} from "@chakra-ui/react";
import { RecipeLinesSkeleton } from "@/components/ui/skeleton";

import type {
  Control,
  FieldErrors,
  UseFormRegister,
} from "react-hook-form";
import { useFieldArray } from "react-hook-form";
import { EnumSelect } from "@/components/ui/enum-select";
import type { Ingredient } from "@/modules/ingredients/types";
import type { ProductFormValues } from "../schema";
import { RECIPE_UNITS } from "../types";

const StyledSelect = chakra("select", {
  base: {
    width: "100%",
    height: "2.5rem",
    paddingInline: "0.75rem",
    borderRadius: "md",
    borderWidth: "1px",
    borderColor: "border",
    background: "transparent",
    fontSize: "sm",
    outline: "none",
    color: "fg",
    "& option": { bg: "bg", color: "fg" },
    _focusVisible: {
      borderColor: "brand.solid",
      boxShadow: "0 0 0 1px var(--chakra-colors-brand-600)",
    },
  },
});

interface RecipeEditorProps {
  control: Control<ProductFormValues>;
  register: UseFormRegister<ProductFormValues>;
  errors: FieldErrors<ProductFormValues>;
  ingredients: Ingredient[];
  ingredientsLoading: boolean;
}

export function RecipeEditor({
  control,
  register,
  errors,
  ingredients,
  ingredientsLoading,
}: RecipeEditorProps) {
  const { fields, append, remove } = useFieldArray({ control, name: "recipe" });

  return (
    <Flex direction="column" gap={4}>
      <Text fontSize="sm" color="fg.muted">
        Agregá los insumos con su cantidad. Podés usar g o kg, ml o L: el
        cálculo convierte a la unidad de compra del insumo.
      </Text>

      {ingredientsLoading ? (
        <RecipeLinesSkeleton />
      ) : ingredients.length === 0 ? (
        <Text fontSize="sm" color="orange.fg">
          No hay insumos cargados. Creá al menos uno en Ingredientes para poder
          armar la receta.
        </Text>
      ) : null}

      {fields.length === 0 ? (
        <Text fontSize="sm" color="fg.muted">
          La receta está vacía: agregá al menos un insumo.
        </Text>
      ) : null}

      <Flex direction="column" gap={3}>
        {fields.map((field, index) => {
          const rowErrors = errors.recipe?.[index];
          return (
            <Flex key={field.id} direction="column" gap={1}>
              <Flex gap={2} align="flex-end" flexWrap={{ base: "wrap", sm: "nowrap" }}>
                <Field.Root flex="2 1 12rem" invalid={Boolean(rowErrors?.ingredient_id)}>
                  <Field.Label fontSize="xs">Insumo</Field.Label>
                  <StyledSelect
                    {...register(`recipe.${index}.ingredient_id`)}
                    aria-label={`Insumo de la línea ${index + 1}`}
                  >
                    <option value="">Elegí un insumo…</option>
                    {ingredients.map((ing) => (
                      <option key={ing.id} value={ing.id}>
                        {ing.price_per_unit === 0
                          ? `${ing.name} (sin precio)`
                          : `${ing.name} · ${ing.unit}`}
                      </option>
                    ))}
                  </StyledSelect>
                </Field.Root>

                <Field.Root flex="0 1 7rem" invalid={Boolean(rowErrors?.qty)}>
                  <Field.Label fontSize="xs">Cantidad</Field.Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    step="any"
                    min={0}
                    autoComplete="off"
                    {...register(`recipe.${index}.qty`, { valueAsNumber: true })}
                    aria-label={`Cantidad de la línea ${index + 1}`}
                  />
                </Field.Root>

                <Field.Root flex="0 1 6.5rem" invalid={Boolean(rowErrors?.unit)}>
                  <Field.Label fontSize="xs">Unidad</Field.Label>
                  <EnumSelect
                    options={RECIPE_UNITS}
                    {...register(`recipe.${index}.unit`)}
                    aria-label={`Unidad de la línea ${index + 1}`}
                  />
                </Field.Root>

                <IconButton
                  aria-label={`Quitar la línea ${index + 1}`}
                  variant="ghost"
                  colorPalette="red"
                  onClick={() => remove(index)}
                >
                  <span aria-hidden="true">✕</span>
                </IconButton>
              </Flex>
              {rowErrors?.ingredient_id || rowErrors?.qty || rowErrors?.unit ? (
                <Text fontSize="xs" color="red.fg">
                  {rowErrors.ingredient_id?.message ??
                    rowErrors.qty?.message ??
                    rowErrors.unit?.message}
                </Text>
              ) : null}
            </Flex>
          );
        })}
      </Flex>

      <Button
        variant="outline"
        alignSelf="flex-start"
        onClick={() => append({ ingredient_id: "", qty: 1, unit: "g" })}
        disabled={ingredients.length === 0}
      >
        + Agregar insumo
      </Button>

      {errors.recipe?.message ? (
        <Text fontSize="sm" color="red.fg">
          {errors.recipe.message}
        </Text>
      ) : null}
    </Flex>
  );
}
