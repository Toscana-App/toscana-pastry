"use client";

import { useEffect, useMemo, useState } from "react";
import type { Ingredient } from "@/modules/ingredients/types";
import type { ProductFormValues } from "../schema";
import { productsService } from "../service";
import type { PreviewLineItem, PriceBreakdown } from "../types";

const PREVIEW_DEBOUNCE_MS = 300;

export interface UseCostPreviewResult {
  breakdown: PriceBreakdown | null;
  error: string | null;
  loading: boolean;
}

export function useCostPreview(
  recipe: ProductFormValues["recipe"] | undefined,
  prepMinutes: number,
  ingredientById: Map<string, Ingredient>,
): UseCostPreviewResult {
  const [breakdown, setBreakdown] = useState<PriceBreakdown | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const lines = useMemo(() => {
    const out: PreviewLineItem[] = [];
    for (const row of recipe ?? []) {
      const ingredient = ingredientById.get(row.ingredient_id);
      if (!ingredient) continue;
      if (!Number.isFinite(row.qty) || row.qty <= 0) continue;
      out.push({
        qty: row.qty,
        unit: row.unit,
        price_per_purchase_unit: ingredient.price_per_unit,
        purchase_unit: ingredient.unit,
      });
    }
    return out;
  }, [recipe, ingredientById]);

  useEffect(() => {
    if (lines.length === 0) return;

    const prep = Number.isFinite(prepMinutes)
      ? Math.min(Math.max(prepMinutes, 0), 1440)
      : 0;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);

    const timer = setTimeout(async () => {
      try {
        const result = await productsService.preview(lines, prep);
        if (cancelled) return;
        setBreakdown(result);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setBreakdown(null);
        setError(
          e instanceof Error ? e.message : "No se pudo calcular el costo",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, PREVIEW_DEBOUNCE_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [lines, prepMinutes]);

  if (lines.length === 0) return { breakdown: null, error: null, loading: false };
  return { breakdown, error, loading };
}
