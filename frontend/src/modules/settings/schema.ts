import { z } from "zod";
import { DIFFICULTIES } from "./types";

/**
 * Esquema zod de la configuración del negocio (Fase 4, WU7).
 *
 * Rangos y dependencias espejo de `SettingsUpdate` (RF-P5-01, RF-P5-06): el
 * usuario ve el error antes de mandar el PUT, y el backend sigue siendo la
 * última línea (422 / 400).
 */
export const settingsSchema = z
  .object({
    hourly_rate: z
      .number({ message: "Ingresá un valor por hora" })
      .min(0.01, "Mínimo 0,01")
      .max(100_000, "Máximo 100.000"),
    margin_pct: z
      .number({ message: "Ingresá un margen" })
      .min(0, "Mínimo 0")
      .max(100, "Máximo 100"),
    round_step: z
      .number({ message: "Ingresá un paso de redondeo" })
      .min(0.01, "Mínimo 0,01")
      .max(1000, "Máximo 1.000"),
    include_labor: z.boolean(),
    include_gas: z.boolean(),
    gas_pct: z
      .number({ message: "Ingresá un porcentaje" })
      .min(0, "Mínimo 0")
      .max(100, "Máximo 100"),
    include_waste: z.boolean(),
    waste_pct: z
      .number({ message: "Ingresá un porcentaje" })
      .min(0, "Mínimo 0")
      .max(100, "Máximo 100"),
    urgent_surcharge_pct: z
      .number({ message: "Ingresá un porcentaje" })
      .min(0, "Mínimo 0")
      .max(100, "Máximo 100"),
    consumer_markup_pct: z
      .number({ message: "Ingresá un markup" })
      .min(0, "Mínimo 0")
      .max(100, "Máximo 100"),
    default_prep_minutes: z
      .number({ message: "Ingresá los minutos" })
      .int("Tiene que ser un número entero")
      .min(0, "Mínimo 0")
      .max(1440, "Máximo 1440"),
    default_servings: z
      .number({ message: "Ingresá las porciones" })
      .int("Tiene que ser un número entero")
      .min(1, "Mínimo 1")
      .max(999, "Máximo 999"),
    default_difficulty: z.enum(DIFFICULTIES, { message: "Dificultad inválida" }),
  })
  .strict()
  .superRefine((value, ctx) => {
    // RF-P5-06: cada porcentaje exige su toggle encendido. El backend rechaza
    // el PUT si no se cumple; acá se explica antes de enviarlo.
    if (!value.include_gas && value.gas_pct !== 0) {
      ctx.addIssue({
        code: "custom",
        path: ["gas_pct"],
        message: "Poné 0 o activá el cargo por gas",
      });
    }
    if (!value.include_waste && value.waste_pct !== 0) {
      ctx.addIssue({
        code: "custom",
        path: ["waste_pct"],
        message: "Poné 0 o activá la merma",
      });
    }
  });

export type SettingsValues = z.infer<typeof settingsSchema>;
