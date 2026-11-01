"use client";

import { useCallback, useEffect, useState } from "react";
import { productsService } from "../service";
import type { ProductDetail } from "../types";

export interface UseProductDetailResult {
  product: ProductDetail | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * Detalle de producto (Fase 5, P4): carga la vista completa (receta con
 * costo por línea + desglose del motor o missing_ingredients).
 *
 * El precio no se cachea ni se recalcula en el cliente: el backend lo deriva
 * con los insumos y settings actuales en cada lectura (RF-P3-04). `reload` se
 * usa después de borrar o de volver de la edición.
 */
export function useProductDetail(productId: string): UseProductDetailResult {
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await productsService.getDetail(productId);
        if (cancelled) return;
        setProduct(data);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "No se pudo cargar el producto");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [productId, reloadToken]);

  const reload = useCallback(() => {
    setLoading(true);
    setReloadToken((token) => token + 1);
  }, []);

  return { product, loading, error, reload };
}
