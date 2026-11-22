"use client";

import { Box, Heading, SimpleGrid, Text } from "@chakra-ui/react";
import { Chart, useChart } from "@chakra-ui/charts";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DashboardResponse } from "@/types/calc";

const CENTS_PER_PESO = 100;
const CHART_HEIGHT = "16rem";

const currencyOptions: Intl.NumberFormatOptions = {
  style: "currency",
  currency: "ARS",
  notation: "compact",
};

const fullCurrency = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
});

const toPesos = (cents: number) => cents / CENTS_PER_PESO;

const ChartCard = ({
  title,
  description,
  empty,
  children,
}: {
  title: string;
  description: string;
  empty: boolean;
  children: React.ReactNode;
}) => (
  <Box p={4} bg="bg.panel" borderRadius="md" shadow="sm" border="1px solid" borderColor="border">
    <Heading size="md" mb={1}>
      {title}
    </Heading>
    <Text fontSize="sm" color="fg.muted" mb={4}>
      {description}
    </Text>
    {empty ? (
      <Text color="fg.muted" role="status">
        Sin datos para mostrar
      </Text>
    ) : (
      children
    )}
  </Box>
);

function ProductStatusChart({ active, draft }: { active: number; draft: number }) {
  const chart = useChart({
    data: [
      { label: "Activos", total: active, color: "green.solid" },
      { label: "Borrador", total: draft, color: "yellow.solid" },
    ],
  });
  const summary = `Productos: ${active} activos y ${draft} en borrador`;

  return (
    <ChartCard
      title="Productos por estado"
      description="Cantidad de productos activos y en borrador"
      empty={active + draft === 0}
    >
      <Chart.Root height={CHART_HEIGHT} chart={chart} role="img" aria-label={summary}>
        <BarChart data={chart.data} responsive>
          <CartesianGrid stroke={chart.color("border.muted")} vertical={false} />
          <XAxis axisLine={false} tickLine={false} dataKey={chart.key("label")} />
          <YAxis axisLine={false} tickLine={false} allowDecimals={false} />
          <Tooltip cursor={{ fill: chart.color("bg.muted") }} content={<Chart.Tooltip />} />
          <Bar dataKey={chart.key("total")} isAnimationActive={false} radius={4} name="Productos">
            {chart.data.map((item) => (
              <Cell key={item.label} fill={chart.color(item.color)} />
            ))}
          </Bar>
        </BarChart>
      </Chart.Root>
    </ChartCard>
  );
}

function MaterialStatusChart({ active, incomplete }: { active: number; incomplete: number }) {
  const chart = useChart({
    data: [
      { name: "Activos", value: active, color: "blue.solid" },
      { name: "Incompletos", value: incomplete, color: "red.solid" },
    ],
  });
  const summary = `Materiales: ${active} activos y ${incomplete} incompletos`;

  return (
    <ChartCard
      title="Estado de materiales"
      description="Materiales activos frente a incompletos"
      empty={active + incomplete === 0}
    >
      <Chart.Root height={CHART_HEIGHT} chart={chart} role="img" aria-label={summary}>
        <PieChart responsive>
          <Tooltip animationDuration={100} content={<Chart.Tooltip hideLabel />} />
          <Legend content={<Chart.Legend />} />
          <Pie
            data={chart.data}
            dataKey={chart.key("value")}
            nameKey="name"
            innerRadius="55%"
            isAnimationActive={false}
          >
            {chart.data.map((item) => (
              <Cell key={item.name} fill={chart.color(item.color)} />
            ))}
          </Pie>
        </PieChart>
      </Chart.Root>
    </ChartCard>
  );
}

function CostVsPriceChart({ avgCost, avgPrice }: { avgCost: number; avgPrice: number }) {
  const chart = useChart({
    data: [
      { label: "Costo promedio", amount: toPesos(avgCost), color: "purple.solid" },
      { label: "Precio promedio", amount: toPesos(avgPrice), color: "cyan.solid" },
    ],
  });
  const summary = `Costo promedio ${fullCurrency.format(toPesos(avgCost))} frente a precio promedio ${fullCurrency.format(toPesos(avgPrice))}`;

  return (
    <ChartCard
      title="Costo vs. precio promedio"
      description="Costo promedio y precio final promedio por producto activo"
      empty={avgCost === 0 && avgPrice === 0}
    >
      <Chart.Root height={CHART_HEIGHT} chart={chart} role="img" aria-label={summary}>
        <BarChart data={chart.data} responsive>
          <CartesianGrid stroke={chart.color("border.muted")} vertical={false} />
          <XAxis axisLine={false} tickLine={false} dataKey={chart.key("label")} />
          <YAxis
            axisLine={false}
            tickLine={false}
            tickFormatter={chart.formatNumber(currencyOptions)}
          />
          <Tooltip
            cursor={{ fill: chart.color("bg.muted") }}
            content={<Chart.Tooltip formatter={(value) => fullCurrency.format(Number(value))} />}
          />
          <Bar dataKey={chart.key("amount")} isAnimationActive={false} radius={4} name="Monto">
            {chart.data.map((item) => (
              <Cell key={item.label} fill={chart.color(item.color)} />
            ))}
          </Bar>
        </BarChart>
      </Chart.Root>
    </ChartCard>
  );
}

