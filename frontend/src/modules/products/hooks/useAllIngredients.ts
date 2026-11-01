"use client";

import { useEffect, useState } from "react";
import { ingredientsService } from "@/modules/ingredients/service";
import type { Ingredient } from "@/modules/ingredients/types";

export interface UseAllIngredientsResult {
  ingredients: Ingredient[];
  loading: boolean;
  error: string | null;
}

/** Carga el catálogo completo de insumos (todas las páginas) para el editor de receta. */
export function useAllIngredients(): UseAllIngredientsResult {
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
          setError("No se pudieron cargar los insumos del catálogo.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { ingredients, loading, error };
}
