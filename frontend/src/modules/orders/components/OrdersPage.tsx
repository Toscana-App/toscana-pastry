"use client";

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
import { formatCents } from "@/lib/format";
import { EmptyState } from "@/modules/shared/EmptyState";
import { useOrders } from "../hooks/useOrders";
import { ORDER_STATUS_LABELS, ORDER_STATUSES, type OrderStatus } from "../types";

const PAGE_SIZE = 20;

/** Color del badge por estado (Chakra v3 colorPalette). */
const STATUS_COLORS: Record<OrderStatus, "blue" | "green" | "gray" | "red"> = {
  nuevo: "blue",
  confirmado: "green",
  entregado: "gray",
  cancelado: "red",
};

/**
 * Listado de pedidos (Fase 6, UC-01 / RF-P6-05) — /pedidos.
 *
 * Filtros combinables: búsqueda por nombre de cliente (debounce 250 ms),
 * estado y rango de fechas de pedido. Paginación server-side (20/página).
 * La creación es solo admin: las mutaciones de pedidos son de
 * administración (mismo RBAC que el wizard).
 */
export function OrdersPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const {
    items,
    total,
    page,
    query,
    status,
    dateFrom,
    dateTo,
    loading,
    error,
    setQuery,
    setStatus,
    setDateFrom,
    setDateTo,
    goToPage,
  } = useOrders();

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters =
    query.trim().length > 0 || status !== null || dateFrom !== "" || dateTo !== "";

  return (
    <Flex direction="column" gap={5}>
      <Flex align="center" justify="space-between" gap={3} flexWrap="wrap">
        <Flex direction="column" gap={1}>
          <Heading fontSize="2xl">Pedidos</Heading>
          <Text color="fg.muted">{total} en total</Text>
        </Flex>
        {isAdmin ? (
          <Button colorPalette="brand" asChild>
            <NextLink href="/pedidos/nuevo">+ Nuevo pedido</NextLink>
          </Button>
        ) : null}
      </Flex>

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
          actionLabel={isAdmin && !hasFilters ? "Crear el primer pedido" : undefined}
          actionHref={isAdmin && !hasFilters ? "/pedidos/nuevo" : undefined}
        />
      ) : (
        <Box overflowX="auto" borderWidth="1px" borderColor="border" rounded="md">
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
            <thead>
              <tr>
                {["Fecha", "Cliente", "Teléfono", "Ítems", "Total", "Estado", ""].map((h) => (
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
    </Flex>
  );
}
