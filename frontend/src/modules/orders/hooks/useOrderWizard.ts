"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useDebounce } from "@/modules/shared/useDebounce";
import { useAuth } from "@/contexts/AuthContext";
import { productsService } from "@/modules/products/service";
import type { ProductListItem } from "@/modules/products/types";
import {
  customersService,
  insufficientStockOf,
  ordersService,
} from "../service";
import { newCustomerSchema, orderCreateSchema } from "../schema";
import type {
  Customer,
  InsufficientStockResponse,
  OrderCreatePayload,
  OrderDetail,
  OrderPreviewResponse,
} from "../types";

export interface WizardItem {
  key: number;
  product_id: string;
  qty: string;
  portions: string; // vacío = porciones del producto
  note: string;
}

export interface PreviewState {
  status: "idle" | "loading" | "done" | "error";
  data?: OrderPreviewResponse;
  error?: string;
}

// Fecha local (no UTC): evita que de noche el default sea el día siguiente.
const todayIso = () => new Date().toLocaleDateString("sv-SE");

/**
 * Estado, fetching, efectos y submit del wizard de pedidos (UC-02/UC-04).
 * El componente OrderWizard es solo presentacional.
 */
export function useOrderWizard(orderId?: string) {
  const router = useRouter();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [customerId, setCustomerId] = useState("");
  const [customerMode, setCustomerMode] = useState<"existing" | "new">("existing");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerQuery] = useState("");
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [date, setDate] = useState(todayIso());
  const [margin, setMargin] = useState("");
  const [items, setItems] = useState<WizardItem[]>([
    { key: 1, product_id: "", qty: "1", portions: "", note: "" },
  ]);
  const [nextKey, setNextKey] = useState(2);
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [preview, setPreview] = useState<PreviewState>({ status: "idle" });
  const [stockError, setStockError] = useState<InsufficientStockResponse | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(!!orderId);
  const [detail, setDetail] = useState<OrderDetail | null>(null);

  const debouncedCustomerQuery = useDebounce(customerQuery, 250);

  // En edición el cliente actual puede quedar fuera de los primeros 50 resultados.
  const customerOptions = useMemo(() => {
    const list = customers.map((c) => ({ value: c.id, label: `${c.name} · ${c.phone}` }));
    const current = detail?.customer;
    if (current && !list.some((o) => o.value === current.id)) {
      list.unshift({ value: current.id, label: current.name });
    }
    return list;
  }, [customers, detail]);
  const previewSeq = useRef(0);

  // Catálogo para el picker de líneas.
  useEffect(() => {
    let cancelled = false;
    productsService
      .list({ page: 1, page_size: 100 })
      .then((res) => {
        if (!cancelled) setProducts(res.items);
      })
      .catch(() => {
        /* sin catálogo: el wizard muestra el select vacío */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Clientes para el selector (búsqueda con debounce).
  useEffect(() => {
    let cancelled = false;
    customersService
      .list(debouncedCustomerQuery.trim() || undefined, 1, 50)
      .then((res) => {
        if (!cancelled) setCustomers(res.items);
      })
      .catch(() => {
        /* la UI se queda con lo último */
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedCustomerQuery]);

  // Modo edición: precarga el pedido (solo estado nuevo lo permite).
  useEffect(() => {
    if (!orderId) return;
    let cancelled = false;
    ordersService
      .getDetail(orderId)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
        setCustomerId(d.customer.id);
        setDate(d.date);
        setMargin(d.margin_pct == null ? "" : String(d.margin_pct));
        setItems(
          d.items.map((item, idx) => ({
            key: idx + 1,
            product_id: item.product_id,
            qty: String(item.qty),
            portions: String(item.portions),
            note: item.note,
          })),
        );
        setNextKey(d.items.length + 1);
        setLoadingDetail(false);
      })
      .catch((e) => {
        if (!cancelled) {
          setSubmitError(e instanceof Error ? e.message : "No se pudo cargar el pedido");
          setLoadingDetail(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [orderId]);

  // Preview en vivo (UC-02): 500 ms de quietud y al menos una línea completa.
  const previewItems = useMemo(
    () =>
      items
        .filter((i) => i.product_id !== "" && /^\d+$/.test(i.qty))
        .map((i) => ({
          product_id: i.product_id,
          qty: Number(i.qty),
          portions: i.portions === "" ? null : Number(i.portions),
          note: i.note,
        })),
    [items],
  );

  useEffect(() => {
    // React Compiler: nada de setState síncrono en el cuerpo del efecto.
    // El reset y el "loading" entran por un timer (borde async).
    if (!isAdmin || previewItems.length === 0) {
      const reset = setTimeout(() => setPreview({ status: "idle" }), 0);
      return () => clearTimeout(reset);
    }
    const seq = ++previewSeq.current;
    const timer = setTimeout(() => {
      setPreview((p) => ({ ...p, status: "loading" }));
      const marginPct = margin === "" ? null : margin;
      ordersService
        .preview(previewItems, marginPct)
        .then((data) => {
          if (seq !== previewSeq.current) return;
          setPreview({ status: "done", data });
        })
        .catch((e) => {
          if (seq !== previewSeq.current) return;
          setPreview({
            status: "error",
            error: e instanceof Error ? e.message : "No se pudo cotizar",
          });
        });
    }, 500);
    return () => clearTimeout(timer);
  }, [isAdmin, previewItems, margin]);

  const updateItem = useCallback((key: number, patch: Partial<WizardItem>) => {
    setItems((prev) => prev.map((i) => (i.key === key ? { ...i, ...patch } : i)));
    setStockError(null);
  }, []);

  const addItem = useCallback(() => {
    setItems((prev) => [
      ...prev,
      { key: nextKey, product_id: "", qty: "1", portions: "", note: "" },
    ]);
    setNextKey((k) => k + 1);
  }, [nextKey]);

  const removeItem = useCallback((key: number) => {
    setItems((prev) => (prev.length > 1 ? prev.filter((i) => i.key !== key) : prev));
  }, []);

  const submit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    setStockError(null);
    try {
      // Cliente: alta inline resuelta antes de mandar el payload.
      let resolvedCustomerId = customerId;
      if (customerMode === "new") {
        const parsed = newCustomerSchema.safeParse({ name: newName, phone: newPhone });
        if (!parsed.success) {
          setSubmitError(parsed.error.issues[0]?.message ?? "Cliente inválido");
          return;
        }
        const created = await customersService.create(parsed.data);
        resolvedCustomerId = created.id;
      }

      const payload: OrderCreatePayload = {
        customer_id: resolvedCustomerId,
        date,
        margin_pct: margin === "" ? null : margin,
        items: items.map((i) => ({
          product_id: i.product_id,
          qty: Number(i.qty),
          portions: i.portions === "" ? null : Number(i.portions),
          note: i.note,
        })),
      };

      const validated = orderCreateSchema.safeParse(payload);
      if (!validated.success) {
        setSubmitError(validated.error.issues[0]?.message ?? "Revisá el pedido");
        return;
      }

      if (orderId) {
        await ordersService.update(orderId, payload);
        router.push(`/pedidos/${orderId}`);
      } else {
        const created = await ordersService.create(payload);
        router.push(`/pedidos/${created.id}`);
      }
    } catch (e) {
      const stock = insufficientStockOf(e);
      if (stock) {
        setStockError(stock);
      } else {
        setSubmitError(e instanceof Error ? e.message : "No se pudo guardar el pedido");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return {
    isAdmin,
    customerId,
    setCustomerId,
    customerMode,
    setCustomerMode,
    customerQuery,
    newName,
    setNewName,
    newPhone,
    setNewPhone,
    date,
    setDate,
    margin,
    setMargin,
    items,
    products,
    customerOptions,
    preview,
    stockError,
    submitError,
    submitting,
    loadingDetail,
    updateItem,
    addItem,
    removeItem,
    submit,
  };
}
