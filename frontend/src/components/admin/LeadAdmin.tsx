"use client";

/** Lead management for admin (F4 — C5, RF-P11-13).

List with search (name/email), consumer/business badges, read status,
per-lead read toggle and "mark all as read".
*/

import {
  Badge,
  Box,
  Button,
  Card,
  Flex,
  Input,
  Stack,
  Table,
  Text,
} from "@chakra-ui/react";
import { useCallback, useEffect, useState } from "react";
import {
  fetchLeads,
  markAllLeadsRead,
  setLeadRead,
} from "@/services/leadsService";
import { LeadOut } from "@/types/leads";

const PAGE_SIZE = 25;

function LeadAdmin() {
  const [leads, setLeads] = useState<LeadOut[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState<string>("");

  const reload = useCallback(async (pageToLoad: number, q: string) => {
    setLoading(true);
    try {
      const res = await fetchLeads({
        q: q || undefined,
        page: pageToLoad,
        page_size: PAGE_SIZE,
      });
      setLeads(res.items ?? []);
      setTotal(res.total);
      setPage(res.page);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchLeads({ page: 1, page_size: PAGE_SIZE });
        if (cancelled) return;
        setLeads(res.items ?? []);
        setTotal(res.total);
      } catch {
        // no leads is not an error: empty table
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const applySearch = useCallback(() => {
    setAppliedQuery(query.trim());
    void reload(1, query.trim());
  }, [query, reload]);

  const toggleRead = useCallback(
    async (lead: LeadOut) => {
      setBusy(true);
      try {
        await setLeadRead(lead.id, !lead.read);
        setLeads((prev) =>
          prev.map((l) => (l.id === lead.id ? { ...l, read: !l.read } : l))
        );
      } finally {
        setBusy(false);
      }
    },
    []
  );

  const markAll = useCallback(async () => {
    setBusy(true);
    try {
      await markAllLeadsRead();
      setLeads((prev) => prev.map((l) => ({ ...l, read: true })));
    } finally {
      setBusy(false);
    }
  }, []);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Card.Root>
      <Card.Body>
        <Stack gap={4}>
          <Flex justify="space-between" align="center" flexWrap="wrap" gap={3}>
            <Text fontWeight="semibold">Leads ({total})</Text>
            <Button
              size="xs"
              variant="outline"
              disabled={busy || leads.every((l) => l.read)}
              onClick={() => void markAll()}
            >
              Marcar todos como leídos
            </Button>
          </Flex>

          <Flex gap={2}>
            <Input
              placeholder="Buscar por nombre o email"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") applySearch();
              }}
            />
            <Button variant="outline" onClick={applySearch}>
              Buscar
            </Button>
          </Flex>

          {leads.length === 0 ? (
            <Text fontSize="sm" color="fg.muted">
              {loading ? "Cargando…" : "No hay leads con esos filtros."}
            </Text>
          ) : (
            <Table.ScrollArea rounded="md">
              <Table.Root size="sm" variant="outline">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeader />
                    <Table.ColumnHeader>Nombre</Table.ColumnHeader>
                    <Table.ColumnHeader>Email</Table.ColumnHeader>
                    <Table.ColumnHeader>Tipo</Table.ColumnHeader>
                    <Table.ColumnHeader>Mensaje</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {leads.map((lead) => (
                    <Table.Row key={lead.id} opacity={lead.read ? 0.6 : 1}>
                      <Table.Cell>
                        <Button
                          size="xs"
                          variant={lead.read ? "ghost" : "solid"}
                          colorPalette={lead.read ? "gray" : "brand"}
                          disabled={busy}
                          onClick={() => void toggleRead(lead)}
                          aria-label={
                            lead.read
                              ? `Marcar ${lead.name} como no leído`
                              : `Marcar ${lead.name} como leído`
                          }
                        >
                          {lead.read ? "Leído" : "Nuevo"}
                        </Button>
                      </Table.Cell>
                      <Table.Cell>
                        <Text fontWeight="medium">{lead.name}</Text>
                        {lead.business_name && (
                          <Text fontSize="xs" color="fg.muted">
                            {lead.business_name}
                          </Text>
                        )}
                      </Table.Cell>
                      <Table.Cell>
                        <Text fontSize="sm">{lead.email}</Text>
                        {lead.phone && (
                          <Text fontSize="xs" color="fg.muted">
                            {lead.phone}
                          </Text>
                        )}
                      </Table.Cell>
                      <Table.Cell>
                        <Badge
                          colorPalette={
                            lead.customer_type === "business"
                              ? "brand"
                              : "gray"
                          }
                          variant="subtle"
                        >
                          {lead.customer_type === "business"
                            ? "Business"
                            : "Consumer"}
                        </Badge>
                      </Table.Cell>
                      <Table.Cell>
                        <Box maxW="280px">
                          <Text
                            fontSize="sm"
                            style={{
                              display: "-webkit-box",
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: "vertical",
                              overflow: "hidden",
                            }}
                          >
                            {lead.message}
                          </Text>
                        </Box>
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </Table.ScrollArea>
          )}

          {pageCount > 1 && (
            <Flex justify="center" align="center" gap={3}>
              <Button
                size="xs"
                variant="outline"
                disabled={page <= 1 || loading}
                onClick={() => void reload(page - 1, appliedQuery)}
              >
                Anterior
              </Button>
              <Text fontSize="sm">
                {page} / {pageCount}
              </Text>
              <Button
                size="xs"
                variant="outline"
                disabled={page >= pageCount || loading}
                onClick={() => void reload(page + 1, appliedQuery)}
              >
                Siguiente
              </Button>
            </Flex>
          )}
        </Stack>
      </Card.Body>
    </Card.Root>
  );
}

export default LeadAdmin;
