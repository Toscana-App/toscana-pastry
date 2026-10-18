"use client";

import { useCallback, useEffect, useState } from "react";
import { useDebounce } from "@/modules/shared/useDebounce";
import { ordersService } from "../service";
import type { OrderListItem, OrderStatus } from "../types";

/** RF-P6-05: paginación de 20 por página (mismo page_size del backend). */
const PAGE_SIZE = 20;

export interface UseOrdersResult {
  items: OrderListItem[];
  total: number;
  page: number;
  query: string;
  status: OrderStatus | null;
  dateFrom: string;
  dateTo: string;
  loading: boolean;
  error: string | null;
  setQuery: (q: string) => void;
  setStatus: (status: OrderStatus | null) => void;
  setDateFrom: (date: string) => void;
  setDateTo: (date: string) => void;
  goToPage: (page: number) => void;
  reload: () => void;
}

/**
 * Estado del listado de pedidos (Fase 6, UC-01 / RF-P6-05).
 *
 * - Filtros combinables: búsqueda (debounce 250 ms), estado y rango de
 *   fechas; cualquier cambio vuelve a la página 1.
 * - Paginación server-side (page_size = 20).
 */
export function useOrders(): UseOrdersResult {
  const [query, setQueryState] = useState("");
  const [status, setStatusState] = useState<OrderStatus | null>(null);
  const [dateFrom, setDateFromState] = useState("");
  const [dateTo, setDateToState] = useState("");
  const [page, setPage] = useState(1);
  const [reloadToken, setReloadToken] = useState(0);
  const [items, setItems] = useState<OrderListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const debouncedQuery = useDebounce(query, 250);
  const searchTerm = debouncedQuery.trim();

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await ordersService.list({
          q: searchTerm || undefined,
          status: status ?? undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          page,
          page_size: PAGE_SIZE,
        });
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
  }, [searchTerm, status, dateFrom, dateTo, page, reloadToken]);

  const setQuery = useCallback((q: string) => {
    setQueryState(q);
    setPage(1);
    setLoading(true);
  }, []);

  const setStatus = useCallback((next: OrderStatus | null) => {
    setStatusState(next);
    setPage(1);
    setLoading(true);
  }, []);

  const setDateFrom = useCallback((date: string) => {
    setDateFromState(date);
    setPage(1);
    setLoading(true);
  }, []);

  const setDateTo = useCallback((date: string) => {
    setDateToState(date);
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
    status,
    dateFrom,
    dateTo,
    loading,
    error,
    setQuery,
    setStatus,
    setDateFrom,
    setDateTo,
    goToPage,
    reload,
  };
}
