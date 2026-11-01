"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Flex,
  Input,
  Button,
  Table,
  Text,
  Spinner,
  IconButton,
} from "@chakra-ui/react";
import { calcProductsService } from "@/services/calcProductsService";
import { toaster } from "@/lib/toaster";
import type {
  ProductListItem,
  ProductListQuery,
  ProductStatus,
} from "@/types/calc";

interface ProductListProps {
  mode?: "library" | "price-list";
}

export type { ProductListProps };

// Union type for items from different services
export type ProductListDisplayItem = ProductListItem;

export default function ProductList({ mode = "library" }: ProductListProps) {
  const [products, setProducts] = useState<ProductListDisplayItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);

  // Search and filter state
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ProductStatus | "">("");
  const [sortBy, setSortBy] = useState<ProductListQuery["sort"]>("name");
  const [sortDir, setSortDir] = useState<ProductListQuery["dir"]>("asc");

  // Fetch products/price list when dependencies change
  useEffect(() => {
    const query: ProductListQuery = {
      q: search || undefined,
      category_id: undefined,
      status: statusFilter || undefined,
      sort: sortBy,
      dir: sortDir,
      page,
      page_size: pageSize,
    };

    const fetchData = async () => {
      setLoading(true);
      try {
        const fetchData = mode === "library" 
          ? calcProductsService.listProducts(query)
          : calcProductsService.listPriceList(query);

        const response = await fetchData;
        
        if (mode === "library") {
          setProducts(response.items as ProductListDisplayItem[]);
          setTotal(response.total);
        } else {
          setProducts(response.items as ProductListDisplayItem[]);
          setTotal(response.total);
        }
      } catch {
        toaster.create({ title: `Error cargando ${mode}`, type: "error" });
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [mode, search, statusFilter, sortBy, sortDir, page, pageSize]);

  const handleSearch = useCallback(() => {
    setSearch(searchInput);
    setPage(1);
  }, [searchInput]);

  const clearFilters = useCallback(() => {
    setSearchInput("");
    setSearch("");
    setStatusFilter("");
    setSortBy("name");
    setSortDir("asc");
    setPage(1);
  }, []);

  const getStatusColor = (status: ProductStatus) => {
    switch (status) {
      case "active": return "green";
      case "draft": return "yellow";
      case "archived": return "gray";
      default: return "gray";
    }
  };

  const getStatusLabel = (status: ProductStatus) => {
    switch (status) {
      case "active": return "Activo";
      case "draft": return "Borrador";
      case "archived": return "Archivado";
      default: return status;
    }
  };

  const renderTable = () => {
    const data = products as ProductListDisplayItem[];
    
    return (
      <Table.Root size="sm">
        <Table.Header>
          <Table.ColumnHeader>Nombre</Table.ColumnHeader>
          <Table.ColumnHeader>SKU</Table.ColumnHeader>
          <Table.ColumnHeader>Categoría</Table.ColumnHeader>
          {mode === "library" && (
            <Table.ColumnHeader>Estado</Table.ColumnHeader>
          )}
          <Table.ColumnHeader textAlign="right">Costo</Table.ColumnHeader>
          <Table.ColumnHeader textAlign="right">Precio Final</Table.ColumnHeader>
          <Table.ColumnHeader textAlign="right">Margen</Table.ColumnHeader>
          <Table.ColumnHeader textAlign="center">Acciones</Table.ColumnHeader>
        </Table.Header>
        <Table.Body>
          {data.map((item) => {
            const isProductListItem = (item: ProductListDisplayItem): item is ProductListItem => 
              'status' in item;
            
            return (
              <Table.Row key={item.id}>
                <Table.Cell>{item.name}</Table.Cell>
                <Table.Cell>{item.sku || "-"}</Table.Cell>
                <Table.Cell>{item.category_name || "-"}</Table.Cell>
                {mode === "library" && isProductListItem(item) && (
                  <Table.Cell>
                    <Text color={`${getStatusColor(item.status)}.fg`} fontWeight="medium">
                      {getStatusLabel(item.status)}
                    </Text>
                  </Table.Cell>
                )}
                <Table.Cell textAlign="right">{item.product_total_cost}</Table.Cell>
                <Table.Cell textAlign="right">{item.final_sale_price}</Table.Cell>
                <Table.Cell textAlign="right">{item.margin_percent}</Table.Cell>
                <Table.Cell textAlign="center">
                  <IconButton
                    size="sm"
                    variant="ghost"
                    aria-label="Ver detalles"
                    onClick={() => window.open(`/admin/calculadora/productos/${item.id}`, "_blank")}
                  >
                    👁️
                  </IconButton>
                </Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>
      </Table.Root>
    );
  };

  const totalPages = Math.ceil(total / pageSize);

  if (loading && page === 1) {
    return (
      <Flex justify="center" align="center" minH="400px">
        <Spinner size="xl" />
      </Flex>
    );
  }

  return (
    <Flex direction="column" gap={4}>
      {/* Search and Filters */}
      <Flex direction={{ base: "column", lg: "row" }} gap={4} p={4} bg="bg.subtle" borderRadius="md" align="end">
        <Flex direction="column" flex={1}>
          <Text fontSize="sm" mb={1}>Búsqueda</Text>
          <Flex gap={2}>
            <Input
              placeholder="Buscar por nombre o SKU"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            <Button variant="outline" onClick={handleSearch}>Buscar</Button>
          </Flex>
        </Flex>

        <Button variant="outline" onClick={clearFilters}>
          Limpiar filtros
        </Button>
      </Flex>

      {/* Table */}
      <Flex direction="column" gap={4}>
        {renderTable()}
      </Flex>

      {/* Pagination */}
      {totalPages > 1 && (
        <Flex justify="center" gap={2} mt={4}>
          <Button
            variant="outline"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Anterior
          </Button>
          <Text py={2} px={4} bg="bg.muted" borderRadius="md">
            Página {page} de {totalPages}
          </Text>
          <Button
            variant="outline"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Siguiente
          </Button>
        </Flex>
      )}
    </Flex>
  );
}