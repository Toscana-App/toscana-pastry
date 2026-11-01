"use client";

import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Field,
  Fieldset,
  Flex,
  Grid,
  Heading,
  Input,
  Spinner,
  Switch,
  Text,
} from "@chakra-ui/react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { EnumSelect } from "@/components/ui/enum-select";
import { toaster } from "@/lib/toaster";
import { useSettings } from "../hooks/useSettings";
import { settingsSchema, type SettingsValues } from "../schema";
import {
  DIFFICULTIES,
  SETTINGS_DEFAULTS,
  type SettingsFormValues,
} from "../types";

/** Campo numérico con sufijo opcional (ARS, %, min). */
function NumberField({
  label,
  suffix,
  error,
  helper,
  disabled,
  registerProps,
}: {
  label: string;
  suffix?: string;
  error?: string;
  helper?: string;
  disabled?: boolean;
  registerProps: ReturnType<
    ReturnType<typeof useForm<SettingsFormValues>>["register"]
  >;
}) {
  return (
    <Field.Root invalid={!!error} disabled={disabled}>
      <Field.Label>
        {label}
        {suffix ? (
          <Text as="span" color="fg.muted" fontWeight="400">
            {" "}
            ({suffix})
          </Text>
        ) : null}
      </Field.Label>
      <Input type="number" step="0.01" disabled={disabled} {...registerProps} />
      {helper ? <Field.HelperText>{helper}</Field.HelperText> : null}
      <Field.ErrorText>{error}</Field.ErrorText>
    </Field.Root>
  );
}

/**
 * Configuración del negocio (Fase 4, WU7) — /admin/settings.
 *
 * Tres bloques (RF-P5-01):
 * 1. Mano de obra y margen (hora, margen, paso de redondeo).
 * 2. Costos indirectos: gas y merma, cada uno con su toggle (RF-P5-06: apagar
 *    el toggle obliga a 0 y deshabilita el input).
 * 3. Valores por defecto de recetas nuevas (minutos, porciones, dificultad).
 *
 * PUT completo: se envían los 12 campos siempre. Los errores 422 vuelven por
 * campo y se muestran en su input.
 */
