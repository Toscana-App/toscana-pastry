"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  chakra,
  Field,
  Flex,
  Heading,
  HStack,
  Input,
  Skeleton,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";
import { BudgetRowsSkeleton } from "@/components/ui/skeleton";

import NextLink from "next/link";
import { useRouter } from "next/navigation";
import { formatCents, pesosToCents, centsToPesos } from "@/lib/format";
import { budgetItemsSchema } from "../schema";
import { budgetsService } from "../service";
import {
  CALCULATION_MODE_LABELS,
  type BudgetDetail,
  type CalculationMode,
} from "../types";
import { productsService } from "@/modules/products/service";
import type { ProductListItem } from "@/modules/products/types";

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
      boxShadow: "0 0 0 1px var(--chakra-colors-brand-focus-ring)",
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

interface EditRow {
  key: number;
  product_id: string;
  qty: string;
  price: string;
}

interface BudgetEditPageProps {
  budgetId: string;
}

export function BudgetEditPage({ budgetId }: BudgetEditPageProps) {
  const router = useRouter();
  const [budget, setBudget] = useState<BudgetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<CalculationMode>("cost_plus");
  const [margin, setMargin] = useState("");
  const [rows, setRows] = useState<EditRow[]>([]);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [productsLoading, setProductsLoading] = useState(true);
  const [productsError, setProductsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    budgetsService
      .getDetail(budgetId)
      .then((d) => {
        if (cancelled) return;
        setBudget(d);
        setMode(d.calculation_mode);
        setMargin(d.margin_pct == null ? "" : String(d.margin_pct));
        setRows(
          d.items.map((it, i) => ({
            key: i + 1,
            product_id: it.product_id,
            qty: String(it.qty),
            price:
              d.calculation_mode === "manual" && it.price_overridden
                ? String(centsToPesos(it.unit_selling))
                : "",
          })),
        );
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "No se pudo cargar el presupuesto");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [budgetId]);

  useEffect(() => {
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
  }, []);

  const priceByProduct = useMemo(() => {
    const map = new Map<string, number | null>();
    for (const p of products) map.set(p.id, p.price_final);
    return map;
  }, [products]);

  const patchRow = useCallback((key: number, partial: Partial<EditRow>) => {
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...partial } : r)));
  }, []);

  const addRow = useCallback(() => {
    setRows((rs) => [...rs, { key: Math.max(0, ...rs.map((r) => r.key)) + 1, product_id: "", qty: "1", price: "" }]);
  }, []);

  const removeRow = useCallback((key: number) => {
    setRows((rs) =>
      rs.length <= 1
        ? [{ key: 1, product_id: "", qty: "1", price: "" }]
        : rs.filter((r) => r.key !== key),
    );
  }, []);

  const save = useCallback(async () => {
    if (!budget) return;
    const parsed = budgetItemsSchema.safeParse({
      mode,
      margin_pct: margin === "" ? "" : Number(margin),
      items: rows.map((r) => ({
        product_id: r.product_id,
        qty: r.qty === "" ? 0 : Number(r.qty),
        price_override: mode === "manual" && r.price !== "" ? pesosToCents(r.price) : "",
      })),
    });
    if (!parsed.success) {
      const errs: Record<string, string> = {};
      for (const issue of parsed.error.issues) {
        const path = issue.path;
        if (path[0] === "items" && typeof path[1] === "number") {
          const key = rows[path[1]]?.key ?? path[1];
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
      setFieldErrors(errs);
      return;
    }
    setFieldErrors({});
    setSaving(true);
    setSaveError(null);
    try {
      const items = parsed.data.items.map((it) => ({
        product_id: it.product_id,
        qty: it.qty,
        price_override: it.price_override === "" ? null : it.price_override,
      }));
      await budgetsService.update(budget.id, {
        calculation_mode: mode,
        margin_pct: mode === "cost_plus" ? (margin === "" ? null : margin) : undefined,
        items,
      });
      router.push(`/presupuestos/${budget.id}`);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "No se pudo guardar el presupuesto");
      setSaving(false);
    }
  }, [budget, mode, margin, rows, router]);

  if (loading) {
    return (
      <Stack gap={3} maxW="860px">
        <Skeleton h="32px" />
        <Skeleton h="96px" />
        <Skeleton h="200px" />
      </Stack>
    );
  }

  if (error || !budget) {
    return (
      <Alert.Root status="error" maxW="640px">
        <Alert.Content>
          <Alert.Title>No se pudo cargar el presupuesto</Alert.Title>
          <Alert.Description>{error ?? "Presupuesto no encontrado"}</Alert.Description>
        </Alert.Content>
      </Alert.Root>
    );
  }

  return (
    <VStack align="stretch" gap={5} maxW="860px" w="full">
      <Flex align="center" justify="space-between" gap={3} flexWrap="wrap">
        <Heading as="h1" fontSize="2xl" textWrap="balance">Editar presupuesto #{budget.seq}</Heading>
        <Button variant="ghost" asChild>
          <NextLink href={`/presupuestos/${budget.id}`}>Cancelar</NextLink>
        </Button>
      </Flex>

      {budget.status === "enviado" ? (
        <Alert.Root status="warning" fontSize="sm">
          <Alert.Description>
            Este presupuesto ya fue enviado. Tras guardar los cambios hay que
            reenviarlo desde el detalle.
          </Alert.Description>
        </Alert.Root>
      ) : null}

      <Alert.Root status="info" fontSize="sm">
        <Alert.Description>
          Al guardar, los costos y precios de motor se re-derivan contra el
          catálogo actual. Los precios manuales se conservan.
        </Alert.Description>
      </Alert.Root>

      {saveError ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Description>{saveError}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      <Box borderWidth="1px" borderColor="border" rounded="md" p={5}>
        <Stack gap={4}>
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
                  variant={mode === m ? "solid" : "outline"}
                  colorPalette={mode === m ? "brand" : undefined}
                  aria-pressed={mode === m}
                  onClick={() => setMode(m)}
                >
                  {CALCULATION_MODE_LABELS[m]}
                </Button>
              ))}
            </HStack>
            {fieldErrors.mode ? (
              <Text color="red.fg" fontSize="xs" mt={1}>
                {fieldErrors.mode}
              </Text>
            ) : null}
          </Box>

          {mode === "cost_plus" ? (
            <Field.Root w="100%" maxW="240px">
              <Field.Label>Margen (%)</Field.Label>
              <Input
                type="number"
                name="margin_pct"
                inputMode="decimal"
                autoComplete="off"
                min={0}
                max={200}
                value={margin}
                onChange={(e) => setMargin(e.target.value)}
                placeholder="Margen del negocio…"
                aria-label="Margen por ciento"
              />
              <Field.HelperText>Vacío = margen del negocio.</Field.HelperText>
              {fieldErrors.margin_pct ? (
                <Field.ErrorText>{fieldErrors.margin_pct}</Field.ErrorText>
              ) : null}
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
                {rows.map((row, idx) => (
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
                      {fieldErrors[String(row.key)] ? (
                        <Field.ErrorText>{fieldErrors[String(row.key)]}</Field.ErrorText>
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
                    {mode === "manual" ? (
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
                        {fieldErrors[`${row.key}-price_override`] ? (
                          <Field.ErrorText>{fieldErrors[`${row.key}-price_override`]}</Field.ErrorText>
                        ) : null}
                      </Field.Root>
                    ) : null}
                    <Button
                      variant="ghost"
                      colorPalette="red"
                      aria-label={`Quitar línea ${idx + 1}`}
                      onClick={() => removeRow(row.key)}
                      disabled={rows.length <= 1}
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

          <HStack justify="flex-end" gap={3} pt={1}>
            <Button variant="ghost" asChild>
              <NextLink href={`/presupuestos/${budget.id}`}>Cancelar</NextLink>
            </Button>
            <Button colorPalette="brand" onClick={() => void save()} loading={saving}>
              Guardar cambios
            </Button>
          </HStack>
        </Stack>
      </Box>

      {}
      {priceByProduct.size > 0 ? (
        <Text fontSize="xs" color="fg.muted" maxW="860px">
          Precios del catálogo usados para el recálculo:{" "}
          {products
            .filter((p) => priceByProduct.get(p.id) != null)
            .slice(0, 6)
            .map((p) => `${p.name} ${formatCents(priceByProduct.get(p.id)!)}`)
            .join(" · ")}
        </Text>
      ) : null}
    </VStack>
  );
}
