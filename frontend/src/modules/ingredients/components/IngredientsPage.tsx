"use client";

import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Flex,
  FormatNumber,
  Heading,
  Input,
  InputGroup,
  Pagination,
  Table,
  Text,
} from "@chakra-ui/react";
import { IngredientsSkeleton } from "@/components/ui/skeleton";

import NextLink from "next/link";
import { formatQty, centsToPesos } from "@/lib/format";
import { SearchIcon } from "@/components/ui/search-icon";
import { EmptyState } from "@/modules/shared/EmptyState";
import { useIngredients } from "../hooks/useIngredients";
import { ImportDialogV2 } from "@/modules/imports/ImportDialogV2";
import { downloadTemplate } from "@/modules/imports/download";
import { StockBadge } from "./StockBadge";

const PAGE_SIZE = 50;

export function IngredientsPage() {
  const { items, total, page, query, loading, error, setQuery, goToPage, reload } =
    useIngredients();
  const [csvImportOpen, setCsvImportOpen] = useState(false);
  const [tplError, setTplError] = useState<string | null>(null);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasSearched = query.trim().length > 0;

  return (
    <Flex direction="column" gap={5}>
      <Flex align="center" justify="space-between" gap={3} flexWrap="wrap">
        <Flex direction="column" gap={1}>
          <Heading fontSize="2xl" textWrap="balance">Ingredientes</Heading>
          <Text color="fg.muted" fontVariantNumeric="tabular-nums" aria-live="polite">
            {total} en total
          </Text>
        </Flex>
        <Flex gap={3}>
          <Button
            variant="outline"
            onClick={() =>
              downloadTemplate("ingredients")
                .then(() => setTplError(null))
                .catch((e) =>
                  setTplError(
                    e instanceof Error ? e.message : "No se pudo descargar la plantilla",
                  ),
                )
            }
          >
            Descargar plantilla
          </Button>
          <Button variant="outline" onClick={() => setCsvImportOpen(true)}>
            Importar CSV
          </Button>
          <Button colorPalette="brand" asChild>
            <NextLink href="/admin/ingredients/new">+ Nuevo</NextLink>
          </Button>
        </Flex>
      </Flex>

      <InputGroup startElement={<SearchIcon />}>
        <Input
          name="q"
          type="search"
          autoComplete="off"
          spellCheck={false}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar por nombre…"
          aria-label="Buscar ingredientes por nombre"
        />
      </InputGroup>

      {error ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Title>No se pudo cargar la lista</Alert.Title>
            <Alert.Description>{error}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {tplError ? (
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Description>{tplError}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
      ) : null}

      {loading ? (
        <IngredientsSkeleton />
      ) : total === 0 && !hasSearched ? (
        <EmptyState
          title="Todavía no hay ingredientes"
          description="Cargá tu primer ingrediente para empezar a calcular precios."
          actionLabel="Cargar ingrediente"
          actionHref="/admin/ingredients/new"
        />
      ) : total === 0 ? (
        <EmptyState
          title={`Sin resultados para «${query.trim()}»`}
          description="Probá con otro nombre."
        />
      ) : (
        <>
          {}
          <Box display={{ base: "none", md: "block" }}>
            <Table.ScrollArea borderWidth="1px" rounded="md">
              <Table.Root size="sm">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeader>Name</Table.ColumnHeader>
                    <Table.ColumnHeader>Unit price</Table.ColumnHeader>
                    <Table.ColumnHeader>Stock</Table.ColumnHeader>
                    <Table.ColumnHeader>Status</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {items.map((ing) => (
                    <Table.Row key={ing.id}>
                      <Table.Cell>
                        <NextLink href={`/admin/ingredients/${ing.id}`}>
                          <Text fontWeight="500" color="brand.fg" textDecoration="none" overflowWrap="anywhere">
                            {ing.name}
                          </Text>
                        </NextLink>
                      </Table.Cell>
                      <Table.Cell fontVariantNumeric="tabular-nums"><FormatNumber value={centsToPesos(ing.price_per_unit)} style="currency" currency="ARS" /></Table.Cell>
                      <Table.Cell fontVariantNumeric="tabular-nums">{formatQty(ing.stock_qty, ing.unit)}</Table.Cell>
                      <Table.Cell>
                        <StockBadge
                          status={ing.status}
                          stockQty={ing.stock_qty}
                          unit={ing.unit}
                        />
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </Table.ScrollArea>
          </Box>

          {}
          <Flex direction="column" gap={3} display={{ base: "flex", md: "none" }}>
            {items.map((ing) => (
              <NextLink key={ing.id} href={`/admin/ingredients/${ing.id}`}>
                <Flex
                  direction="column"
                  gap={2}
                  borderWidth="1px"
                  borderColor="border"
                  rounded="md"
                  p={4}
                  _hover={{ borderColor: "brand.solid" }}
                >
                  <Flex justify="space-between" align="center" gap={3}>
                    <Text fontWeight="600" overflowWrap="anywhere" minW={0}>{ing.name}</Text>
                    <StockBadge
                      status={ing.status}
                      stockQty={ing.stock_qty}
                      unit={ing.unit}
                    />
                  </Flex>
                  <Flex justify="space-between" color="fg.muted" fontSize="sm">
                    <Text fontVariantNumeric="tabular-nums">Unit price: {<FormatNumber value={centsToPesos(ing.price_per_unit)} style="currency" currency="ARS" />}</Text>
                    <Text fontVariantNumeric="tabular-nums">Stock: {formatQty(ing.stock_qty, ing.unit)}</Text>
                  </Flex>
                </Flex>
              </NextLink>
            ))}
          </Flex>

          {pageCount > 1 ? (
            <Pagination.Root
              colorScheme="brand"
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

      <ImportDialogV2
        entity="ingredients"
        open={csvImportOpen}
        onOpenChange={setCsvImportOpen}
        onImported={reload}
      />
    </Flex>
  );
}
