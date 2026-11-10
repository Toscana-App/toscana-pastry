"use client";

import { useState } from "react";
import { Container, Flex, Heading, Tabs } from "@chakra-ui/react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import CategoryAbm from "@/components/calc/CategoryAbm";
import DefaultCostsAbm from "@/components/calc/DefaultCostsAbm";
import GeneralSettingsForm from "@/components/calc/GeneralSettingsForm";
import SupplierAbm from "@/components/calc/SupplierAbm";

type CalcTabId =
  | "general"
  | "material-categories"
  | "product-categories"
  | "suppliers"
  | "default-costs";

const CALC_TABS: { id: CalcTabId; label: string }[] = [
  { id: "general", label: "General" },
  { id: "material-categories", label: "Categorías de materiales" },
  { id: "product-categories", label: "Categorías de productos" },
  { id: "suppliers", label: "Proveedores" },
  { id: "default-costs", label: "Costos por defecto" },
];

export default function CalculatorConfigPage() {
  const [activeTab, setActiveTab] = useState<CalcTabId>("general");
  const [visited, setVisited] = useState<Set<CalcTabId>>(
    () => new Set<CalcTabId>(["general"])
  );

  function handleTabChange(details: { value: string }) {
    const tab = details.value as CalcTabId;
    setActiveTab(tab);
    setVisited((prev) =>
      prev.has(tab) ? prev : new Set(prev).add(tab)
    );
  }

  return (
    <ProtectedRoute requiredRole="admin">
      <Container py={10} maxW="container.md">
        <Flex direction="column" gap={6}>
          <Heading fontSize="3xl" textWrap="balance">Configuración de la calculadora</Heading>
          <Tabs.Root value={activeTab} onValueChange={handleTabChange}>
            <Tabs.List>
              {CALC_TABS.map((tab) => (
                <Tabs.Trigger key={tab.id} value={tab.id}>
                  {tab.label}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
            <Tabs.Content value="general">
              {visited.has("general") && <GeneralSettingsForm />}
            </Tabs.Content>
            <Tabs.Content value="material-categories">
              {visited.has("material-categories") && (
                <CategoryAbm
                  endpoint="material-categories"
                  title="Categorías de materiales"
                />
              )}
            </Tabs.Content>
            <Tabs.Content value="product-categories">
              {visited.has("product-categories") && (
                <CategoryAbm
                  endpoint="product-categories"
                  title="Categorías de productos"
                />
              )}
            </Tabs.Content>
            <Tabs.Content value="suppliers">
              {visited.has("suppliers") && <SupplierAbm />}
            </Tabs.Content>
            <Tabs.Content value="default-costs">
              {visited.has("default-costs") && <DefaultCostsAbm />}
            </Tabs.Content>
          </Tabs.Root>
        </Flex>
      </Container>
    </ProtectedRoute>
  );
}
