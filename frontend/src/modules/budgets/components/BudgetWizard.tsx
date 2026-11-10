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
  FormatNumber,
  Heading,
  HStack,
  Input,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";
import { BudgetRowsSkeleton } from "@/components/ui/skeleton";

import { customersService } from "@/modules/orders/service";
import type { Customer } from "@/modules/orders/types";
import { budgetClientSchema, budgetItemsSchema } from "../schema";
import { budgetsService } from "../service";
import { CALCULATION_MODE_LABELS, type CalculationMode } from "../types";
import { productsService } from "@/modules/products/service";
import type { ProductListItem } from "@/modules/products/types";
import { formatCents, pesosToCents, centsToPesos } from "@/lib/format";

const DRAFT_KEY = "budget_wizard_draft";

const StyledOptionSelect = chakra("select", {
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
  price: string;
}

interface DraftState {
  step: number;
  name: string;
  phone: string;
  deliveryAddress: string;
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
    deliveryAddress: "",
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
                bg={active ? "brand.solid" : done ? "green.solid" : "bg.emphasized"}
                color={active || done ? "white" : "fg.muted"}
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
              <Box as="hr" flex="1" border="none" h="1px" bg={done ? "border.success" : "border"} mx={3} />
            ) : null}
          </Flex>
        );
      })}
    </Flex>
  );
}

