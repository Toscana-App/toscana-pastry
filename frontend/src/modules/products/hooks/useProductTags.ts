"use client";

import { useEffect, useState } from "react";
import { productsService } from "../service";
import type { ProductTagCount } from "../types";

export function useProductTags(reloadToken = 0): ProductTagCount[] {
  const [tags, setTags] = useState<ProductTagCount[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await productsService.listTags();
        if (!cancelled) setTags(data.tags);
      } catch {
        if (!cancelled) setTags([]);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  return tags;
}
