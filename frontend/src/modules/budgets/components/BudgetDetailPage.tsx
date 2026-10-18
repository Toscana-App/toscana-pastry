"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Box,
  Button,
  Dialog,
  Flex,
  Heading,
  HStack,
  Skeleton,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";
import NextLink from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { formatCents, formatPct } from "@/lib/format";
import { budgetsService } from "../service";
import {
  BUDGET_STATUS_LABELS,
  CALCULATION_MODE_LABELS,
  type BudgetDetail,
  type BudgetSummary,
} from "../types";

const STATUS_COLORS: Record<BudgetDetail["status"], "blue" | "green"> = {
  borrador: "blue",
  enviado: "green",
};

type PendingAction = "send" | "convert" | "delete";

const DIALOG_COPY: Record<PendingAction, { title: string; body: string; cta: string }> = {
  send: {
    title: "¿Enviar el presupuesto?",
    body: "Se marca como enviado y queda congelada una nueva versión (auditoría). Tras editarla podés reenviarla.",
    cta: "Enviar",
  },
  convert: {
    title: "¿Convertir en pedido?",
    body: "Se crea un pedido (estado nuevo) con los mismos ítems. El stock no se descuenta hasta confirmar el pedido.",
    cta: "Convertir",
  },
  delete: {
    title: "¿Eliminar el presupuesto?",
    body: "Se elimina de forma definitiva. No afecta stock ni pedidos ya creados.",
    cta: "Eliminar",
  },
};

/**
 * Detalle de presupuesto (Fase 7, P8) — /presupuestos/[id].
 *
 * Lectura pura: muestra los costos/precios derivados al guardar, sin
 * volver al catálogo. Totales siempre consistentes (RNF-P8-02).
 *
 * Acciones (admin, RF-P8-04/05/07/08): editar (borrador), recalcular
 * contra el catálogo, enviar/reenviar (congela versión), convertir en
 * pedido y eliminar con confirmación.
 */
interface BudgetDetailPageProps {
  budgetId: string;
}

