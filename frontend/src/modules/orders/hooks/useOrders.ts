"use client";

import { useCallback, useEffect, useState } from "react";
import { useDebounce } from "@/modules/shared/useDebounce";
import { ordersService } from "../service";
import type { OrderListItem, OrderStatus } from "../types";

const PAGE_SIZE = 20;

export interface UseOrdersResult {
  items: OrderListItem[];
  total: number;
  unpaidCount: number;
  page: number;
  query: string;
  status: OrderStatus | null;
  paid: boolean | null;
  dateFrom: string;
  dateTo: string;
  loading: boolean;
  error: string | null;
  setQuery: (q: string) => void;
  setStatus: (status: OrderStatus | null) => void;
  setPaid: (paid: boolean | null) => void;
  setDateFrom: (date: string) => void;
  setDateTo: (date: string) => void;
  goToPage: (page: number) => void;
  reload: () => void;
}

export function useOrders(): UseOrdersResult {
  const [query, setQueryState] = useState("");
  const [status, setStatusState] = useState<OrderStatus | null>(null);
  const [paid, setPaidState] = useState<boolean | null>(null);
  const [dateFrom, setDateFromState] = useState("");
  const [dateTo, setDateToState] = useState("");
  const [page, setPage] = useState(1);
  const [reloadToken, setReloadToken] = useState(0);
  const [items, setItems] = useState<OrderListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [unpaidCount, setUnpaidCount] = useState(0);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const debouncedQuery = useDebounce(query, 250);
  const searchTerm = debouncedQuery.trim();
  const requestKey = JSON.stringify([searchTerm, status, paid, dateFrom, dateTo, page, reloadToken]);
  const loading = loadedKey !== requestKey;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await ordersService.list({
          q: searchTerm || undefined,
          status: status ?? undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          paid: paid ?? undefined,
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
        if (!cancelled) setLoadedKey(requestKey);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [searchTerm, status, paid, dateFrom, dateTo, page, reloadToken, requestKey]);

  useEffect(() => {
    let cancelled = false;

    async function loadCount() {
      try {
        const data = await ordersService.list({
          q: searchTerm || undefined,
          status: status ?? undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          paid: false,
          page: 1,
          page_size: 1,
        });
        if (!cancelled) setUnpaidCount(data.total);
      } catch {
      }
    }

    loadCount();
    return () => {
      cancelled = true;
    };
  }, [searchTerm, status, dateFrom, dateTo, reloadToken]);

  const setQuery = useCallback((q: string) => {
    setQueryState(q);
    setPage(1);
  }, []);

  const setStatus = useCallback((next: OrderStatus | null) => {
    setStatusState(next);
    setPage(1);
  }, []);

  const setPaid = useCallback((next: boolean | null) => {
    setPaidState(next);
    setPage(1);
  }, []);

  const setDateFrom = useCallback((date: string) => {
    setDateFromState(date);
    setPage(1);
  }, []);

  const setDateTo = useCallback((date: string) => {
    setDateToState(date);
    setPage(1);
  }, []);

  const goToPage = useCallback((p: number) => {
    setPage(p);
  }, []);

  const reload = useCallback(() => {
    setReloadToken((token) => token + 1);
  }, []);

  return {
    items,
    total,
    unpaidCount,
    page,
    query,
    status,
    paid,
    dateFrom,
    dateTo,
    loading,
    error,
    setQuery,
    setStatus,
    setPaid,
    setDateFrom,
    setDateTo,
    goToPage,
    reload,
  };
}
