"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Flex,
  SimpleGrid,
  Box,
  Text,
  Heading,
  Table,
  Badge,
  IconButton,
} from "@chakra-ui/react";
import { CalcDashboardSkeleton } from "@/components/ui/skeleton";

import { calcProductsService } from "@/services/calcProductsService";
import { toaster } from "@/lib/toaster";
import type { DashboardResponse, DashboardTopItem, DashboardBottomItem } from "@/types/calc";

// KPI Card component (defined outside render)
const KPICard = ({ title, value, subtitle, color = "gray" }: {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: string;
}) => (
  <Box p={4} bg="white" borderRadius="md" shadow="sm" border="1px solid" borderColor="gray.200">
    <Text fontSize="sm" color="gray.600" fontWeight="medium" mb={2}>
      {title}
    </Text>
    <Heading size="lg" color={`${color}.900`}>
      {typeof value === "number" ? value.toLocaleString() : value}
    </Heading>
    {subtitle && (
      <Text fontSize="sm" color="gray.500" mt={1}>
        {subtitle}
      </Text>
    )}
  </Box>
);

// Section Card component (defined outside render)
const SectionCard = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <Box p={4} bg="white" borderRadius="md" shadow="sm" border="1px solid" borderColor="gray.200">
    <Heading size="md" mb={4}>
      {title}
    </Heading>
    {children}
  </Box>
);

export default function Dashboard() {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    calcProductsService.getDashboard()
      .then(setDashboard)
      .catch(() => {
        toaster.create({ title: "Error cargando dashboard", type: "error" });
      })
      .finally(() => setLoading(false));
  }, []);

  const handleViewProduct = useCallback((productId: string) => {
    // Secure navigation to product edit page
    window.location.href = `/admin/calculadora/productos/${productId}`;
  }, []);

  if (loading) {
    return <CalcDashboardSkeleton />;
  }

  if (!dashboard) {
    return <Text color="red.500">Error cargando dashboard</Text>;
  }

  return (
    <Flex direction="column" gap={6}>
      {/* KPI Cards */}
      <SimpleGrid columns={{ base: 1, sm: 2, md: 4 }} gap={4}>
        <KPICard
          title="Productos Activos"
          value={dashboard.active_products}
          subtitle="Artículos disponibles para venta"
          color="green"
        />
        <KPICard
          title="Productos Borrador"
          value={dashboard.draft_products}
          subtitle="No están disponibles aún"
          color="yellow"
        />
        <KPICard
          title="Materiales Activos"
          value={dashboard.active_materials}
          subtitle="Componentes disponibles"
          color="blue"
        />
        <KPICard
          title="Materiales Incompletos"
          value={dashboard.incomplete_materials}
          subtitle="Necesitan atención"
          color="red"
        />
        <KPICard
          title="Costo Promedio"
          value={dashboard.avg_product_cost}
          subtitle="Por producto"
          color="purple"
        />
        <KPICard
          title="Precio Promedio"
          value={dashboard.avg_final_price}
          subtitle="Por producto"
          color="cyan"
        />
      </SimpleGrid>

      {/* Top and Bottom Items */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
        {/* Top by Price */}
        <SectionCard title="🏆 Productos con Mayor Precio Final">
          <Table.Root size="sm">
            <Table.Header>
              <Table.ColumnHeader>Producto</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="right">Precio Final</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="right">Margen</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="center">Acciones</Table.ColumnHeader>
            </Table.Header>
            <Table.Body>
              {dashboard.top_by_price.map((item: DashboardTopItem) => {
                const marginNum = parseFloat(item.margin_percent) || 0;
                const badgeColor = marginNum > 30 ? "green" : marginNum > 15 ? "blue" : marginNum > 0 ? "yellow" : "red";
                const badgeText = marginNum > 30 ? "Alto" : marginNum > 15 ? "Bueno" : marginNum > 0 ? "Regular" : "Bajo";

                return (
                  <Table.Row key={item.id}>
                    <Table.Cell fontWeight="medium">{item.name}</Table.Cell>
                    <Table.Cell textAlign="right">{item.final_sale_price}</Table.Cell>
                    <Table.Cell textAlign="right">
                      <Badge colorPalette={badgeColor} variant="subtle">
                        {badgeText}
                      </Badge>
                      <Text fontSize="sm" mt={1}>{item.margin_percent}</Text>
                    </Table.Cell>
                    <Table.Cell textAlign="center">
                      <IconButton
                        size="sm"
                        variant="ghost"
                        aria-label="Ver producto"
                        onClick={() => handleViewProduct(item.id)}
                      >
                        👁️
                      </IconButton>
                    </Table.Cell>
                  </Table.Row>
                );
              })}
            </Table.Body>
          </Table.Root>
        </SectionCard>

        {/* Bottom by Margin */}
        <SectionCard title="📉 Productos con Menor Margen">
          <Table.Root size="sm">
            <Table.Header>
              <Table.ColumnHeader>Producto</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="right">Costo Total</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="right">Margen</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="center">Acciones</Table.ColumnHeader>
            </Table.Header>
            <Table.Body>
              {dashboard.bottom_by_margin.map((item: DashboardBottomItem) => {
                const marginNum = parseFloat(item.margin_percent) || 0;
                const badgeColor = marginNum > 30 ? "green" : marginNum > 15 ? "blue" : marginNum > 0 ? "yellow" : "red";
                const badgeText = marginNum > 30 ? "Excelente" : marginNum > 15 ? "Bueno" : marginNum > 0 ? "Regular" : "Requiere atención";

                return (
                  <Table.Row key={item.id}>
                    <Table.Cell fontWeight="medium">{item.name}</Table.Cell>
                    <Table.Cell textAlign="right">{item.product_total_cost}</Table.Cell>
                    <Table.Cell textAlign="right">
                      <Badge colorPalette={badgeColor} variant="subtle">
                        {badgeText}
                      </Badge>
                      <Text fontSize="sm" mt={1}>{item.margin_percent}</Text>
                    </Table.Cell>
                    <Table.Cell textAlign="center">
                      <IconButton
                        size="sm"
                        variant="ghost"
                        aria-label="Ver producto"
                        onClick={() => handleViewProduct(item.id)}
                      >
                        👁️
                      </IconButton>
                    </Table.Cell>
                  </Table.Row>
                );
              })}
            </Table.Body>
          </Table.Root>
        </SectionCard>
      </SimpleGrid>
    </Flex>
  );
}