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
  type PdfShare,
  type WhatsAppLink,
} from "../types";

const STATUS_COLORS: Record<BudgetDetail["status"], "blue" | "green"> = {
  borrador: "blue",
  enviado: "green",
};

type PendingAction = "send" | "convert" | "delete";

/** P9: el link temporal firma un vencimiento; vencido → se regenera. */
function isShareExpired(share: PdfShare | null): boolean {
  return share != null && new Date(share.expires_at).getTime() < Date.now();
}

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
  // Fase 8 (P9/P10): PDF y WhatsApp.
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [waLast, setWaLast] = useState<WhatsAppLink | null>(null);
  const [waLoading, setWaLoading] = useState(false);
  const [share, setShare] = useState<PdfShare | null>(null);
  const [shareLoading, setShareLoading] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

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

  /** P9: preview del PDF (GET binario → objectURL → iframe). */
  const openPdf = useCallback(async () => {
    if (!budget) return;
    setPdfLoading(true);
    setActionError(null);
    try {
      const url = await budgetsService.pdfUrl(budget.id);
      setPdfUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return url;
      });
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "No se pudo generar el PDF");
    } finally {
      setPdfLoading(false);
    }
  }, [budget]);

  /** P10: wa.me prellenado; 429 → mensaje de límite (RNF-P10-06). */
  const sendWhatsapp = useCallback(async () => {
    if (!budget) return;
    setWaLoading(true);
    setActionError(null);
    try {
      const res = await budgetsService.whatsappLink(budget.id);
      window.open(res.url, "_blank", "noopener");
      setWaLast(res);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "No se pudo generar el link de WhatsApp");
    } finally {
      setWaLoading(false);
    }
  }, [budget]);

  /** P9: link temporal firmado (72 h). Regenerar lo reemplaza. */
  const newShareLink = useCallback(async () => {
    if (!budget) return;
    setShareLoading(true);
    setActionError(null);
    try {
      setShare(await budgetsService.sharePdf(budget.id));
      setShareCopied(false);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "No se pudo generar el link");
    } finally {
      setShareLoading(false);
    }
  }, [budget]);

  const copyShare = useCallback(async () => {
    if (!share) return;
    try {
      await navigator.clipboard.writeText(share.url);
      setShareCopied(true);
    } catch {
      setActionError("No se pudo copiar el link al portapapeles");
    }
  }, [share]);

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
      <Box borderWidth="1px" borderColor="border" rounded="md" p={4}>
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
      <Box borderWidth="1px" borderColor="border" rounded="md" overflowX="auto">
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
                    borderBottom: "1px solid var(--chakra-colors-border)",
                    fontWeight: 600,
                    color: "var(--chakra-colors-fg-muted)",
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
              <tr key={item.product_id} style={{ borderBottom: "1px solid var(--chakra-colors-border-muted)" }}>
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
        borderColor="border"
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
              color={budget.summary.ganancia < 0 ? "red.fg" : undefined}
            >
              {formatCents(budget.summary.ganancia)}
            </Text>
          </HStack>
          <Box as="hr" border="none" h="1px" bg="bg.emphasized" />
          <HStack justify="space-between">
            <Text fontWeight="600">Total venta (sin IVA)</Text>
            <Text
              fontWeight="700"
              fontSize="xl"
              fontVariantNumeric="tabular-nums"
              aria-live="polite"
            >
              {formatCents(budget.summary.total_venta)}
            </Text>
          </HStack>
          <HStack justify="space-between" fontSize="sm">
            <Text color="fg.muted">IVA (21%) — costo aparte</Text>
            <Text fontVariantNumeric="tabular-nums">{formatCents(budget.summary.iva)}</Text>
          </HStack>
          <HStack justify="space-between" fontSize="sm">
            <Text color="fg.muted">Total con IVA</Text>
            <Text fontVariantNumeric="tabular-nums" fontWeight="600">
              {formatCents(budget.summary.total_venta + budget.summary.iva)}
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
              {formatCents(recalculated.total_costos)} · Total venta (sin IVA){" "}
              {formatCents(recalculated.total_venta)} + IVA{" "}
              {formatCents(recalculated.iva)} (costo aparte) ={" "}
              {formatCents(recalculated.total_venta + recalculated.iva)}.
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
          <Button variant="outline" asChild>
            <NextLink href={`/presupuestos/${budget.id}/editar`}>Editar</NextLink>
          </Button>
          {budget.status === "borrador" ? (
            <>
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
          <Button variant="outline" loading={pdfLoading} onClick={() => void openPdf()}>
            Ver PDF
          </Button>
          <Button
            variant="outline"
            loading={waLoading}
            onClick={() => void sendWhatsapp()}
          >
            Enviar por WhatsApp
          </Button>
          <Button
            variant="outline"
            loading={shareLoading && !isShareExpired(share)}
            onClick={() => void newShareLink()}
          >
            Link temporal (72 h)
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

      {/* Preview del PDF (P9): objectURL del binario servido. */}
      {pdfUrl ? (
        <Box borderWidth="1px" borderColor="gray.200" rounded="md" w="full">
          <iframe
            src={pdfUrl}
            title={`PDF presupuesto ${budget.seq}`}
            style={{ width: "100%", height: "720px", border: "none", display: "block" }}
          />
        </Box>
      ) : null}

      {/* WhatsApp (P10): wa.me abierto + registro de auditoría. */}
      {waLast ? (
        <Alert.Root status="success" fontSize="sm">
          <Alert.Content>
            <Alert.Description>
              WhatsApp abierto con el presupuesto prellenado (enviado {waLast.sent_at}). El
              cliente solo presiona &quot;enviar&quot; en la app.
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {/* Link temporal (P9): copiable, con vencimiento y regeneración. */}
      {share ? (
        <Box borderWidth="1px" borderColor="gray.200" rounded="md" p={4} maxW="640px">
          <VStack align="start" gap={2}>
            <Text fontWeight="600">Link temporal (72 h)</Text>
            {isShareExpired(share) ? (
              <>
                <Text fontSize="sm" color="red.600">
                  El link venció.
                </Text>
                <Button
                  size="sm"
                  variant="outline"
                  loading={shareLoading}
                  onClick={() => void newShareLink()}
                >
                  Generar nuevo
                </Button>
              </>
            ) : (
              <>
                <HStack gap={2} align="center" wrap="wrap">
                  <Text fontSize="sm" fontFamily="mono" wordBreak="break-all">
                    {share.url}
                  </Text>
                  <Button size="sm" variant="outline" onClick={() => void copyShare()}>
                    {shareCopied ? "Copiado" : "Copiar"}
                  </Button>
                </HStack>
                <Text fontSize="sm" color="fg.muted">
                  Vence: {new Date(share.expires_at).toLocaleString()}
                </Text>
              </>
            )}
          </VStack>
        </Box>
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
