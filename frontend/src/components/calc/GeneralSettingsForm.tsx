"use client";

import { useEffect, useState } from "react";
import { createListCollection } from "@ark-ui/react";
import {
  Button,
  Field,
  Flex,
  Input,
  Select,
} from "@chakra-ui/react";
import { FormSkeleton } from "@/components/ui/skeleton";

import { calcSettingsService } from "@/services/calcSettingsService";
import { toaster } from "@/lib/toaster";
import type { CalcSettingsResponse, RoundingMode } from "@/types/calc";

// Allow-list exacta de modos de redondeo (RF-P5CC-02).
const ROUNDING_MODE_OPTIONS: { value: RoundingMode; label: string }[] = [
  { value: "none", label: "Sin redondeo" },
  { value: "integer", label: "Entero" },
  { value: "multiple_10", label: "Múltiplos de 10" },
  { value: "commercial_99", label: "Comercial 99" },
];

// Ark UI (Chakra v3) usa colecciones para sus selects: items {value, label}.
const ROUNDING_MODE_COLLECTION = createListCollection({
  items: ROUNDING_MODE_OPTIONS.map((option) => ({
    value: option.value,
    label: option.label,
  })),
});

function isValidPercent(value: string): boolean {
  if (value.trim() === "") return false;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 && n <= 100;
}

export default function GeneralSettingsForm() {
  const [form, setForm] = useState<CalcSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;

    calcSettingsService
      .getSettings()
      .then((settings) => {
        if (!cancelled) setForm(settings);
      })
      .catch((error) => {
        if (cancelled) return;
        toaster.create({
          title: "Error al cargar la configuración",
          description:
            error instanceof Error
              ? error.message
              : "No se pudo cargar la configuración.",
          type: "error",
        });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading || !form) {
    return <FormSkeleton fields={7} />;
  }

  const setField =
    (field: keyof CalcSettingsResponse) =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => (prev ? { ...prev, [field]: e.target.value } : prev));
    };

  const percents = [
    form.default_margin_percent,
    form.default_discount_percent,
    form.default_tax_percent,
  ];
  const required = [
    form.business_name,
    form.main_currency_name,
    form.main_currency_symbol,
  ];
  // Validación client-side: no depender del 422 del backend para rango 0-100
  // ni para campos requeridos vacíos.
  const canSave =
    !saving &&
    percents.every(isValidPercent) &&
    required.every((value) => value.trim().length > 0);

  async function handleSave() {
    if (!canSave || !form) return;
    setSaving(true);
    try {
      // PUT = reemplazo completo atómico: SIEMPRE los 7 campos.
      const saved = await calcSettingsService.updateSettings({
        business_name: form.business_name,
        main_currency_name: form.main_currency_name,
        main_currency_symbol: form.main_currency_symbol,
        default_margin_percent: form.default_margin_percent,
        default_discount_percent: form.default_discount_percent,
        default_tax_percent: form.default_tax_percent,
        rounding_mode: form.rounding_mode,
      });
      setForm(saved);
      toaster.create({
        title: "Configuración guardada",
        type: "success",
      });
    } catch (error) {
      toaster.create({
        title: "Error al guardar",
        description:
          error instanceof Error
            ? error.message
            : "No se pudo guardar la configuración.",
        type: "error",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Flex direction="column" gap={4}>
      <Field.Root>
        <Field.Label>Nombre del negocio</Field.Label>
        <Input
          value={form.business_name}
          maxLength={120}
          onChange={setField("business_name")}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label>Moneda principal (nombre)</Field.Label>
        <Input
          value={form.main_currency_name}
          maxLength={40}
          onChange={setField("main_currency_name")}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label>Moneda principal (símbolo)</Field.Label>
        <Input
          value={form.main_currency_symbol}
          maxLength={8}
          onChange={setField("main_currency_symbol")}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label>Margen por defecto (%)</Field.Label>
        <Input
          type="number"
          step="0.01"
          min={0}
          max={100}
          value={form.default_margin_percent}
          onChange={setField("default_margin_percent")}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label>Descuento por defecto (%)</Field.Label>
        <Input
          type="number"
          step="0.01"
          min={0}
          max={100}
          value={form.default_discount_percent}
          onChange={setField("default_discount_percent")}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label>Impuesto por defecto (%)</Field.Label>
        <Input
          type="number"
          step="0.01"
          min={0}
          max={100}
          value={form.default_tax_percent}
          onChange={setField("default_tax_percent")}
        />
      </Field.Root>

      <Field.Root>
        <Field.Label>Modo de redondeo</Field.Label>
        {/* API collection-based de Ark UI: value es string[] y cada item
            se declara con item={{ value, label }}. */}
        <Select.Root
          collection={ROUNDING_MODE_COLLECTION}
          value={[form.rounding_mode]}
          onValueChange={(details) => {
            const next = details.value[0];
            if (!next) return;
            setForm((prev) =>
              prev ? { ...prev, rounding_mode: next as RoundingMode } : prev
            );
          }}
        >
          <Select.Trigger w="100%">
            <Select.ValueText placeholder="Seleccionar modo" />
          </Select.Trigger>
          <Select.Positioner>
            <Select.Content>
              {ROUNDING_MODE_OPTIONS.map((option) => (
                <Select.Item
                  key={option.value}
                  item={{ value: option.value, label: option.label }}
                >
                  {option.label}
                </Select.Item>
              ))}
            </Select.Content>
          </Select.Positioner>
        </Select.Root>
      </Field.Root>

      <Button
        rounded="full"
        loading={saving}
        disabled={!canSave}
        onClick={handleSave}
      >
        Guardar
      </Button>
    </Flex>
  );
}
