"use client";

import { useEffect, useState } from "react";
import { productsService } from "../service";
import type { ProductCategoryCount } from "../types";

export function useProductCategories(
  reloadToken = 0,
): ProductCategoryCount[] {
  const [categories, setCategories] = useState<ProductCategoryCount[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await productsService.listCategories();
        if (!cancelled) setCategories(data.categories);
      } catch {
        if (!cancelled) setCategories([]);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  return categories;
}
