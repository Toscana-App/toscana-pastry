"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Box,
  Button,
  Flex,
  Heading,
  Input,
  Skeleton,
  Text,
} from "@chakra-ui/react";
import { trackEvent } from "@/lib/analytics";
import { formatCents } from "@/lib/format";
import { weeklyService } from "../weekly.service";
import type { WeeklySummary } from "../types";

export function WeeklySummaryView() {
  const [summary, setSummary] = useState<WeeklySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<null | "csv" | "pdf">(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const [appliedWeek, setAppliedWeek] = useState<string | null>(null);
  const [weekInput, setWeekInput] = useState("");

  const load = useCallback((week: string | null) => {
    setLoading(true);
    setError(null);
    weeklyService
      .get(week)
      .then((res) => setSummary(res))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "No se pudo cargar el resumen"),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadInitial = async () => {
      try {
        const res = await weeklyService.get(null);
        if (!cancelled) setSummary(res);
      } catch (e: unknown) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "No se pudo cargar el resumen");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadInitial();
    return () => {
      cancelled = true;
    };
  }, []);

  const applyWeek = () => {
    const week = weekInput.trim() || null;
    setAppliedWeek(week);
    load(week);
  };

  const showCurrent = () => {
    setWeekInput("");
    setAppliedWeek(null);
    load(null);
  };

  const handleExport = (format: "csv" | "pdf") => {
    if (!summary) return;
    setExporting(format);
    setExportError(null);
    const done = () => setExporting(null);
    const fail = (e: unknown) => {
      setExportError(e instanceof Error ? e.message : "No se pudo generar el archivo");
      setExporting(null);
    };
    if (format === "csv") {
      weeklyService
        .exportCsv(summary.week)
        .then(done)
        .catch(fail);
    } else {
      weeklyService
        .exportPdf(appliedWeek)
        .then(done)
        .catch(fail);
    }
    trackEvent("weekly_export", { format, week: appliedWeek ?? "actual" });
  };

  return (
    <Flex direction="column" gap={4}>
      <Flex align="center" justify="space-between" gap={3} flexWrap="wrap">
        <Flex align="center" gap={3} flexWrap="wrap">
          <Input
            value={weekInput}
            onChange={(e) => setWeekInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applyWeek()}
            placeholder="Ej. 2026-W45 o 2026-11-02"
            aria-label="Semana a ver (ISO AAAA-Wnn o fecha)"
            maxW="240px"
            size="sm"
          />
          <Button size="sm" variant="outline" onClick={applyWeek}>
            Ver
          </Button>
          {appliedWeek !== null ? (
            <Button size="sm" variant="ghost" onClick={showCurrent}>
              Semana actual
            </Button>
          ) : null}
        </Flex>
        <Flex gap={2}>
          <Button
            size="sm"
            variant="outline"
            disabled={loading || !summary || exporting !== null}
            onClick={() => handleExport("csv")}
          >
            {exporting === "csv" ? "Generando…" : "Exportar CSV"}
          </Button>
          <Button
            size="sm"
            colorPalette="brand"
            variant="outline"
            disabled={loading || !summary || exporting !== null}
            onClick={() => handleExport("pdf")}
          >
            {exporting === "pdf" ? "Generando…" : "Exportar PDF"}
          </Button>
        </Flex>
      </Flex>

      {summary && !loading ? (
        <Text color="fg.muted" fontSize="sm">
          Semana del {summary.week.from} al {summary.week.to}
        </Text>
      ) : null}

      {exportError ? (
        <Alert.Root status="error" borderRadius="md">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title>No se pudo exportar</Alert.Title>
            <Alert.Description>{exportError}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {error ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Title>No se pudo cargar el resumen semanal</Alert.Title>
            <Alert.Description>{error}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {loading ? (
        <Flex direction="column" gap={3}>
          <Skeleton h="64px" />
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} h="40px" />
          ))}
        </Flex>
      ) : summary ? (
        <>
          <Flex gap={3} flexWrap="wrap">
            {[
              { label: "Total", value: summary.totals.amount, palette: "gray" as const },
              { label: "Pagado", value: summary.totals.paid, palette: "green" as const },
              { label: "Pendiente", value: summary.totals.unpaid, palette: "orange" as const },
            ].map((t) => (
              <Flex
                key={t.label}
                direction="column"
                gap={1}
                borderWidth="1px"
                borderColor="gray.200"
                rounded="md"
                p={4}
                minW="160px"
              >
                <Text color="fg.muted" fontSize="sm">
                  {t.label}
                </Text>
                <Text fontSize="lg" fontWeight="600" fontVariantNumeric="tabular-nums">
                  {formatCents(t.value)}
                </Text>
              </Flex>
            ))}
          </Flex>

          {summary.items.length === 0 ? (
            <Text color="fg.muted">
              Sin pedidos confirmados o entregados en la semana.
            </Text>
          ) : (
            <Box overflowX="auto" borderWidth="1px" borderColor="gray.200" rounded="md">
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
                <thead>
                  <tr>
                    {["Fecha", "Cliente", "Ítems", "Total", "Pago"].map((h) => (
                      <th
                        key={h}
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
                  {summary.items.map((item) => (
                    <tr key={item.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                      <td style={{ padding: "10px 14px", whiteSpace: "nowrap" }}>
                        {item.date}
                      </td>
                      <td style={{ padding: "10px 14px", fontWeight: 500 }}>
                        {item.customer}
                      </td>
                      <td style={{ padding: "10px 14px" }}>{item.items_count}</td>
                      <td
                        style={{
                          padding: "10px 14px",
                          whiteSpace: "nowrap",
                          fontVariantNumeric: "tabular-nums",
                        }}
                      >
                        {formatCents(item.total)}
                      </td>
                      <td style={{ padding: "10px 14px" }}>
                        <Badge colorPalette={item.paid ? "green" : "orange"} variant="subtle">
                          {item.paid ? "Pagado" : "Sin pagar"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Box>
          )}
        </>
      ) : null}
    </Flex>
  );
}
