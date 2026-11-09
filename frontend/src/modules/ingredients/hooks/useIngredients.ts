"use client";

import { useCallback, useEffect, useState } from "react";
import { useDebounce } from "@/modules/shared/useDebounce";
import { ingredientsService } from "../service";
import type { Ingredient, IngredientListParams } from "../types";

const PAGE_SIZE = 50;

export interface UseIngredientsResult {
  items: Ingredient[];
  total: number;
  page: number;
  query: string;
  loading: boolean;
  error: string | null;
  setQuery: (q: string) => void;
  goToPage: (page: number) => void;
  reload: () => void;
}

export function useIngredients(): UseIngredientsResult {
  const [query, setQueryState] = useState("");
  const [page, setPage] = useState(1);
  const [reloadToken, setReloadToken] = useState(0);
  const [items, setItems] = useState<Ingredient[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const debouncedQuery = useDebounce(query, 250);
  const searchTerm = debouncedQuery.trim();

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const params: IngredientListParams = {
        q: searchTerm || undefined,
        page,
        page_size: PAGE_SIZE,
      };
      try {
        const data = await ingredientsService.list(params);
        if (cancelled) return;
        setItems(data.items);
        setTotal(data.total);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "No se pudo cargar la lista");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [searchTerm, page, reloadToken]);

  const setQuery = useCallback((q: string) => {
    setQueryState(q);
    setPage(1);
    setLoading(true);
  }, []);

  const goToPage = useCallback((p: number) => {
    setPage(p);
    setLoading(true);
  }, []);

  const reload = useCallback(() => {
    setLoading(true);
    setReloadToken((token) => token + 1);
  }, []);

  return { items, total, page, query, loading, error, setQuery, goToPage, reload };
}
