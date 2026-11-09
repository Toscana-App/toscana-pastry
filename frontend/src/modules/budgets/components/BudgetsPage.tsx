"use client";

import { useState } from "react";
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
import { useBudgets } from "../hooks/useBudgets";
import { budgetsService } from "../service";
import { BUDGET_STATUS_LABELS, BUDGET_STATUSES, type BudgetStatus } from "../types";

const PAGE_SIZE = 20;

const STATUS_COLORS: Record<BudgetStatus, "blue" | "green"> = {
  borrador: "blue",
  enviado: "green",
};

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso.slice(0, 10);
  return date.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function BudgetsPage() {
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
  } = useBudgets();

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters =
    query.trim().length > 0 || status !== null || dateFrom !== "" || dateTo !== "";

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const handleExport = (format: "csv" | "pdf") => {
    setExporting(true);
    setExportError(null);
    budgetsService
      .exportReport(
        {
          status: status ?? undefined,
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

  return (
    <Flex direction="column" gap={5}>
      <Flex align="center" justify="space-between" gap={3} flexWrap="wrap">
        <Flex direction="column" gap={1}>
          <Heading fontSize="2xl">Presupuestos</Heading>
          <Text color="fg.muted">{total} en total</Text>
        </Flex>
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
          {isAdmin ? (
            <Button colorPalette="brand" asChild>
              <NextLink href="/presupuestos/nuevo">+ Nuevo presupuesto</NextLink>
            </Button>
          ) : null}
        </Flex>
      </Flex>

      {exportError ? (
        <Alert.Root status="error" borderRadius="md">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title>No se pudo exportar</Alert.Title>
            <Alert.Description>{exportError}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      <Flex gap={3} flexWrap="wrap" align="center">
        <InputGroup startElement={<SearchIcon />} maxW="320px">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por cliente o nº…"
            aria-label="Buscar presupuestos por cliente o número"
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
          {BUDGET_STATUSES.map((s) => (
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
              {BUDGET_STATUS_LABELS[s]}
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
          title={hasFilters ? "Sin resultados" : "Todavía no hay presupuestos"}
          description={
            hasFilters
              ? "Probá cambiar los filtros o la búsqueda."
              : isAdmin
                ? "Cargá el primer presupuesto desde el wizard."
                : "Los presupuestos de tu panadero aparecerán acá."
          }
          actionLabel={isAdmin && !hasFilters ? "Crear el primer presupuesto" : undefined}
          actionHref={isAdmin && !hasFilters ? "/presupuestos/nuevo" : undefined}
        />
      ) : (
        <Box overflowX="auto" borderWidth="1px" borderColor="border" rounded="md">
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
            <thead>
              <tr>
                {[
                  "Nº",
                  "Fecha",
                  "Cliente",
                  "Teléfono",
                  "Ítems",
                  "Total",
                  "Estado",
                  "",
                ].map((h, i) => (
                  <th
                    key={`${h}-${i}`}
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
              {items.map((budget) => (
                <tr key={budget.id} style={{ borderBottom: "1px solid var(--chakra-colors-border-muted)" }}>
                  <td style={{ padding: "10px 14px", fontVariantNumeric: "tabular-nums" }}>
                    {budget.seq}
                  </td>
                  <td style={{ padding: "10px 14px", whiteSpace: "nowrap" }}>
                    {formatDate(budget.created_at)}
                  </td>
                  <td style={{ padding: "10px 14px", fontWeight: 500 }}>
                    {budget.customer_name}
                  </td>
                  <td style={{ padding: "10px 14px", whiteSpace: "nowrap" }}>
                    {budget.customer_phone}
                  </td>
                  <td style={{ padding: "10px 14px" }}>{budget.item_count}</td>
                  <td style={{ padding: "10px 14px", whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>
                    {formatCents(budget.total)}
                  </td>
                  <td style={{ padding: "10px 14px" }}>
                    <Badge colorPalette={STATUS_COLORS[budget.status]} variant="subtle">
                      {BUDGET_STATUS_LABELS[budget.status]}
                    </Badge>
                  </td>
                  <td style={{ padding: "10px 14px", textAlign: "right" }}>
                    <Button size="xs" variant="outline" asChild>
                      <NextLink href={`/presupuestos/${budget.id}`}>Ver</NextLink>
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
