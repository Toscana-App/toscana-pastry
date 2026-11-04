"use client";

import { useState } from "react";
import { Tabs } from "@chakra-ui/react";
import ProductList from "@/components/calc/ProductList";
import Dashboard from "@/components/calc/Dashboard";

export default function ProductsPage() {
  const [activeTab, setActiveTab] = useState("library");

  return (
    <Tabs.Root value={activeTab} onValueChange={(details) => setActiveTab(details.value)}>
      <Tabs.List>
        <Tabs.Trigger value="library">📚 Biblioteca de Productos</Tabs.Trigger>
        <Tabs.Trigger value="price-list">💰 Lista de Precios</Tabs.Trigger>
        <Tabs.Trigger value="dashboard">📊 Dashboard</Tabs.Trigger>
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
  );
}