export function BudgetWizard() {
  const router = useRouter();
  const [draft, setDraft] = useState<DraftState>(loadDraft);
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});
  const [itemErrors, setItemErrors] = useState<Record<string, string>>({});
  const [savingClient, setSavingClient] = useState(false);
  const [savingBudget, setSavingBudget] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<Customer | null>(null);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [productsLoading, setProductsLoading] = useState(true);
  const [productsError, setProductsError] = useState<string | null>(null);

  const { step } = draft;

  useEffect(() => {
    try {
      window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    } catch {
    }
  }, [draft]);

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

  const continueFromClient = useCallback(async () => {
    const parsed = budgetClientSchema.safeParse({
      name: draft.name,
      phone: draft.phone,
      delivery_address: draft.deliveryAddress,
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
      const { customer, adopted } = await customersService.createWithAdoption({
        name: parsed.data.name,
        phone: parsed.data.phone,
        delivery_address:
          parsed.data.delivery_address === "" ? undefined : parsed.data.delivery_address,
      });
      if (adopted) {
        setSuggestion(customer);
        setDraft((d) => ({
          ...d,
          deliveryAddress: customer.delivery_address ?? d.deliveryAddress,
        }));
        return;
      }
      setSuggestion(null);
      setDraft((d) => ({ ...d, customer, step: 2 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar el cliente");
    } finally {
      setSavingClient(false);
    }
  }, [draft.name, draft.phone, draft.deliveryAddress]);

  const continueFromItems = useCallback(() => {
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

  const saveBudget = useCallback(async () => {
    setSavingBudget(true);
    setError(null);
    try {
      const items = draft.rows.map((r) => ({
        product_id: r.product_id,
        qty: Number(r.qty),
        price_override: draft.mode === "manual" && r.price !== "" ? pesosToCents(r.price) : null,
      }));
      const address = draft.deliveryAddress.trim();
      const customer = draft.customer!;
      const budget = await budgetsService.create({
        customer_id: customer.id,
        calculation_mode: draft.mode,
        margin_pct: draft.margin === "" ? null : draft.margin,
        delivery_address: address === "" ? undefined : address,
        items,
      });
      if (address !== "" && customer.delivery_address !== address) {
        await customersService.updateAddress(customer.id, address);
      }
      try {
        window.sessionStorage.removeItem(DRAFT_KEY);
      } catch {
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
    }
    setDraft(freshDraft());
    setClientErrors({});
    setItemErrors({});
    setError(null);
    setSuggestion(null);
  }, []);

  return (
    <VStack align="stretch" gap={5} maxW="860px" w="full">
      <Flex align="center" justify="space-between" gap={3} flexWrap="wrap">
        <Heading fontSize="2xl" textWrap="balance">Nuevo presupuesto</Heading>
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
        <Box borderWidth="1px" borderColor="border" rounded="md" p={5}>
          <Stack gap={4}>
            <Text fontSize="sm" color="fg.muted">
              Si el cliente ya existe (mismo nombre y teléfono) se adopta automáticamente, sin
              duplicados (RF-P6-08).
            </Text>
            <Field.Root w="100%">
              <Field.Label>Nombre</Field.Label>
              <Input
                name="name"
                autoComplete="off"
                value={draft.name}
                onChange={(e) => patch({ name: e.target.value })}
                placeholder="Ej.: María González…"
                aria-label="Nombre del cliente"
              />
              {clientErrors.name ? <Field.ErrorText>{clientErrors.name}</Field.ErrorText> : null}
            </Field.Root>
            <Field.Root w="100%">
              <Field.Label>Teléfono (WhatsApp)</Field.Label>
              <Input
                name="phone"
                type="tel"
                inputMode="tel"
                autoComplete="off"
                value={draft.phone}
                onChange={(e) => patch({ phone: e.target.value })}
                placeholder="Ej.: 11 5555 0100…"
                aria-label="Teléfono del cliente"
              />
              {clientErrors.phone ? <Field.ErrorText>{clientErrors.phone}</Field.ErrorText> : null}
            </Field.Root>
            <Field.Root w="100%">
              <Field.Label>Dirección de entrega</Field.Label>
              <Input
                name="delivery_address"
                autoComplete="off"
                value={draft.deliveryAddress}
                onChange={(e) => patch({ deliveryAddress: e.target.value })}
                placeholder="Ej.: Av. San Martín 1234, San Francisco…"
                aria-label="Dirección de entrega del cliente"
              />
              <Field.HelperText>
                Opcional: se guarda en el cliente y en el presupuesto (RF-P7-06).
              </Field.HelperText>
              {clientErrors.delivery_address ? (
                <Field.ErrorText>{clientErrors.delivery_address}</Field.ErrorText>
              ) : null}
            </Field.Root>
            {suggestion ? (
              <Alert.Root status="info" fontSize="sm">
                <Alert.Content>
                  <Alert.Title>Cliente existente</Alert.Title>
                  <Alert.Description>
                    Ya existe un cliente con este nombre y teléfono: <b>{suggestion.name}</b> ·{" "}
                    {suggestion.phone}
                    {suggestion.delivery_address ? ` · ${suggestion.delivery_address}` : ""}.
                  </Alert.Description>
                  <Button
                    mt={2}
                    size="sm"
                    colorPalette="brand"
                    onClick={() => {
                      setDraft((d) => ({ ...d, customer: suggestion, step: 2 }));
                      setSuggestion(null);
                    }}
                  >
                    Usar datos existentes
                  </Button>
                </Alert.Content>
              </Alert.Root>
            ) : null}
            <HStack justify="flex-end" pt={1}>
              <Button colorPalette="brand" onClick={continueFromClient} loading={savingClient}>
                Continuar
              </Button>
            </HStack>
          </Stack>
        </Box>
      ) : null}

      {step === 2 ? (
        <Box borderWidth="1px" borderColor="border" rounded="md" p={5}>
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
                  name="margin_pct"
                  inputMode="decimal"
                  autoComplete="off"
                  min={0}
                  max={200}
                  value={draft.margin}
                  onChange={(e) => patch({ margin: e.target.value })}
                  placeholder="Margen del negocio…"
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
                <BudgetRowsSkeleton rows={3} />
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
                          name="qty"
                          inputMode="numeric"
                          autoComplete="off"
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
                            name="price"
                            inputMode="decimal"
                            autoComplete="off"
                            min={0.01}
                            step={0.01}
                            value={row.price}
                            onChange={(e) => patchRow(row.key, { price: e.target.value })}
                            placeholder="0.00…"
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
        <Box borderWidth="1px" borderColor="border" rounded="md" p={5}>
          <Stack gap={4}>
            <Text fontSize="sm" color="fg.muted">
              Cliente: <b>{draft.customer?.name}</b> · {draft.customer?.phone}
            </Text>
            {draft.deliveryAddress.trim() ? (
              <Text fontSize="sm" color="fg.muted">
                Entrega: {draft.deliveryAddress}
              </Text>
            ) : null}

            <Box w="full" overflowX="auto" borderWidth="1px" borderColor="border" rounded="md">
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
                <thead>
                  <tr>
                    {["Producto", "Cantidad", "Precio unitario", ""].map((h, i) => (
                      <th
                        key={`${h}-${i}`}
                        style={{
                          textAlign: "left",
                          padding: "10px 14px",
                          borderBottom: "1px solid var(--chakra-colors-border)",
                          fontWeight: 600,
                          color: "var(--chakra-colors-fg-muted)",
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
                      <tr key={row.key} style={{ borderBottom: "1px solid var(--chakra-colors-border-muted)" }}>
                        <td style={{ padding: "10px 14px", fontWeight: 500, overflowWrap: "anywhere" }}>
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
                              <span><FormatNumber value={centsToPesos(price)} style="currency" currency="ARS" /></span>
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
                Los costos, la ganancia y el total de venta se calculan al guardar, contra el
                catálogo actual. El IVA (21%) se muestra aparte, como costo separado del total.
                Lo verás en el detalle y ahí podrás editarlo.
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
