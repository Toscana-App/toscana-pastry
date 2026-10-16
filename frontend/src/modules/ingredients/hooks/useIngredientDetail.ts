"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { ingredientsService } from "../service";
import type { DeleteImpact, Ingredient, StockMovement, StockReason } from "../types";
import { statusOf } from "../types";

export interface AdjustStockResult {
  ok: boolean;
  /** Mensaje del backend cuando falla (400: stock insuficiente, etc.). */
  message?: string;
}

export interface UseIngredientDetailResult {
  ingredient: Ingredient | null;
  movements: StockMovement[];
  loading: boolean;
  error: string | null;
  reload: () => void;
  /**
   * Ajuste de stock optimista (RF-P2-03): la UI se mueve al instante y se
   * revierte si el servidor rechaza (400 stock insuficiente / 404).
   */
  adjustStock: (delta: number, reason: StockReason, ref?: string) => Promise<AdjustStockResult>;
  /**
   * Intenta eliminar. Devuelve "deleted" si salió bien; si el backend responde
   * 409, devuelve el impacto ({impacted_recipes}) para que la UI lo explique.
   */
  remove: () => Promise<"deleted" | DeleteImpact>;
}

/**
 * Estado del detalle de un ingrediente (Fase 4, WU6).
 *
 * Trae el ingrediente junto con su historial de movimientos
 * (include_movements=true) en una sola request.
 */
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
      let previous: Ingredient | null = null;
      setIngredient((current) => {
        previous = current;
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
        // Rollback: el estado autoritativo es el del servidor.
        if (previous) setIngredient(previous);
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