function TopPriceChart({ items }: { items: DashboardResponse["top_by_price"] }) {
  const chart = useChart({
    data: items.map((item) => ({ name: item.name, price: toPesos(item.final_sale_price) })),
    series: [{ name: "price", color: "teal.solid" }],
  });
  const summary = `Precio final de los ${items.length} productos con mayor precio: ${chart.data
    .map((item) => `${item.name} ${fullCurrency.format(item.price)}`)
    .join(", ")}`;

  return (
    <ChartCard
      title="Mayor precio final"
      description="Precio final de los productos mejor posicionados"
      empty={items.length === 0}
    >
      <Chart.Root height={CHART_HEIGHT} chart={chart} role="img" aria-label={summary}>
        <BarChart layout="vertical" data={chart.data} responsive>
          <CartesianGrid stroke={chart.color("border.muted")} horizontal={false} />
          <XAxis
            type="number"
            axisLine={false}
            tickLine={false}
            tickFormatter={chart.formatNumber(currencyOptions)}
          />
          <YAxis type="category" dataKey={chart.key("name")} width={100} axisLine={false} tickLine={false} />
          <Tooltip
            cursor={{ fill: chart.color("bg.muted") }}
            content={<Chart.Tooltip formatter={(value) => fullCurrency.format(Number(value))} />}
          />
          <Bar
            dataKey={chart.key("price")}
            fill={chart.color("teal.solid")}
            isAnimationActive={false}
            radius={4}
            name="Precio final"
          />
        </BarChart>
      </Chart.Root>
    </ChartCard>
  );
}

function LowestMarginChart({ items }: { items: DashboardResponse["bottom_by_margin"] }) {
  const chart = useChart({
    data: items.map((item) => ({
      name: item.name,
      margin: parseFloat(item.margin_percent) || 0,
    })),
    series: [{ name: "margin", color: "orange.solid" }],
  });
  const summary = `Margen de los ${items.length} productos con menor margen: ${chart.data
    .map((item) => `${item.name} ${item.margin}%`)
    .join(", ")}`;

  return (
    <ChartCard
      title="Menor margen"
      description="Margen porcentual de los productos que requieren atención"
      empty={items.length === 0}
    >
      <Chart.Root height={CHART_HEIGHT} chart={chart} role="img" aria-label={summary}>
        <BarChart layout="vertical" data={chart.data} responsive>
          <CartesianGrid stroke={chart.color("border.muted")} horizontal={false} />
          <XAxis
            type="number"
            axisLine={false}
            tickLine={false}
            tickFormatter={(value) => `${value}%`}
          />
          <YAxis type="category" dataKey={chart.key("name")} width={100} axisLine={false} tickLine={false} />
          <Tooltip
            cursor={{ fill: chart.color("bg.muted") }}
            content={<Chart.Tooltip formatter={(value) => `${value}%`} />}
          />
          <Bar
            dataKey={chart.key("margin")}
            fill={chart.color("orange.solid")}
            isAnimationActive={false}
            radius={4}
            name="Margen"
          />
        </BarChart>
      </Chart.Root>
    </ChartCard>
  );
}

export default function DashboardCharts({ dashboard }: { dashboard: DashboardResponse }) {
  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
      <ProductStatusChart active={dashboard.active_products} draft={dashboard.draft_products} />
      <MaterialStatusChart
        active={dashboard.active_materials}
        incomplete={dashboard.incomplete_materials}
      />
      <CostVsPriceChart avgCost={dashboard.avg_product_cost} avgPrice={dashboard.avg_final_price} />
      <TopPriceChart items={dashboard.top_by_price} />
      <LowestMarginChart items={dashboard.bottom_by_margin} />
    </SimpleGrid>
  );
}
