"use client";

import { useCallback, useEffect, useState } from "react";
import { useDebounce } from "@/modules/shared/useDebounce";
import { productsService } from "../service";
import type { ProductListItem, ProductListParams } from "../types";

const PAGE_SIZE = 20;

export interface UseProductsResult {
  items: ProductListItem[];
  total: number;
  page: number;
  query: string;
  category: string | null;
  tags: string[];
  loading: boolean;
  error: string | null;
  setQuery: (q: string) => void;
  setCategory: (category: string | null) => void;
  toggleTag: (tag: string) => void;
  goToPage: (page: number) => void;
  reload: () => void;
}

export function useProducts(): UseProductsResult {
  const [query, setQueryState] = useState("");
  const [category, setCategoryState] = useState<string | null>(null);
  const [tags, setTags] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [reloadToken, setReloadToken] = useState(0);
  const [items, setItems] = useState<ProductListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const debouncedQuery = useDebounce(query, 250);
  const searchTerm = debouncedQuery.trim();
  const tagKey = tags.join(",");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const params: ProductListParams = {
        q: searchTerm || undefined,
        category: category ?? undefined,
        tags: tags.length > 0 ? tags : undefined,
        page,
        page_size: PAGE_SIZE,
      };
      try {
        const data = await productsService.list(params);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm, category, tagKey, page, reloadToken]);

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

  const toggleTag = useCallback((tag: string) => {
    setTags((current: string[]) =>
      current.some((item: string) => item.toLowerCase() === tag.toLowerCase())
        ? current.filter(
            (item: string) => item.toLowerCase() !== tag.toLowerCase(),
          )
        : [...current, tag],
    );
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
    tags,
    loading,
    error,
    setQuery,
    setCategory,
    toggleTag,
    goToPage,
    reload,
  };
}
