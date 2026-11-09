"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { ingredientsService } from "../service";
import type { DeleteImpact, Ingredient, StockMovement, StockReason } from "../types";
import { statusOf } from "../types";

export interface AdjustStockResult {
  ok: boolean;
  message?: string;
}

export interface UseIngredientDetailResult {
  ingredient: Ingredient | null;
  movements: StockMovement[];
  loading: boolean;
  error: string | null;
  reload: () => void;
  adjustStock: (delta: number, reason: StockReason, ref?: string) => Promise<AdjustStockResult>;
  remove: () => Promise<"deleted" | DeleteImpact>;
}

export function useIngredientDetail(id: string): UseIngredientDetailResult {
  const [ingredient, setIngredient] = useState<Ingredient | null>(null);
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await ingredientsService.getDetail(id, true);
        if (cancelled) return;
        setIngredient(data.ingredient);
        setMovements(data.movements ?? []);
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof Error ? e.message : "No se pudo cargar el ingrediente",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey]);

  const adjustStock = useCallback(
    async (delta: number, reason: StockReason, ref?: string): Promise<AdjustStockResult> => {
      setIngredient((current) => {
        if (!current) return current;
        return {
          ...current,
          stock_qty: String(Number(current.stock_qty) + delta),
          status: statusOf(Number(current.stock_qty) + delta, current.low_stock_threshold),
        };
      });

      try {
        const result = await ingredientsService.adjustStock(id, {
          delta,
          reason,
          ...(ref ? { ref } : {}),
        });
        setIngredient((current) =>
          current
            ? {
                ...current,
                stock_qty: result.stock_qty,
                status: statusOf(result.stock_qty, current.low_stock_threshold),
              }
            : current,
        );
        setMovements((current) => [result.movement, ...current]);
        return { ok: true };
      } catch (e) {
        setIngredient((current) => {
          if (!current) return current;
          const reverted = Number(current.stock_qty) - delta;
          return {
            ...current,
            stock_qty: String(reverted),
            status: statusOf(reverted, current.low_stock_threshold),
          };
        });
        return {
          ok: false,
          message: e instanceof Error ? e.message : "No se pudo ajustar el stock",
        };
      }
    },
    [id],
  );

  const remove = useCallback(async (): Promise<"deleted" | DeleteImpact> => {
    try {
      await ingredientsService.remove(id);
      return "deleted";
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const payload = e.payload as { impacted_recipes?: number } | null;
        return { impacted_recipes: payload?.impacted_recipes ?? 0 };
      }
      throw e;
    }
  }, [id]);

  return { ingredient, movements, loading, error, reload, adjustStock, remove };
}
