import { Badge } from "@chakra-ui/react";
import { formatQty } from "@/lib/format";
import type { IngredientStatus } from "../types";

/**
 * Badge de stock (Fase 4, RF-P2-04): color + texto según el status
 * computado por el servidor.
 *
 * OK (verde) "12 kg disponibles" · LOW (naranja) "2 kg restantes" ·
 * EMPTY (rojo) "Agotado".
 */
const STATUS_STYLE: Record<
  IngredientStatus,
  { palette: "green" | "orange" | "red"; label: (qty: string, unit: string) => string }
> = {
  OK: {
    palette: "green",
    label: (qty, unit) => `${formatQty(qty, unit)} disponibles`,
  },
  LOW: {
    palette: "orange",
    label: (qty, unit) => `${formatQty(qty, unit)} restantes`,
  },
  EMPTY: {
    palette: "red",
    label: () => "Agotado",
  },
};

interface StockBadgeProps {
  status: IngredientStatus;
  stockQty: string;
  unit: string;
}

export function StockBadge({ status, stockQty, unit }: StockBadgeProps) {
  const style = STATUS_STYLE[status];
  return <Badge colorPalette={style.palette}>{style.label(stockQty, unit)}</Badge>;
}
