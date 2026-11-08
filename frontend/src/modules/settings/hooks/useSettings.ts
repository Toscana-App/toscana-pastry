"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { settingsService } from "../service";
import {
  SETTINGS_DEFAULTS,
  toFormValues,
  type SettingsFormValues,
} from "../types";

export type SettingsFieldErrors = Partial<Record<keyof SettingsFormValues, string>>;

export interface UseSettingsResult {
  settings: SettingsFormValues | null;
  loading: boolean;
  saving: boolean;
  error: string | null;
  fieldErrors: SettingsFieldErrors;
  save: (values: SettingsFormValues) => Promise<boolean>;
}

function parseFieldErrors(payload: unknown): SettingsFieldErrors {
  const detail = (payload as { detail?: unknown } | null)?.detail;
  if (!Array.isArray(detail)) return {};

  const errors: SettingsFieldErrors = {};
  for (const issue of detail) {
    const item = issue as { loc?: unknown[]; msg?: string };
    const field = Array.isArray(item.loc) ? String(item.loc[item.loc.length - 1]) : "";
    if (field && field in SETTINGS_DEFAULTS && item.msg) {
      errors[field as keyof SettingsFormValues] = item.msg;
    }
  }
  return errors;
}

export function useSettings(): UseSettingsResult {
  const [settings, setSettings] = useState<SettingsFormValues | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<SettingsFieldErrors>({});

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await settingsService.get();
        if (!cancelled) setSettings(toFormValues(data));
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof Error ? e.message : "No se pudo cargar la configuración",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const save = useCallback(async (values: SettingsFormValues): Promise<boolean> => {
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      const updated = await settingsService.update(values);
      setSettings(toFormValues(updated));
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        const parsed = parseFieldErrors(e.payload);
        setFieldErrors(parsed);
        if (Object.keys(parsed).length === 0) {
          setError("La configuración tiene valores inválidos.");
        }
      } else if (e instanceof ApiError && e.status === 403) {
        setError("Solo un administrador puede modificar la configuración.");
      } else {
        setError(e instanceof Error ? e.message : "No se pudo guardar");
      }
      return false;
    } finally {
      setSaving(false);
    }
  }, []);

  return { settings, loading, saving, error, fieldErrors, save };
}
