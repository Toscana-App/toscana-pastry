"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import NextLink from "next/link";
import {
  Alert,
  Button,
  Flex,
  Heading,
  Tabs,
  Text,
  FormatNumber,
} from "@chakra-ui/react";
import { DetailPageSkeleton } from "@/components/ui/skeleton";

import { centsToPesos, formatQty } from "@/lib/format";
import { toaster } from "@/lib/toaster";
import { useIngredientDetail } from "../hooks/useIngredientDetail";
import type { DeleteImpact } from "../types";
import { DeleteIngredientDialog } from "./DeleteIngredientDialog";
import { MovementsList } from "./MovementsList";
import { StockBadge } from "./StockBadge";
import { StockDrawer } from "./StockDrawer";

interface IngredientDetailPageProps {
  id: string;
}

function DataRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Flex justify="space-between" gap={4} px={4} py={3} flexWrap="wrap">
      <Text color="fg.muted">{label}</Text>
      <Text fontWeight="500" fontVariantNumeric="tabular-nums">{value}</Text>
    </Flex>
  );
}

export function IngredientDetailPage({ id }: IngredientDetailPageProps) {
  const router = useRouter();
  const { ingredient, movements, loading, error, adjustStock, remove } =
    useIngredientDetail(id);

  const [stockOpen, setStockOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [impact, setImpact] = useState<DeleteImpact | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      const result = await remove();
      if (result === "deleted") {
        toaster.create({ title: "Ingredient deleted", type: "success" });
        router.push("/admin/ingredients");
      } else {
        setImpact(result);
      }
    } catch (e) {
      toaster.create({
        title: "No se pudo eliminar",
        description: e instanceof Error ? e.message : undefined,
        type: "error",
      });
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return <DetailPageSkeleton tabs={2} />;
  }

  if (error || !ingredient) {
    return (
      <Flex direction="column" gap={4}>
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Title>No se pudo cargar el ingrediente</Alert.Title>
            <Alert.Description>{error ?? "No existe"}</Alert.Description>
          </Alert.Content>
        </Alert.Root>
        <Button asChild variant="outline" alignSelf="flex-start">
          <NextLink href="/admin/ingredients">Volver a la lista</NextLink>
        </Button>
      </Flex>
    );
  }

  return (
    <Flex direction="column" gap={6}>
      <Button asChild variant="ghost" size="sm" alignSelf="flex-start" px={0}>
        <NextLink href="/admin/ingredients">← Ingredientes</NextLink>
      </Button>

      <Flex justify="space-between" align="flex-start" gap={4} flexWrap="wrap">
        <Flex direction="column" gap={2}>
          <Heading fontSize="2xl" textWrap="balance" overflowWrap="anywhere">{ingredient.name}</Heading>
          <StockBadge
            status={ingredient.status}
            stockQty={ingredient.stock_qty}
            unit={ingredient.unit}
          />
        </Flex>
        <Flex gap={3} flexWrap="wrap">
          <Button colorPalette="brand" onClick={() => setStockOpen(true)}>
            Ajustar stock
          </Button>
          <Button asChild variant="outline">
            <NextLink href={`/admin/ingredients/${ingredient.id}/edit`}>Editar</NextLink>
          </Button>
          <Button
            variant="outline"
            colorPalette="red"
            onClick={() => {
              setImpact(null);
              setDeleteOpen(true);
            }}
          >
            Eliminar
          </Button>
        </Flex>
      </Flex>

      <Tabs.Root defaultValue="resumen" variant="line">
        <Tabs.List>
          <Tabs.Trigger value="resumen">Resumen</Tabs.Trigger>
          <Tabs.Trigger value="movimientos">
            Movimientos ({movements.length})
          </Tabs.Trigger>
          <Tabs.Indicator />
        </Tabs.List>

        <Tabs.ContentGroup>
          <Tabs.Content value="resumen" pt={4}>
            <Flex
              direction="column"
              borderWidth="1px"
              borderColor="border"
              rounded="md"
              divideY="1px"
            >
              <DataRow label="Unidad" value={ingredient.unit} />
              <DataRow
                label="Precio por unidad"
                value={<FormatNumber value={centsToPesos(ingredient.price_per_unit)} style="currency" currency="ARS" />}
              />
              <DataRow
                label="Stock actual"
                value={formatQty(ingredient.stock_qty, ingredient.unit)}
              />
              <DataRow
                label="Umbral de stock bajo"
                value={formatQty(ingredient.low_stock_threshold, ingredient.unit)}
              />
            </Flex>
          </Tabs.Content>

          <Tabs.Content value="movimientos" pt={4}>
            <MovementsList movements={movements} />
          </Tabs.Content>
        </Tabs.ContentGroup>
      </Tabs.Root>

      <StockDrawer
        open={stockOpen}
        onOpenChange={setStockOpen}
        ingredientName={ingredient.name}
        unit={ingredient.unit}
        onSubmit={adjustStock}
      />

      <DeleteIngredientDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        ingredientName={ingredient.name}
        impact={impact}
        deleting={deleting}
        onConfirm={handleDelete}
      />
    </Flex>
  );
}
