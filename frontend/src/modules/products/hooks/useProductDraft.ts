"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { UseFormReset, UseFormWatch } from "react-hook-form";
import { productDraftSchema, type ProductFormValues } from "../schema";

const DRAFT_DEBOUNCE_MS = 500;

export const PRODUCT_CREATE_DEFAULTS: ProductFormValues = {
  name: "",
  category: "",
  description: "",
  prep_time_min: 0,
  servings: 1,
  difficulty: "simple",
  recipe: [],
  available: false,
};

interface UseProductDraftArgs {
  draftKey: string;
  isEdit: boolean;
  isDirty: boolean;
  reset: UseFormReset<ProductFormValues>;
  watch: UseFormWatch<ProductFormValues>;
}

export interface UseProductDraftResult {
  draftRestored: boolean;
  clearDraft: () => void;
  discardDraft: () => void;
}

export function useProductDraft({
  draftKey,
  isEdit,
  isDirty,
  reset,
  watch,
}: UseProductDraftArgs): UseProductDraftResult {
  const [draftRestored, setDraftRestored] = useState(false);
  const draftTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isDirtyRef = useRef(isDirty);
  useEffect(() => {
    isDirtyRef.current = isDirty;
  }, [isDirty]);

  useEffect(() => {
    if (isEdit) return;
    try {
      const raw = sessionStorage.getItem(draftKey);
      if (!raw) return;
      const parsed = productDraftSchema.safeParse(JSON.parse(raw));
      if (parsed.success) {
        reset({ ...PRODUCT_CREATE_DEFAULTS, ...parsed.data });
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setDraftRestored(true);
      }
    } catch {
    }
  }, [isEdit, draftKey, reset]);

  useEffect(() => {
    if (isEdit) return;
    const subscription = watch((values) => {
      if (!isDirtyRef.current) return;
      if (draftTimer.current) clearTimeout(draftTimer.current);
      draftTimer.current = setTimeout(() => {
        try {
          sessionStorage.setItem(draftKey, JSON.stringify(values));
        } catch {
        }
      }, DRAFT_DEBOUNCE_MS);
    });
    return () => {
      subscription.unsubscribe();
      if (draftTimer.current) clearTimeout(draftTimer.current);
    };
  }, [watch, draftKey, isEdit]);

  const clearDraft = useCallback(() => {
    sessionStorage.removeItem(draftKey);
  }, [draftKey]);

  const discardDraft = useCallback(() => {
    sessionStorage.removeItem(draftKey);
    reset(PRODUCT_CREATE_DEFAULTS);
    setDraftRestored(false);
  }, [draftKey, reset]);

  return { draftRestored, clearDraft, discardDraft };
}
