"use client";

import { useCallback, useEffect, useState } from "react";
import { useDebounce } from "@/modules/shared/useDebounce";
import { productsService } from "../service";
import type { ProductListItem, ProductListParams } from "../types";

/** RF-P3-01: paginación de 20 por página. */
const PAGE_SIZE = 20;

export interface UseProductsResult {
  items: ProductListItem[];
  total: number;
  page: number;
  query: string;
  /** null = "Todas" (sin filtro). */
  category: string | null;
  /** Categorías derivadas de los productos activos (chips del P3). */
  categories: string[];
  loading: boolean;
  error: string | null;
  setQuery: (q: string) => void;
  setCategory: (category: string | null) => void;
  goToPage: (page: number) => void;
  reload: () => void;
}

/**
 * Estado del listado de productos (Fase 5, P3).
 *
 * - Búsqueda con debounce de 250 ms (RF-P3-03), combinable con el filtro de
 *   categoría (RF-P3-02): cualquier cambio vuelve a la página 1.
 * - Paginación server-side (page_size = 20, RF-P3-01).
 * - `categories` viene del backend en cada respuesta (derivadas de los
 *   productos activos, no de la página): los chips no desaparecen al filtrar.
 */
export function useProducts(): UseProductsResult {
  const [query, setQueryState] = useState("");
  const [category, setCategoryState] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [reloadToken, setReloadToken] = useState(0);
  const [items, setItems] = useState<ProductListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const debouncedQuery = useDebounce(query, 250);
  const searchTerm = debouncedQuery.trim();

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const params: ProductListParams = {
        q: searchTerm || undefined,
        category: category ?? undefined,
        page,
        page_size: PAGE_SIZE,
      };
      try {
        const data = await productsService.list(params);
        if (cancelled) return;
        setItems(data.items);
        setTotal(data.total);
        setCategories(data.categories);
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
  }, [searchTerm, category, page, reloadToken]);

  const setQuery = useCallback((q: string) => {
    setQueryState(q);
    setPage(1);
    setLoading(true);
  }, []);

  const setCategory = useCallback((next: string | null) => {
    setCategoryState(next);
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

  return {
    items,
    total,
    page,
    query,
    category,
    categories,
    loading,
    error,
    setQuery,
    setCategory,
    goToPage,
    reload,
  };
}
