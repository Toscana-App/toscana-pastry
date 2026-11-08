import { Badge } from "@chakra-ui/react";
import { formatQty } from "@/lib/format";
import type { IngredientStatus } from "../types";

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
