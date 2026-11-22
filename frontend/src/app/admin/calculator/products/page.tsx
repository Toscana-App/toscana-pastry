"use client";

import { useState } from "react";
import NextLink from "next/link";
import { Button, Flex, Heading, Tabs } from "@chakra-ui/react";
import ProductList from "@/components/calc/ProductList";
import Dashboard from "@/components/calc/Dashboard";

export default function ProductsPage() {
  const [activeTab, setActiveTab] = useState("library");

  return (
    <Flex direction="column" gap={6}>
      <Flex align="center" gap={4} mb={2} wrap="wrap">
        <Heading as="h1" fontSize="2xl" textWrap="balance" flex="1">
          Calculadora de costos
        </Heading>
        <Button colorPalette="brand" asChild>
          <NextLink href="/admin/calculator/products/new">
            + Nuevo producto
          </NextLink>
        </Button>
      </Flex>
      <Tabs.Root
        value={activeTab}
        onValueChange={(details) => setActiveTab(details.value)}
      >
        <Tabs.List>
          <Tabs.Trigger value="library">Biblioteca de Productos</Tabs.Trigger>
          <Tabs.Trigger value="price-list">Lista de Precios</Tabs.Trigger>
          <Tabs.Trigger value="dashboard">Dashboard</Tabs.Trigger>
        </Tabs.List>

      <Tabs.Content value="library">
        <ProductList mode="library" />
      </Tabs.Content>

      <Tabs.Content value="price-list">
        <ProductList mode="price-list" />
      </Tabs.Content>

      <Tabs.Content value="dashboard">
        <Dashboard />
      </Tabs.Content>
      </Tabs.Root>
    </Flex>
  );
}