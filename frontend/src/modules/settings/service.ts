import { apiFetch } from "@/lib/api";
import { pesosToCents } from "@/lib/format";
import type { BusinessSettings, OrderWindow, OrderWindowUpdate, SettingsFormValues } from "./types";

const BASE = "/tenant/settings";
const WINDOW_BASE = "/tenant/order-window";

export const settingsService = {
  get(): Promise<BusinessSettings> {
    return apiFetch<BusinessSettings>(BASE);
  },

  update(values: SettingsFormValues): Promise<BusinessSettings> {
    return apiFetch<BusinessSettings>(BASE, {
      method: "PUT",
      body: JSON.stringify({
        ...values,
        hourly_rate: pesosToCents(values.hourly_rate),
        round_step: pesosToCents(values.round_step),
        margin_pct: String(values.margin_pct),
        gas_pct: String(values.gas_pct),
        waste_pct: String(values.waste_pct),
        urgent_surcharge_pct: String(values.urgent_surcharge_pct),
        consumer_markup_pct: String(values.consumer_markup_pct),
      }),
    });
  },
};

export const orderWindowService = {
  get(): Promise<OrderWindow> {
    return apiFetch<OrderWindow>(WINDOW_BASE);
  },

  update(payload: OrderWindowUpdate): Promise<OrderWindow> {
    return apiFetch<OrderWindow>(WINDOW_BASE, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
};