export function SettingsPage() {
  const { settings, loading, saving, error, fieldErrors, save } = useSettings();
  const [saveFailed, setSaveFailed] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isDirty },
  } = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: SETTINGS_DEFAULTS,
  });

  // Cuando llega la configuración del backend, el formulario la refleja.
  useEffect(() => {
    if (settings) reset(settings);
  }, [settings, reset]);

  const includeGas = watch("include_gas");
  const includeWaste = watch("include_waste");

  function zeroOnNaN(event: Event, field: "gas_pct" | "waste_pct") {
    const target = event.target as HTMLInputElement;
    if (Number.isNaN(target.valueAsNumber)) setValue(field, 0);
  }

  async function onSubmit(values: SettingsValues) {
    const ok = await save(values);
    setSaveFailed(!ok);
    if (ok) {
      toaster.create({ title: "Configuración guardada", type: "success" });
    }
  }

  if (loading) {
    return (
      <Flex align="center" justify="center" py={16}>
        <Spinner size="xl" />
      </Flex>
    );
  }

  return (
    <Flex direction="column" gap={6}>
      <Flex direction="column" gap={1}>
        <Heading fontSize="2xl">Configuración</Heading>
        <Text color="fg.muted">
          Estos valores alimentan el cálculo de precios de todas las recetas.
        </Text>
      </Flex>

      {error && (saveFailed || settings === null) ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Title>No se pudo guardar</Alert.Title>
            <Alert.Description>{error}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <Flex direction="column" gap={6} maxW="44rem">
          <Fieldset.Root
            borderWidth="1px"
            borderColor="gray.200"
            rounded="md"
            p={5}
          >
            <Fieldset.Legend fontWeight="600">
              Mano de obra y margen
            </Fieldset.Legend>
            <Grid
              templateColumns={{ base: "1fr", md: "repeat(2, 1fr)" }}
              gap={5}
              mt={4}
            >
              <NumberField
                label="Valor de la hora"
                suffix="ARS"
                error={fieldErrors.hourly_rate ?? errors.hourly_rate?.message}
                registerProps={register("hourly_rate", { valueAsNumber: true })}
              />
              <NumberField
                label="Margen"
                suffix="%"
                error={fieldErrors.margin_pct ?? errors.margin_pct?.message}
                registerProps={register("margin_pct", { valueAsNumber: true })}
              />
              <NumberField
                label="Paso de redondeo"
                suffix="ARS"
                helper="Los precios finales se redondean a este múltiplo."
                error={fieldErrors.round_step ?? errors.round_step?.message}
                registerProps={register("round_step", { valueAsNumber: true })}
              />
            </Grid>

            <Flex align="center" gap={3} mt={5}>
              <Switch.Root
                checked={watch("include_labor")}
                onCheckedChange={(details) =>
                  setValue("include_labor", details.checked, {
                    shouldDirty: true,
                    shouldValidate: true,
                  })
                }
              >
                <Switch.HiddenInput />
                <Switch.Control>
                  <Switch.Thumb />
                </Switch.Control>
              </Switch.Root>
              <Text>Incluir mano de obra en el costo</Text>
            </Flex>
          </Fieldset.Root>

          <Fieldset.Root
            borderWidth="1px"
            borderColor="gray.200"
            rounded="md"
            p={5}
          >
            <Fieldset.Legend fontWeight="600">Costos indirectos</Fieldset.Legend>
            <Grid
              templateColumns={{ base: "1fr", md: "repeat(2, 1fr)" }}
              gap={5}
              mt={4}
            >
              <Flex direction="column" gap={3}>
                <Flex align="center" gap={3}>
                  <Switch.Root
                    checked={includeGas}
                    onCheckedChange={(details) => {
                      setValue("include_gas", details.checked, {
                        shouldDirty: true,
                        shouldValidate: true,
                      });
                      if (!details.checked) {
                        setValue("gas_pct", 0, {
                          shouldDirty: true,
                          shouldValidate: true,
                        });
                      }
                    }}
                  >
                    <Switch.HiddenInput />
                    <Switch.Control>
                      <Switch.Thumb />
                    </Switch.Control>
                  </Switch.Root>
                  <Text>Cargar costo de gas</Text>
                </Flex>
                <NumberField
                  label="Gas"
                  suffix="%"
                  disabled={!includeGas}
                  error={fieldErrors.gas_pct ?? errors.gas_pct?.message}
                  registerProps={register("gas_pct", {
                    valueAsNumber: true,
                    onChange: (e: Event) => zeroOnNaN(e, "gas_pct"),
                  })}
                />
              </Flex>

              <Flex direction="column" gap={3}>
                <Flex align="center" gap={3}>
                  <Switch.Root
                    checked={includeWaste}
                    onCheckedChange={(details) => {
                      setValue("include_waste", details.checked, {
                        shouldDirty: true,
                        shouldValidate: true,
                      });
                      if (!details.checked) {
                        setValue("waste_pct", 0, {
                          shouldDirty: true,
                          shouldValidate: true,
                        });
                      }
                    }}
                  >
                    <Switch.HiddenInput />
                    <Switch.Control>
                      <Switch.Thumb />
                    </Switch.Control>
                  </Switch.Root>
                  <Text>Incluir merma</Text>
                </Flex>
                <NumberField
                  label="Merma"
                  suffix="%"
                  disabled={!includeWaste}
                  error={fieldErrors.waste_pct ?? errors.waste_pct?.message}
                  registerProps={register("waste_pct", {
                    valueAsNumber: true,
                    onChange: (e: Event) => zeroOnNaN(e, "waste_pct"),
                  })}
                />
              </Flex>
            </Grid>

            <Grid
              templateColumns={{ base: "1fr", md: "repeat(2, 1fr)" }}
              gap={5}
              mt={5}
            >
              <NumberField
                label="Recargo por pedido urgente"
                suffix="%"
                error={
                  fieldErrors.urgent_surcharge_pct ??
                  errors.urgent_surcharge_pct?.message
                }
                registerProps={register("urgent_surcharge_pct", {
                  valueAsNumber: true,
                })}
              />
              <NumberField
                label="Markup consumidor final"
                suffix="%"
                error={
                  fieldErrors.consumer_markup_pct ??
                  errors.consumer_markup_pct?.message
                }
                registerProps={register("consumer_markup_pct", {
                  valueAsNumber: true,
                })}
              />
            </Grid>
          </Fieldset.Root>

          <Fieldset.Root
            borderWidth="1px"
            borderColor="gray.200"
            rounded="md"
            p={5}
          >
            <Fieldset.Legend fontWeight="600">
              Valores por defecto de recetas
            </Fieldset.Legend>
            <Grid
              templateColumns={{ base: "1fr", md: "repeat(3, 1fr)" }}
              gap={5}
              mt={4}
            >
              <NumberField
                label="Tiempo de preparación"
                suffix="min"
                error={
                  fieldErrors.default_prep_minutes ??
                  errors.default_prep_minutes?.message
                }
                registerProps={register("default_prep_minutes", {
                  valueAsNumber: true,
                })}
              />
              <NumberField
                label="Porciones"
                error={
                  fieldErrors.default_servings ?? errors.default_servings?.message
                }
                registerProps={register("default_servings", {
                  valueAsNumber: true,
                })}
              />
              <Field.Root invalid={!!errors.default_difficulty}>
                <Field.Label>Dificultad</Field.Label>
                <EnumSelect
                  options={DIFFICULTIES}
                  {...register("default_difficulty")}
                />
                <Field.ErrorText>
                  {errors.default_difficulty?.message}
                </Field.ErrorText>
              </Field.Root>
            </Grid>
          </Fieldset.Root>

          <Flex gap={3} flexWrap="wrap">
            <Button type="submit" colorPalette="brand" loading={saving}>
              Guardar configuración
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={saving}
              onClick={() => reset(SETTINGS_DEFAULTS)}
            >
              Restaurar valores por defecto
            </Button>
            {isDirty ? (
              <Text alignSelf="center" color="fg.muted" fontSize="sm">
                Hay cambios sin guardar.
              </Text>
            ) : null}
          </Flex>
        </Flex>
      </form>
    </Flex>
  );
}
