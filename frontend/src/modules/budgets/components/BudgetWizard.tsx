"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Alert,
  Badge,
  Box,
  Button,
  chakra,
  Field,
  Flex,
  Heading,
  HStack,
  Input,
  Spinner,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";
import { customersService } from "@/modules/orders/service";
import type { Customer } from "@/modules/orders/types";
import { budgetClientSchema, budgetItemsSchema } from "../schema";
import { budgetsService } from "../service";
import { CALCULATION_MODE_LABELS, type CalculationMode } from "../types";
import { productsService } from "@/modules/products/service";
import type { ProductListItem } from "@/modules/products/types";
import { formatCents, pesosToCents } from "@/lib/format";

/** RF-P7-04: el borrador del wizard sobrevive a recargas hasta guardarlo. */
const DRAFT_KEY = "budget_wizard_draft";

/**
 * Select nativo estilizado (misma convención de EnumSelect de F5) para
 * pickers de registros (id + label).
 */
const StyledOptionSelect = chakra("select", {
  base: {
    width: "100%",
    height: "2.5rem",
    paddingInline: "0.75rem",
    borderRadius: "md",
    borderWidth: "1px",
    borderColor: "gray.200",
    background: "transparent",
    fontSize: "sm",
    outline: "none",
    _focusVisible: {
      borderColor: "brand.600",
      boxShadow: "0 0 0 1px var(--chakra-colors-brand-600)",
    },
  },
});

interface OptionSelectProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  "aria-label": string;
  options: Array<{ value: string; label: string }>;
}

function OptionSelect({ value, onChange, placeholder, "aria-label": label, options }: OptionSelectProps) {
  return (
    <StyledOptionSelect
      value={value}
      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onChange(e.target.value)}
      aria-label={label}
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </StyledOptionSelect>
  );
}

interface WizardRow {
  key: number;
  product_id: string;
  qty: string;
  /** Precio manual en PESOS (input); "" = precio del motor. */
  price: string;
}

interface DraftState {
  step: number;
  name: string;
  phone: string;
  customer: Customer | null;
  mode: CalculationMode;
  margin: string;
  rows: WizardRow[];
}

function freshDraft(): DraftState {
  return {
    step: 1,
    name: "",
    phone: "",
    customer: null,
    mode: "cost_plus",
    margin: "",
    rows: [{ key: 1, product_id: "", qty: "1", price: "" }],
  };
}

function loadDraft(): DraftState {
  if (typeof window === "undefined") return freshDraft();
  try {
    const raw = window.sessionStorage.getItem(DRAFT_KEY);
    if (!raw) return freshDraft();
    const parsed = JSON.parse(raw) as Partial<DraftState>;
    const base = freshDraft();
    return {
      ...base,
      ...parsed,
      rows: parsed.rows && parsed.rows.length > 0 ? parsed.rows : base.rows,
      customer: parsed.customer ?? null,
    };
  } catch {
    return freshDraft();
  }
}

/** Indicador de pasos (P7): números, activo resaltado, completados con check. */
function StepIndicator({ current, labels }: { current: number; labels: string[] }) {
  return (
    <Flex align="center" w="full" mb={5}>
      {labels.map((label, i) => {
        const n = i + 1;
        const done = n < current;
        const active = n === current;
        return (
          <Flex key={label} align="center" flex={n === labels.length ? "none" : "1"}>
            <HStack gap={2}>
              <Box
                w="28px"
                h="28px"
                borderRadius="full"
                display="flex"
                alignItems="center"
                justifyContent="center"
                fontSize="sm"
                fontWeight={700}
                bg={active ? "brand.500" : done ? "green.400" : "gray.200"}
                color={active || done ? "white" : "gray.600"}
                flexShrink={0}
                aria-hidden={active ? undefined : true}
              >
                {done ? "✓" : n}
              </Box>
              <Text
                fontSize="sm"
                fontWeight={active ? 700 : 500}
                color={active || done ? "fg" : "fg.muted"}
                whiteSpace="nowrap"
              >
                {label}
              </Text>
            </HStack>
            {n < labels.length ? (
              <Box as="hr" flex="1" border="none" h="1px" bg={done ? "green.300" : "gray.200"} mx={3} />
            ) : null}
          </Flex>
        );
      })}
    </Flex>
  );
}

