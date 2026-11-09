"use client";

import { useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Box,
  Button,
  Flex,
  Heading,
  Input,
  InputGroup,
  Pagination,
  Skeleton,
  Text,
} from "@chakra-ui/react";
import NextLink from "next/link";
import { SearchIcon } from "@/components/ui/search-icon";
import { useAuth } from "@/contexts/AuthContext";
import { formatCents, formatDateTime } from "@/lib/format";
import { EmptyState } from "@/modules/shared/EmptyState";
import { orderWindowService } from "@/modules/settings/service";
import type { OrderWindow } from "@/modules/settings/types";
import { useOrders } from "../hooks/useOrders";
import { ordersService } from "../service";
import { WeeklySummaryView } from "./WeeklySummaryView";
import { ORDER_STATUS_LABELS, ORDER_STATUSES, type OrderStatus } from "../types";

const PAGE_SIZE = 20;

const STATUS_COLORS: Record<OrderStatus, "blue" | "green" | "gray" | "red"> = {
  nuevo: "blue",
  confirmado: "green",
  entregado: "gray",
  cancelado: "red",
};

export function OrdersPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [view, setView] = useState<"list" | "weekly">("list");
  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const {
    items,
    total,
    unpaidCount,
    page,
    query,
    status,
    paid,
    dateFrom,
    dateTo,
    loading,
    error,
    setQuery,
    setStatus,
    setPaid,
    setDateFrom,
    setDateTo,
    goToPage,
  } = useOrders();

  const [orderWindow, setOrderWindow] = useState<OrderWindow | null>(null);
  useEffect(() => {
    let active = true;
    orderWindowService
      .get()
      .then((w) => {
        if (active) setOrderWindow(w);
      })
      .catch(() => {
        if (active) setOrderWindow(null);
      });
    return () => {
      active = false;
    };
  }, []);
  const windowClosed = orderWindow !== null && !orderWindow.open;

  const handleExport = (format: "csv" | "pdf") => {
    setExporting(true);
    setExportError(null);
    ordersService
      .exportReport(
        {
          status: status ?? undefined,
          paid: paid ?? undefined,
          from: dateFrom || undefined,
          to: dateTo || undefined,
        },
        format,
      )
      .catch((e: unknown) =>
        setExportError(
          e instanceof Error ? e.message : "No se pudo generar el archivo",
        ),
      )
      .finally(() => setExporting(false));
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters =
    query.trim().length > 0 ||
    status !== null ||
    paid !== null ||
    dateFrom !== "" ||
    dateTo !== "";

  return (
    <Flex direction="column" gap={5}>
      <Flex align="center" justify="space-between" gap={3} flexWrap="wrap">
        <Flex direction="column" gap={1}>
          <Heading fontSize="2xl">Pedidos</Heading>
          <Text color="fg.muted">
            {total} en total
            {unpaidCount > 0 ? ` · ${unpaidCount} sin pagar` : ""}
          </Text>
        </Flex>
        {view === "list" ? (
          <Flex gap={2}>
            <Button
              size="sm"
              variant="outline"
              disabled={exporting || total === 0}
              onClick={() => handleExport("csv")}
            >
              {exporting ? "Generando…" : "Exportar CSV"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              colorPalette="brand"
              disabled={exporting || total === 0}
              onClick={() => handleExport("pdf")}
            >
              {exporting ? "Generando…" : "Exportar PDF"}
            </Button>
          </Flex>
        ) : null}
        {isAdmin ? (
          windowClosed ? (
            <Button
              colorPalette="brand"
              disabled
              title="La ventana de pedidos está cerrada"
            >
              + Nuevo pedido
            </Button>
          ) : (
            <Button colorPalette="brand" asChild>
              <NextLink href="/pedidos/nuevo">+ Nuevo pedido</NextLink>
            </Button>
          )
        ) : null}
      </Flex>

      {windowClosed ? (
        <Alert.Root status="warning" borderRadius="md">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title>Sección de pedidos cerrada</Alert.Title>
            <Alert.Description>
              {orderWindow?.message || "No se pueden crear pedidos nuevos."}
              {orderWindow?.reopens_at
                ? ` Reabre el ${formatDateTime(orderWindow.reopens_at)}.`
                : ""}
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {}
      <Flex gap={1} borderBottomWidth="1px" borderColor="gray.200">
        {(
          [
            { id: "list", label: "Listado" },
            { id: "weekly", label: "Resumen semanal" },
          ] as const
        ).map((tab) => (
          <Box
            key={tab.id}
            as="button"
            onClick={() => setView(tab.id)}
            px={4}
            py={2}
            fontSize="sm"
            fontWeight={view === tab.id ? "600" : "400"}
            color={view === tab.id ? "brand.500" : "fg.muted"}
            borderBottomWidth="2px"
            borderBottomColor={view === tab.id ? "brand.500" : "transparent"}
            cursor="pointer"
          >
            {tab.label}
          </Box>
        ))}
      </Flex>

      {view === "weekly" ? (
        <WeeklySummaryView />
      ) : (
        <>
      <Flex gap={3} flexWrap="wrap" align="center">
        <InputGroup startElement={<SearchIcon />} maxW="320px">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por cliente…"
            aria-label="Buscar pedidos por nombre de cliente"
          />
        </InputGroup>

        <Flex gap={1} align="center">
          <Button
            size="sm"
            rounded="full"
            variant={status === null ? "solid" : "outline"}
            colorPalette={status === null ? "brand" : "gray"}
            aria-pressed={status === null}
            onClick={() => setStatus(null)}
          >
            Todos
          </Button>
          {ORDER_STATUSES.map((s) => (
            <Button
              key={s}
              size="sm"
              rounded="full"
              whiteSpace="nowrap"
              variant={status === s ? "solid" : "outline"}
              colorPalette={status === s ? "brand" : "gray"}
              aria-pressed={status === s}
              onClick={() => setStatus(status === s ? null : s)}
            >
              {ORDER_STATUS_LABELS[s]}
            </Button>
          ))}
          <Button
            size="sm"
            rounded="full"
            whiteSpace="nowrap"
            variant={paid === false ? "solid" : "outline"}
            colorPalette={paid === false ? "orange" : "gray"}
            aria-pressed={paid === false}
            onClick={() => setPaid(paid === false ? null : false)}
          >
            Sin pagar
          </Button>
        </Flex>

        <Flex gap={2} align="center">
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            maxW="160px"
            aria-label="Filtrar desde fecha"
          />
          <Text color="fg.muted" fontSize="sm">
            a
          </Text>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            maxW="160px"
            aria-label="Filtrar hasta fecha"
          />
        </Flex>
      </Flex>

      {error ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Title>No se pudo cargar la lista</Alert.Title>
            <Alert.Description>{error}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {loading ? (
        <Flex direction="column" gap={3}>
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} h="40px" />
          ))}
        </Flex>
      ) : items.length === 0 ? (
        <EmptyState
          title={hasFilters ? "Sin resultados" : "Todavía no hay pedidos"}
          description={
            hasFilters
              ? "Probá cambiar los filtros o la búsqueda."
              : isAdmin
                ? "Cargá el primer pedido desde el wizard."
                : "Los pedidos que haga tu panadero aparecerán acá."
          }
          actionLabel={
            isAdmin && !hasFilters && !windowClosed
              ? "Crear el primer pedido"
              : undefined
          }
          actionHref={
            isAdmin && !hasFilters && !windowClosed ? "/pedidos/nuevo" : undefined
          }
        />
      ) : (
        <Box overflowX="auto" borderWidth="1px" borderColor="border" rounded="md">
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
            <thead>
              <tr>
                {[
                  "Fecha",
                  "Cliente",
                  "Teléfono",
                  "Ítems",
                  "Total",
                  "Pago",
                  "Estado",
                  "",
                ].map((h) => (
                  <th
                    key={h}
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
              {items.map((order) => (
                <tr key={order.id} style={{ borderBottom: "1px solid var(--chakra-colors-border-muted)" }}>
                  <td style={{ padding: "10px 14px", whiteSpace: "nowrap" }}>
                    {order.date}
                  </td>
                  <td style={{ padding: "10px 14px", fontWeight: 500 }}>
                    {order.customer_name}
                  </td>
                  <td style={{ padding: "10px 14px", whiteSpace: "nowrap" }}>
                    {order.customer_phone}
                  </td>
                  <td style={{ padding: "10px 14px" }}>{order.item_count}</td>
                  <td style={{ padding: "10px 14px", whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>
                    {formatCents(order.total)}
                  </td>
                  <td style={{ padding: "10px 14px" }}>
                    <Badge
                      colorPalette={order.paid ? "green" : "orange"}
                      variant="subtle"
                    >
                      {order.paid ? "Pagado" : "Sin pagar"}
                    </Badge>
                  </td>
                  <td style={{ padding: "10px 14px" }}>
                    <Badge colorPalette={STATUS_COLORS[order.status]} variant="subtle">
                      {ORDER_STATUS_LABELS[order.status]}
                    </Badge>
                  </td>
                  <td style={{ padding: "10px 14px", textAlign: "right" }}>
                    <Button size="xs" variant="outline" asChild>
                      <NextLink href={`/pedidos/${order.id}`}>Ver</NextLink>
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Box>
      )}

      {!loading && pageCount > 1 ? (
        <Pagination.Root
          colorPalette="brand"
          count={total}
          pageSize={PAGE_SIZE}
          page={page}
          onPageChange={(details) => goToPage(details.page)}
        >
          <Pagination.PrevTrigger />
          <Pagination.Items
            render={(item) =>
              item.type === "page" ? (
                <Pagination.Item type="page" value={item.value}>
                  {item.value}
                </Pagination.Item>
              ) : null
            }
          />
          <Pagination.NextTrigger />
        </Pagination.Root>
      ) : null}
        </>
      )}
    </Flex>
  );
}