export function BudgetDetailPage({ budgetId }: BudgetDetailPageProps) {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "admin";

  const [budget, setBudget] = useState<BudgetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [recalculated, setRecalculated] = useState<BudgetSummary | null>(null);
  const [recalcMargin, setRecalcMargin] = useState<number | null>(null);
  const [recalcLoading, setRecalcLoading] = useState(false);

  const load = useCallback(() => {
    budgetsService
      .getDetail(budgetId)
      .then(setBudget)
      .catch((e) => setError(e instanceof Error ? e.message : "No se pudo cargar el presupuesto"))
      .finally(() => setLoading(false));
  }, [budgetId]);

  // Un mount por id (route param de Next): sin reset de estado en el efecto.
  useEffect(() => {
    load();
  }, [load]);

  const runAction = useCallback(async () => {
    if (!budget || !pendingAction) return;
    setActionLoading(true);
    setActionError(null);
    try {
      if (pendingAction === "send") {
        setBudget(await budgetsService.send(budget.id));
      } else if (pendingAction === "convert") {
        const res = await budgetsService.convertToOrder(budget.id);
        router.push(`/pedidos/${res.order_id}`);
        return;
      } else {
        await budgetsService.remove(budget.id);
        router.push("/presupuestos");
        return;
      }
      setPendingAction(null);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "La acción falló");
    } finally {
      setActionLoading(false);
    }
  }, [budget, pendingAction, router]);

  const runRecalc = useCallback(async () => {
    if (!budget) return;
    setRecalcLoading(true);
    setActionError(null);
    setRecalculated(null);
    try {
      const res = await budgetsService.recalculate(budget.id);
      setRecalculated(res.summary);
      setRecalcMargin(res.margin_applied);
      // Volver a leer el detalle con los precios re-derivados.
      setBudget(await budgetsService.getDetail(budget.id));
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "El recálculo falló");
    } finally {
      setRecalcLoading(false);
    }
  }, [budget]);

  if (loading) {
    return (
      <Stack gap={3} maxW="720px">
        <Skeleton h="32px" />
        <Skeleton h="96px" />
        <Skeleton h="160px" />
        <Skeleton h="120px" />
      </Stack>
    );
  }

  if (error || !budget) {
    return (
      <Alert.Root status="error" maxW="640px">
        <Alert.Content>
          <Alert.Title>No se pudo cargar el presupuesto</Alert.Title>
          <Alert.Description>{error ?? "Presupuesto no encontrado"}</Alert.Description>
        </Alert.Content>
      </Alert.Root>
    );
  }

  const gananciaPct =
    budget.summary.subtotal > 0
      ? (budget.summary.ganancia / budget.summary.subtotal) * 100
      : null;

  return (
    <Flex direction="column" gap={5}>
      <Flex align="center" justify="space-between" gap={3} flexWrap="wrap">
        <HStack gap={3} align="center">
          <Heading fontSize="2xl">Presupuesto #{budget.seq}</Heading>
          <Badge colorPalette={STATUS_COLORS[budget.status]} variant="subtle">
            {BUDGET_STATUS_LABELS[budget.status]}
          </Badge>
          <Badge colorPalette="gray" variant="subtle">
            v{budget.version}
          </Badge>
        </HStack>
        <Button variant="ghost" asChild>
          <NextLink href="/presupuestos">Volver al listado</NextLink>
        </Button>
      </Flex>

      {/* Cliente + parámetros */}
      <Box borderWidth="1px" borderColor="gray.200" rounded="md" p={4}>
        <VStack align="start" gap={2}>
          <Text fontWeight="600">{budget.customer.name}</Text>
          <Text color="fg.muted" fontSize="sm">
            {budget.customer.phone}
          </Text>
          <HStack gap={4} fontSize="sm" color="fg.muted" wrap="wrap">
            <Text>Modo: {CALCULATION_MODE_LABELS[budget.calculation_mode]}</Text>
            <Text>
              Margen: {budget.margin_pct == null ? "margen del negocio" : formatPct(budget.margin_pct)}
            </Text>
            {budget.sent_at ? <Text>Enviado: {budget.sent_at}</Text> : null}
          </HStack>
        </VStack>
      </Box>

      {/* Ítems — precios guardados al escribir (RF-P8-04) */}
      <Box borderWidth="1px" borderColor="gray.200" rounded="md" overflowX="auto">
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
          <thead>
            <tr>
              {["Producto", "Cant.", "Costo unit.", "Precio unit.", "Subtotal"].map((h) => (
                <th
                  key={h}
                  scope="col"
                  style={{
                    textAlign: "left",
                    padding: "10px 14px",
                    borderBottom: "1px solid #e5e5e5",
                    fontWeight: 600,
                    color: "#525252",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {budget.items.map((item) => (
              <tr key={item.product_id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                <td style={{ padding: "10px 14px", fontWeight: 500 }}>{item.product_name}</td>
                <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                  {item.qty}
                </td>
                <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                  {formatCents(item.unit_cost)}
                </td>
                <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                  <HStack gap={2}>
                    <span>{formatCents(item.unit_selling)}</span>
                    {item.price_overridden ? (
                      <Badge colorPalette="purple" variant="subtle">
                        manual
                      </Badge>
                    ) : null}
                  </HStack>
                </td>
                <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                  {formatCents(item.line_selling)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Box>

      {/* Bloques de cálculo (RF-P8-02): ticket de fila, total destacado */}
      <Box
        borderWidth="1px"
        borderColor="gray.200"
        rounded="md"
        p={4}
        maxW="420px"
        alignSelf="flex-end"
        w="full"
      >
        <VStack align="stretch" gap={2}>
          <HStack justify="space-between" fontSize="sm">
            <Text color="fg.muted">Total costos</Text>
            <Text fontVariantNumeric="tabular-nums">{formatCents(budget.summary.total_costos)}</Text>
          </HStack>
          <HStack justify="space-between" fontSize="sm">
            <Text color="fg.muted">Subtotal de venta</Text>
            <Text fontVariantNumeric="tabular-nums">{formatCents(budget.summary.subtotal)}</Text>
          </HStack>
          <HStack justify="space-between" fontSize="sm">
            <Text color="fg.muted">
              Ganancia
              {gananciaPct != null ? ` (${formatPct(gananciaPct)})` : ""}
            </Text>
            <Text
              fontVariantNumeric="tabular-nums"
              color={budget.summary.ganancia < 0 ? "red.600" : undefined}
            >
              {formatCents(budget.summary.ganancia)}
            </Text>
          </HStack>
          <Box as="hr" border="none" h="1px" bg="gray.200" />
          <HStack justify="space-between">
            <Text fontWeight="600">Total venta (IVA 21%)</Text>
            <Text
              fontWeight="700"
              fontSize="xl"
              fontVariantNumeric="tabular-nums"
              aria-live="polite"
            >
              {formatCents(budget.summary.total_venta)}
            </Text>
          </HStack>
        </VStack>
      </Box>

      {/* Resultado del recálculo (recién re-derivado) */}
      {recalculated ? (
        <Alert.Root status="success" fontSize="sm">
          <Alert.Content>
            <Alert.Title>Precios recalculados contra el catálogo</Alert.Title>
            <Alert.Description>
              Margen aplicado: {formatPct(recalcMargin)}. Subtotal{" "}
              {formatCents(recalculated.subtotal)} · Costos{" "}
              {formatCents(recalculated.total_costos)} · Total venta{" "}
              {formatCents(recalculated.total_venta)}.
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {actionError ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Description>{actionError}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {/* Acciones admin */}
      {isAdmin ? (
        <HStack gap={3} wrap="wrap">
          {budget.status === "borrador" ? (
            <>
              <Button variant="outline" asChild>
                <NextLink href={`/presupuestos/${budget.id}/editar`}>Editar</NextLink>
              </Button>
              <Button variant="outline" loading={recalcLoading} onClick={() => void runRecalc()}>
                Recalcular precios
              </Button>
            </>
          ) : null}
          <Button colorPalette="brand" onClick={() => setPendingAction("send")} loading={actionLoading && pendingAction === "send"}>
            {budget.status === "borrador" ? "Enviar" : "Reenviar"}
          </Button>
          <Button variant="outline" onClick={() => setPendingAction("convert")}>
            Convertir en pedido
          </Button>
          <Button
            variant="outline"
            colorPalette="red"
            onClick={() => setPendingAction("delete")}
          >
            Eliminar
          </Button>
        </HStack>
      ) : null}

      {/* Confirmación de acciones (mismo patrón de Dialog v3 que pedidos) */}
      <Dialog.Root
        open={pendingAction !== null}
        onOpenChange={(e) => {
          if (!e.open) setPendingAction(null);
        }}
        role="alertdialog"
      >
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <Dialog.Header>
              <Dialog.Title>{pendingAction ? DIALOG_COPY[pendingAction].title : ""}</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <Text>{pendingAction ? DIALOG_COPY[pendingAction].body : ""}</Text>
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="ghost" onClick={() => setPendingAction(null)}>
                Cancelar
              </Button>
              <Button
                colorPalette={pendingAction === "delete" ? "red" : "brand"}
                loading={actionLoading}
                onClick={() => {
                  void runAction();
                }}
              >
                {pendingAction ? DIALOG_COPY[pendingAction].cta : ""}
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Dialog.Root>
    </Flex>
  );
}
