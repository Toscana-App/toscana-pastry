import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useForm } from "react-hook-form";
import type { ProductFormValues } from "../schema";
import { PRODUCT_CREATE_DEFAULTS, useProductDraft } from "./useProductDraft";

const KEY = "product-draft:new";

function setup(isEdit = false, draftKey = KEY) {
  return renderHook(() => {
    const form = useForm<ProductFormValues>({
      defaultValues: PRODUCT_CREATE_DEFAULTS,
    });
    const draft = useProductDraft({
      draftKey,
      isEdit,
      isDirty: form.formState.isDirty,
      reset: form.reset,
      watch: form.watch,
    });
    return { form, draft };
  });
}

beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useProductDraft", () => {
  it("restores a partial draft (blank fields, prep 0, empty recipe) over the defaults", () => {
    sessionStorage.setItem(KEY, JSON.stringify({ name: "Torta", prep_time_min: 0 }));
    const { result } = setup();

    expect(result.current.draft.draftRestored).toBe(true);
    expect(result.current.form.getValues()).toEqual({
      ...PRODUCT_CREATE_DEFAULTS,
      name: "Torta",
    });
  });

  it("ignores a corrupt or wrongly-typed draft", () => {
    sessionStorage.setItem(KEY, "{not json");
    expect(setup().result.current.draft.draftRestored).toBe(false);

    sessionStorage.setItem(KEY, JSON.stringify({ servings: "muchas" }));
    const { result } = setup();
    expect(result.current.draft.draftRestored).toBe(false);
    expect(result.current.form.getValues()).toEqual(PRODUCT_CREATE_DEFAULTS);
  });

  it("saves the draft (debounced) once the form is dirty in create mode", () => {
    vi.useFakeTimers();
    const { result } = setup();

    act(() => {
      result.current.form.setValue("name", "Brown", { shouldDirty: true });
    });
    act(() => {
      result.current.form.setValue("name", "Brownie", { shouldDirty: true });
    });
    expect(sessionStorage.getItem(KEY)).toBeNull();
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(JSON.parse(sessionStorage.getItem(KEY) as string)).toMatchObject({
      name: "Brownie",
    });
  });

  it("never reads nor writes a draft in edit mode", () => {
    vi.useFakeTimers();
    const editKey = "product-draft:abc";
    sessionStorage.setItem(editKey, JSON.stringify({ name: "Viejo" }));
    const { result } = setup(true, editKey);

    expect(result.current.draft.draftRestored).toBe(false);
    act(() => {
      result.current.form.setValue("name", "Nuevo", { shouldDirty: true });
      vi.advanceTimersByTime(1000);
    });
    expect(JSON.parse(sessionStorage.getItem(editKey) as string)).toEqual({
      name: "Viejo",
    });
  });

  it("discardDraft clears storage, resets the form and hides the banner", () => {
    sessionStorage.setItem(KEY, JSON.stringify({ name: "Torta" }));
    const { result } = setup();

    act(() => result.current.draft.discardDraft());

    expect(sessionStorage.getItem(KEY)).toBeNull();
    expect(result.current.draft.draftRestored).toBe(false);
    expect(result.current.form.getValues()).toEqual(PRODUCT_CREATE_DEFAULTS);
  });

  it("clearDraft removes the stored draft", () => {
    sessionStorage.setItem(KEY, JSON.stringify({ name: "Torta" }));
    const { result } = setup();

    act(() => result.current.draft.clearDraft());
    expect(sessionStorage.getItem(KEY)).toBeNull();
  });
});
