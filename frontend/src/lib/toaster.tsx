"use client";

import { gooeyToast } from "goey-toast";

type ToastType = "success" | "error" | "warning" | "info";

export interface ToastAction {
  label: string;
  onClick: () => void;
  successLabel?: string;
}

export interface ToastOptions {
  title: string;
  description?: string | null;
  type?: ToastType;
  action?: ToastAction;
}

/**
 * Compat layer: call sites use the old Chakra `toaster.create(...)` shape;
 * toasts now render through goey-toast (GooeyToaster mounted in layout).
 */
function show(type: ToastType, title: string, description?: string, action?: ToastAction): void {
  const options = {
    ...(description ? { description } : {}),
    ...(action ? { action } : {}),
  };
  const withOptions = description !== undefined || action !== undefined;
  const fn =
    type === "success"
      ? gooeyToast.success
      : type === "error"
        ? gooeyToast.error
        : type === "warning"
          ? gooeyToast.warning
          : gooeyToast.info;
  if (withOptions) {
    fn(title, options);
  } else {
    fn(title);
  }
}

export const toaster = {
  create(options: ToastOptions): void {
    const { title, description, type = "info", action } = options;
    show(type, title, description ?? undefined, action);
  },
};