/**
 * Wizard de presupuestos (Fase 7, P7): Cliente → Productos → Resumen.
 *
 * - El cliente se crea (o se adopta vía 409 dedupe, RF-P6-08) al pasar el
 *   paso 1; el presupuesto se guarda SOLO en el paso 3 (RF-P7-04).
 * - Borrador persistido en sessionStorage: sobrevive a recargas.
 * - Los totales finitos los calcula el backend al guardar (costos derivados
 *   contra el catálogo, RF-P8-01); el resumen avisa que se ven al guardar.
 */
export function BudgetWizard() {
  const router = useRouter();
  const [draft, setDraft] = useState<DraftState>(loadDraft);
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});
  const [itemErrors, setItemErrors] = useState<Record<string, string>>({});
  const [savingClient, setSavingClient] = useState(false);
  const [savingBudget, setSavingBudget] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [productsLoading, setProductsLoading] = useState(true);
  const [productsError, setProductsError] = useState<string | null>(null);

  const { step } = draft;

  // RF-P7-04: persistir el borrador en cada cambio.
  useEffect(() => {
    try {
      window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    } catch {
      // sessionStorage no disponible (modo privado): se sigue igual sin draft.
    }
  }, [draft]);

  // Catálogo (paso 2): todo el listado activo, hasta 5 páginas de a 100.
  useEffect(() => {
    if (step < 2) return;
    let cancelled = false;
    (async () => {
      try {
        const all: ProductListItem[] = [];
        let page = 1;
        for (;;) {
          const res = await productsService.list({ page, page_size: 100 });
          all.push(...res.items);
          if (page * res.page_size >= res.total || all.length >= 500) break;
          page += 1;
        }
        if (!cancelled) {
          setProducts(all);
          setProductsError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setProductsError(e instanceof Error ? e.message : "No se pudo cargar el catálogo");
        }
      } finally {
        if (!cancelled) setProductsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [step]);

  const priceByProduct = useMemo(() => {
    const map = new Map<string, number | null>();
    for (const p of products) map.set(p.id, p.price_final);
    return map;
  }, [products]);

  const patch = useCallback((partial: Partial<DraftState>) => setDraft((d) => ({ ...d, ...partial })), []);

  const patchRow = useCallback((key: number, partial: Partial<WizardRow>) => {
    setDraft((d) => ({ ...d, rows: d.rows.map((r) => (r.key === key ? { ...r, ...partial } : r)) }));
  }, []);

  const addRow = useCallback(() => {
    setDraft((d) => ({ ...d, rows: [...d.rows, { key: Math.max(0, ...d.rows.map((r) => r.key)) + 1, product_id: "", qty: "1", price: "" }] }));
  }, []);

  const removeRow = useCallback((key: number) => {
    setDraft((d) =>
      d.rows.length <= 1
        ? { ...d, rows: [{ key: 1, product_id: "", qty: "1", price: "" }] }
        : { ...d, rows: d.rows.filter((r) => r.key !== key) },
    );
  }, []);

  /** Paso 1 → 2: valida y crea/adapta el cliente. */
  const continueFromClient = useCallback(async () => {
    const parsed = budgetClientSchema.safeParse({
      name: draft.name,
      phone: draft.phone,
    });
    if (!parsed.success) {
      const errs: Record<string, string> = {};
      for (const issue of parsed.error.issues) {
        const field = String(issue.path[0] ?? "form");
        if (!errs[field]) errs[field] = issue.message;
      }
      setClientErrors(errs);
      return;
    }
    setClientErrors({});
    setSavingClient(true);
    setError(null);
    try {
      // Dedupe por nombre+teléfono: 409 → el service adopta el existente.
      const customer = await customersService.create({
        name: parsed.data.name,
        phone: parsed.data.phone,
      });
      setDraft((d) => ({ ...d, customer, step: 2 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el cliente");
    } finally {
      setSavingClient(false);
    }
  }, [draft.name, draft.phone]);

  /** Valida el paso 2 y pasa al resumen. */
  const continueFromItems = useCallback(() => {
    // Vacíos como "" (el schema los acepta) o 0 (falla en .min(1) con
    // mensaje claro): nunca undefined, que zod lo lee como campo ausente.
    const rows = draft.rows.map((r) => ({
      product_id: r.product_id,
      qty: r.qty === "" ? 0 : Number(r.qty),
      price_override: draft.mode === "manual" && r.price !== "" ? pesosToCents(r.price) : "",
    }));
    const parsed = budgetItemsSchema.safeParse({
      mode: draft.mode,
      margin_pct: draft.margin === "" ? "" : Number(draft.margin),
      items: rows,
    });
    if (!parsed.success) {
      const errs: Record<string, string> = {};
      for (const issue of parsed.error.issues) {
        const path = issue.path;
        if (path[0] === "items" && typeof path[1] === "number") {
          const key = draft.rows[path[1]]?.key ?? path[1];
          const field = typeof path[2] === "string" ? path[2] : "qty";
          if (!errs[String(key)]) errs[String(key)] = issue.message;
          if (field !== "qty") {
            const pk = `${key}-${field}`;
            if (!errs[pk]) errs[pk] = issue.message;
          }
        } else {
          const field = String(path[0] ?? "form");
          if (!errs[field]) errs[field] = issue.message;
        }
      }
      setItemErrors(errs);
      return;
    }
    setItemErrors({});
    setDraft((d) => ({ ...d, step: 3 }));
  }, [draft]);

  /** Paso 3 → POST /budgets → detalle. */
  const saveBudget = useCallback(async () => {
    setSavingBudget(true);
    setError(null);
    try {
      const items = draft.rows.map((r) => ({
        product_id: r.product_id,
        qty: Number(r.qty),
        price_override: draft.mode === "manual" && r.price !== "" ? pesosToCents(r.price) : null,
      }));
      const budget = await budgetsService.create({
        customer_id: draft.customer!.id,
        calculation_mode: draft.mode,
        margin_pct: draft.margin === "" ? null : draft.margin,
        items,
      });
      try {
        window.sessionStorage.removeItem(DRAFT_KEY);
      } catch {
        // sin draft persistido: nada que limpiar.
      }
      router.push(`/presupuestos/${budget.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el presupuesto");
      setSavingBudget(false);
    }
  }, [draft, router]);

  const clearDraft = useCallback(() => {
    try {
      window.sessionStorage.removeItem(DRAFT_KEY);
    } catch {
      // nada que limpiar
    }
    setDraft(freshDraft());
    setClientErrors({});
    setItemErrors({});
    setError(null);
  }, []);

  return (
    <VStack align="stretch" gap={5} maxW="860px" w="full">
      <Flex align="center" justify="space-between" gap={3} flexWrap="wrap">
        <Heading fontSize="2xl">Nuevo presupuesto</Heading>
        <Button variant="ghost" size="sm" onClick={clearDraft}>
          Empezar de cero
        </Button>
      </Flex>

      <StepIndicator current={step} labels={["Cliente", "Productos", "Resumen"]} />

      {error ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Title>Algo salió mal</Alert.Title>
            <Alert.Description>{error}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {step === 1 ? (
        <Box borderWidth="1px" borderColor="gray.200" rounded="md" p={5}>
          <Stack gap={4}>
            <Text fontSize="sm" color="fg.muted">
              Si el cliente ya existe (mismo nombre y teléfono) se adopta automáticamente, sin
              duplicados (RF-P6-08).
            </Text>
            <Field.Root w="100%">
              <Field.Label>Nombre</Field.Label>
              <Input
                value={draft.name}
                onChange={(e) => patch({ name: e.target.value })}
                placeholder="Ej.: María González"
                aria-label="Nombre del cliente"
              />
              {clientErrors.name ? <Field.ErrorText>{clientErrors.name}</Field.ErrorText> : null}
            </Field.Root>
            <Field.Root w="100%">
              <Field.Label>Teléfono (WhatsApp)</Field.Label>
              <Input
                value={draft.phone}
                onChange={(e) => patch({ phone: e.target.value })}
                placeholder="Ej.: 11 5555 0100"
                aria-label="Teléfono del cliente"
              />
              {clientErrors.phone ? <Field.ErrorText>{clientErrors.phone}</Field.ErrorText> : null}
            </Field.Root>
            <HStack justify="flex-end" pt={1}>
              <Button colorPalette="brand" onClick={continueFromClient} loading={savingClient}>
                Continuar
              </Button>
            </HStack>
          </Stack>
        </Box>
      ) : null}

      {step === 2 ? (
        <Box borderWidth="1px" borderColor="gray.200" rounded="md" p={5}>
          <Stack gap={4}>
            <Text fontSize="sm" color="fg.muted">
              Cliente: <b>{draft.customer?.name}</b> · {draft.customer?.phone}
            </Text>

            <Box w="full">
              <Text fontSize="sm" fontWeight={600} mb={2}>
                Modo de cálculo
              </Text>
              <HStack gap={2} flexWrap="wrap">
                {(["cost_plus", "manual"] as const).map((m) => (
                  <Button
                    key={m}
                    size="sm"
                    rounded="full"
                    whiteSpace="nowrap"
                    variant={draft.mode === m ? "solid" : "outline"}
                    colorPalette={draft.mode === m ? "brand" : "gray"}
                    aria-pressed={draft.mode === m}
                    onClick={() => patch({ mode: m })}
                  >
                    {CALCULATION_MODE_LABELS[m]}
                  </Button>
                ))}
              </HStack>
              <Text fontSize="xs" color="fg.muted" mt={1}>
                {draft.mode === "cost_plus"
                  ? "Cada ítem se vende a costo + margen, el mismo para todos los ítems."
                  : "Cada ítem con su precio de venta manual (no aplica margen)."}
              </Text>
            </Box>

            {draft.mode === "cost_plus" ? (
              <Field.Root w="100%" maxW="240px">
                <Field.Label>Margen (%)</Field.Label>
                <Input
                  type="number"
                  min={0}
                  max={200}
                  value={draft.margin}
                  onChange={(e) => patch({ margin: e.target.value })}
                  placeholder="Margen del negocio"
                  aria-label="Margen por ciento"
                />
                <Field.HelperText>Vacío = margen del negocio.</Field.HelperText>
                {itemErrors.margin_pct ? <Field.ErrorText>{itemErrors.margin_pct}</Field.ErrorText> : null}
              </Field.Root>
            ) : null}

            <Box w="full">
              <Text fontSize="sm" fontWeight={600} mb={2}>
                Productos
              </Text>
              {productsLoading ? (
                <HStack gap={2} py={2}>
                  <Spinner size="sm" color="brand.400" />
                  <Text fontSize="sm" color="fg.muted">
                    Cargando catálogo…
                  </Text>
                </HStack>
              ) : productsError ? (
                <Alert.Root status="error" fontSize="sm">
                  <Alert.Description>{productsError}</Alert.Description>
                </Alert.Root>
              ) : (
                <Stack gap={3}>
                  {draft.rows.map((row, idx) => (
                    <Flex key={row.key} gap={3} wrap="wrap" align="end">
                      <Field.Root w="100%" maxW="300px" flex={1}>
                        <Field.Label>Producto {idx + 1}</Field.Label>
                        <OptionSelect
                          value={row.product_id}
                          onChange={(v) => patchRow(row.key, { product_id: v })}
                          placeholder="Elegir producto…"
                          aria-label={`Producto de la línea ${idx + 1}`}
                          options={products.map((p) => ({
                            value: p.id,
                            label:
                              p.name +
                              (p.price_final != null ? ` · ${formatCents(p.price_final)}` : " · sin precio"),
                          }))}
                        />
                        {itemErrors[String(row.key)] ? (
                          <Field.ErrorText>{itemErrors[String(row.key)]}</Field.ErrorText>
                        ) : null}
                      </Field.Root>
                      <Field.Root w="110px">
                        <Field.Label>Cant.</Field.Label>
                        <Input
                          type="number"
                          min={1}
                          max={99}
                          value={row.qty}
                          onChange={(e) => patchRow(row.key, { qty: e.target.value })}
                          aria-label={`Cantidad de la línea ${idx + 1}`}
                        />
                      </Field.Root>
                      {draft.mode === "manual" ? (
                        <Field.Root w="100%" maxW="170px" flex={1}>
                          <Field.Label>Precio de venta</Field.Label>
                          <Input
                            type="number"
                            min={0.01}
                            step={0.01}
                            value={row.price}
                            onChange={(e) => patchRow(row.key, { price: e.target.value })}
                            placeholder="0.00"
                            aria-label={`Precio de la línea ${idx + 1}`}
                          />
                          {itemErrors[`${row.key}-price_override`] ? (
                            <Field.ErrorText>{itemErrors[`${row.key}-price_override`]}</Field.ErrorText>
                          ) : null}
                        </Field.Root>
                      ) : null}
                      <Button
                        variant="ghost"
                        colorPalette="red"
                        aria-label={`Quitar línea ${idx + 1}`}
                        onClick={() => removeRow(row.key)}
                        disabled={draft.rows.length <= 1}
                      >
                        Quitar
                      </Button>
                    </Flex>
                  ))}
                  <Box alignSelf="start">
                    <Button variant="outline" onClick={addRow}>
                      + Agregar producto
                    </Button>
                  </Box>
                </Stack>
              )}
            </Box>

            <HStack justify="space-between" pt={1}>
              <Button variant="outline" onClick={() => patch({ step: 1 })} disabled={savingClient}>
                ← Volver
              </Button>
              <Button colorPalette="brand" onClick={continueFromItems}>
                Ver resumen
              </Button>
            </HStack>
          </Stack>
        </Box>
      ) : null}

      {step === 3 ? (
        <Box borderWidth="1px" borderColor="gray.200" rounded="md" p={5}>
          <Stack gap={4}>
            <Text fontSize="sm" color="fg.muted">
              Cliente: <b>{draft.customer?.name}</b> · {draft.customer?.phone}
            </Text>

            <Box w="full" overflowX="auto" borderWidth="1px" borderColor="gray.200" rounded="md">
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
                <thead>
                  <tr>
                    {["Producto", "Cantidad", "Precio unitario", ""].map((h, i) => (
                      <th
                        key={`${h}-${i}`}
                        style={{
                          textAlign: "left",
                          padding: "10px 14px",
                          borderBottom: "1px solid #e5e5e5",
                          fontWeight: 600,
                          color: "#525252",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {draft.rows.map((row) => {
                    const product = products.find((p) => p.id === row.product_id);
                    const manualPrice = row.price === "" ? null : pesosToCents(row.price);
                    const price =
                      draft.mode === "manual" ? manualPrice : priceByProduct.get(row.product_id) ?? null;
                    return (
                      <tr key={row.key} style={{ borderBottom: "1px solid #f0f0f0" }}>
                        <td style={{ padding: "10px 14px", fontWeight: 500 }}>
                          {product?.name ?? "—"}
                        </td>
                        <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                          {row.qty}
                        </td>
                        <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                          {price != null ? (
                            <HStack gap={2}>
                              <Badge colorPalette={draft.mode === "manual" ? "purple" : "gray"} variant="subtle">
                                {draft.mode === "manual" ? "manual" : "motor"}
                              </Badge>
                              <span>{formatCents(price)}</span>
                            </HStack>
                          ) : (
                            "se calcula al guardar"
                          )}
                        </td>
                        <td style={{ padding: "10px 14px", textAlign: "right" }}>
                          <Button
                            size="xs"
                            variant="ghost"
                            colorPalette="red"
                            onClick={() => removeRow(row.key)}
                            disabled={draft.rows.length <= 1}
                            aria-label={`Quitar ${product?.name ?? "línea"}`}
                          >
                            Quitar
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Box>

            <HStack gap={4} fontSize="sm" flexWrap="wrap">
              <Text>
                Modo: <b>{CALCULATION_MODE_LABELS[draft.mode]}</b>
              </Text>
              {draft.mode === "cost_plus" ? (
                <Text>
                  Margen: <b>{draft.margin === "" ? "margen del negocio" : `${draft.margin}%`}</b>
                </Text>
              ) : null}
            </HStack>

            <Alert.Root status="info" fontSize="sm">
              <Alert.Description>
                Los costos, la ganancia y el total (con IVA 21%) se calculan al guardar, contra el
                catálogo actual. Los verás en el detalle y ahí podrás editarlos.
              </Alert.Description>
            </Alert.Root>

            <HStack justify="space-between" pt={1}>
              <Button variant="outline" onClick={() => patch({ step: 2 })} disabled={savingBudget}>
                ← Volver
              </Button>
              <Button colorPalette="brand" onClick={saveBudget} loading={savingBudget} disabled={!draft.customer}>
                Guardar presupuesto
              </Button>
            </HStack>
          </Stack>
        </Box>
      ) : null}
    </VStack>
  );
}
