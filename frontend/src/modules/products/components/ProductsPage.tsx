"use client";

import { useState } from "react";
import {
  Alert,
  Button,
  Flex,
  Grid,
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
import { EmptyState } from "@/modules/shared/EmptyState";
import { useProducts } from "../hooks/useProducts";
import { useProductCategories } from "../hooks/useProductCategories";
import { useProductTags } from "../hooks/useProductTags";
import { ImportDialogV2 } from "@/modules/imports/ImportDialogV2";
import { downloadTemplate } from "@/modules/imports/download";
import { ProductCard } from "./ProductCard";

const PAGE_SIZE = 20;

export function ProductsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const {
    items,
    total,
    page,
    query,
    category,
    tags,
    loading,
    error,
    setQuery,
    setCategory,
    toggleTag,
    goToPage,
    reload,
  } = useProducts();
  const tagCounts = useProductTags();
  const categoryCounts = useProductCategories();
  const [csvImportOpen, setCsvImportOpen] = useState(false);
  const [tplError, setTplError] = useState<string | null>(null);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters =
    query.trim().length > 0 || category !== null || tags.length > 0;

  return (
    <Flex direction="column" gap={5}>
      <Flex align="center" justify="space-between" gap={3} flexWrap="wrap">
        <Flex direction="column" gap={1}>
          <Heading as="h1" fontSize="2xl" textWrap="balance">
            Productos
          </Heading>
          <Text color="fg.muted" fontVariantNumeric="tabular-nums" aria-live="polite">
            {total} en total
          </Text>
        </Flex>
        {isAdmin ? (
          <Flex gap={3}>
            <Button
              variant="outline"
              onClick={() =>
                downloadTemplate("products")
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
              <NextLink href="/productos/new">+ Nuevo producto</NextLink>
            </Button>
          </Flex>
        ) : null}
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
          aria-label="Buscar productos por nombre"
        />
      </InputGroup>

      <Flex
        gap={2}
        overflowX="auto"
        pb={1}
        role="group"
        aria-label="Filtrar por categoría"
      >
        <Button
          size="sm"
          rounded="full"
          variant={category === null ? "solid" : "outline"}
          colorPalette={category === null ? "brand" : "gray"}
          aria-pressed={category === null}
          onClick={() => setCategory(null)}
        >
          Todas
        </Button>
        {categoryCounts.map((entry) => (
          <Button
            key={entry.name}
            size="sm"
            rounded="full"
            whiteSpace="nowrap"
            variant={category === entry.name ? "solid" : "outline"}
            colorPalette={category === entry.name ? "brand" : "gray"}
            aria-pressed={category === entry.name}
            onClick={() =>
              setCategory(category === entry.name ? null : entry.name)
            }
          >
            {entry.name}
            <Text as="span" color="inherit" opacity={0.75} fontSize="xs">
              {entry.count}
            </Text>
          </Button>
        ))}
      </Flex>

      {tagCounts.length > 0 ? (
        <Flex
          gap={2}
          overflowX="auto"
          pb={1}
          role="group"
          aria-label="Filtrar por tags"
        >
          {tagCounts.map((tag) => {
            const active = tags.some(
              (item) => item.toLowerCase() === tag.name.toLowerCase(),
            );
            return (
              <Button
                key={tag.name}
                size="xs"
                rounded="full"
                whiteSpace="nowrap"
                variant={active ? "solid" : "subtle"}
                colorPalette={active ? "brand" : "gray"}
                aria-pressed={active}
                onClick={() => toggleTag(tag.name)}
              >
                {tag.name}
                <Text as="span" color="inherit" opacity={0.75}>
                  {tag.count}
                </Text>
              </Button>
            );
          })}
        </Flex>
      ) : null}

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
        <Grid
          gap={4}
          gridTemplateColumns="repeat(auto-fill, minmax(240px, 1fr))"
        >
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} height="5.5rem" rounded="lg" />
          ))}
        </Grid>
      ) : total === 0 && !hasFilters ? (
        <EmptyState
          title="Todavía no hay productos"
          description={
            isAdmin
              ? "Creá tu primer producto con su receta para calcular el precio de venta."
              : "Cuando la pastelería cargue su catálogo, va a aparecer acá."
          }
          actionLabel={isAdmin ? "Crear tu primer producto" : undefined}
          actionHref={isAdmin ? "/productos/new" : undefined}
        />
      ) : total === 0 ? (
        <EmptyState
          title={
            query.trim()
              ? `Sin resultados para «${query.trim()}»`
              : category !== null
                ? `Sin productos en «${category}»`
                : `Sin productos con los tags seleccionados`
          }
          description="Probá con otro nombre o quitá los filtros."
        />
      ) : (
        <>
          <Grid
            gap={4}
            gridTemplateColumns={{
              base: "1fr",
              md: "repeat(2, 1fr)",
              lg: "repeat(3, 1fr)",
            }}
          >
            {items.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </Grid>

          {pageCount > 1 ? (
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

      <ImportDialogV2
        entity="products"
        open={csvImportOpen}
        onOpenChange={setCsvImportOpen}
        onImported={reload}
      />
    </Flex>
  );
}
