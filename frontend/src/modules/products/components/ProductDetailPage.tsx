"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Alert,
  Badge,
  Button,
  Flex,
  Heading,
  Table,
  Tabs,
  Text,
} from "@chakra-ui/react";
import { DetailPageSkeleton } from "@/components/ui/skeleton";

import NextLink from "next/link";
import { formatCents, formatQty } from "@/lib/format";
import { toaster } from "@/lib/toaster";
import { useAuth } from "@/contexts/AuthContext";
import { useProductDetail } from "../hooks/useProductDetail";
import { productsService } from "../service";
import type { ProductDetail } from "../types";
import { DeleteProductDialog } from "./DeleteProductDialog";

const DIFFICULTY_LABELS: Record<string, string> = {
  simple: "Simple",
  intermedio: "Intermedio",
  complejo: "Complejo",
};

interface ProductDetailPageProps {
  productId: string;
}

/**
 * Detalle de producto (Fase 5, P4) — /productos/{id}.
 *
 * Las 4 pestañas de la spec: Información · Ingredientes · Preparación ·
 * Costos. El desglose viene derivado del backend en cada lectura (RF-P3-04):
 * el cliente no recalcula nada ni cachea precios.
 *
 * Producto incompleto (RF-P4-07): las líneas sin precio se marcan y la
 * pestaña Costos explica qué insumos lo bloquean, en lugar de mostrar un
 * total engañoso.
 *
 * Editar y Eliminar son solo para admin (RBAC de mutaciones).
 */
export function ProductDetailPage({ productId }: ProductDetailPageProps) {
  const router = useRouter();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const { product, loading, error } = useProductDetail(productId);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      const impact = await productsService.remove(productId);
      toaster.create({
        title: "Producto eliminado",
        description:
          impact && impact.impacted_orders > 0
            ? `Queda en ${impact.impacted_orders} pedidos históricos.`
            : undefined,
        type: "success",
      });
      router.push("/productos");
    } catch (e) {
      toaster.create({
        title: "No se pudo eliminar",
        description: e instanceof Error ? e.message : undefined,
        type: "error",
      });
      setConfirmDelete(false);
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return <DetailPageSkeleton tabs={3} />;
  }

  if (error || !product) {
    return (
      <Flex direction="column" gap={4}>
        <Alert.Root status="error">
          <Alert.Content>
            <Alert.Title>No se pudo cargar el producto</Alert.Title>
            <Alert.Description>
              {error ?? "El producto no existe o fue eliminado."}
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>
        <Button variant="outline" asChild alignSelf="flex-start">
          <NextLink href="/productos">Volver a productos</NextLink>
        </Button>
      </Flex>
    );
  }

  return (
    <Flex direction="column" gap={5}>
      <Button variant="ghost" size="sm" asChild alignSelf="flex-start">
        <NextLink href="/productos">← Productos</NextLink>
      </Button>

      <Flex align="flex-start" justify="space-between" gap={4} flexWrap="wrap">
        <Flex direction="column" gap={1}>
          <Heading fontSize="2xl">{product.name}</Heading>
          <Flex gap={2} align="center" flexWrap="wrap">
            <Badge variant="subtle">{product.category}</Badge>
            {!product.complete ? (
              <Badge colorPalette="orange">sin precio</Badge>
            ) : null}
          </Flex>
        </Flex>
        {isAdmin ? (
          <Flex gap={2}>
            <Button variant="outline" asChild>
              <NextLink href={`/productos/${product.id}/edit`}>Editar</NextLink>
            </Button>
            <Button
              variant="ghost"
              colorPalette="red"
              onClick={() => setConfirmDelete(true)}
            >
              Eliminar
            </Button>
          </Flex>
        ) : null}
      </Flex>

      <Tabs.Root defaultValue="info" variant="line">
        <Tabs.List overflowX="auto">
          <Tabs.Trigger value="info">Información</Tabs.Trigger>
          <Tabs.Trigger value="recipe">Ingredientes</Tabs.Trigger>
          <Tabs.Trigger value="prep">Preparación</Tabs.Trigger>
          <Tabs.Trigger value="costs">Costos</Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="info" pt={4}>
          <InfoTab product={product} />
        </Tabs.Content>
        <Tabs.Content value="recipe" pt={4}>
          <RecipeTab product={product} />
        </Tabs.Content>
        <Tabs.Content value="prep" pt={4}>
          <PrepTab product={product} />
        </Tabs.Content>
        <Tabs.Content value="costs" pt={4}>
          <CostsTab product={product} />
        </Tabs.Content>
      </Tabs.Root>

      <DeleteProductDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        productName={product.name}
        deleting={deleting}
        onConfirm={handleDelete}
      />
    </Flex>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <Flex direction="column" gap={0.5}>
      <Text fontSize="xs" color="fg.muted">
        {label}
      </Text>
      <Text>{value}</Text>
    </Flex>
  );
}

function InfoTab({ product }: { product: ProductDetail }) {
  return (
    <Flex direction="column" gap={4}>
      <Field
        label="Descripción"
        value={product.description || "Sin descripción"}
      />
      <Field label="Categoría" value={product.category} />
      <Field label="Porciones" value={String(product.servings)} />
    </Flex>
  );
}

function RecipeTab({ product }: { product: ProductDetail }) {
  return (
    <Flex direction="column" gap={3}>
      <Text color="fg.muted" fontSize="sm">
        Cantidades en la unidad de cada línea; el motor las convierte a la
        unidad de compra del insumo.
      </Text>
      <Table.ScrollArea borderWidth="1px" rounded="md">
        <Table.Root size="sm">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>Insumo</Table.ColumnHeader>
              <Table.ColumnHeader>Cantidad</Table.ColumnHeader>
              <Table.ColumnHeader textAlign="end">Costo</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {product.recipe.map((item) => (
              <Table.Row key={item.ingredient_id}>
                <Table.Cell>
                  <Flex gap={2} align="center">
                    <Text>{item.ingredient_name}</Text>
                    {item.missing ? (
                      <Badge colorPalette="orange" size="xs">
                        sin precio
                      </Badge>
                    ) : null}
                  </Flex>
                </Table.Cell>
                <Table.Cell>{formatQty(item.qty, item.unit)}</Table.Cell>
                <Table.Cell
                  textAlign="end"
                  fontVariantNumeric="tabular-nums"
                  color={item.missing ? "fg.muted" : undefined}
                >
                  {item.line_cost !== null ? formatCents(item.line_cost) : "—"}
                </Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      </Table.ScrollArea>
    </Flex>
  );
}

function PrepTab({ product }: { product: ProductDetail }) {
  return (
    <Flex direction="column" gap={4}>
      <Field
        label="Tiempo de preparación"
        value={`${product.prep_time_min} min`}
      />
      <Field label="Porciones" value={String(product.servings)} />
      <Field
        label="Dificultad"
        value={DIFFICULTY_LABELS[product.difficulty] ?? product.difficulty}
      />
      <Text fontSize="sm" color="fg.muted">
        La mano de obra se deriva del tiempo de preparación según la
        configuración del negocio (hora de trabajo cargada en Configuración).
      </Text>
    </Flex>
  );
}

function CostsTab({ product }: { product: ProductDetail }) {
  if (!product.complete || !product.price) {
    return (
      <Alert.Root status="warning">
        <Alert.Content>
          <Alert.Title>Precio incompleto</Alert.Title>
          <Alert.Description>
            {product.missing_ingredients.length > 0
              ? `Estos insumos no tienen precio: ${product.missing_ingredients.join(", ")}.`
              : "La receta tiene insumos sin precio."}{" "}
            Cargá su precio en Ingredientes para ver el costo real.
          </Alert.Description>
        </Alert.Content>
      </Alert.Root>
    );
  }

  const price = product.price;
  const rows: Array<{ label: string; value: string }> = [
    { label: "Materiales", value: formatCents(price.materials) },
    { label: "Merma", value: formatCents(price.waste) },
    {
      label: "Materiales con merma",
      value: formatCents(price.materials_con_merma),
    },
    { label: "Mano de obra", value: formatCents(price.labor) },
    { label: "Gas / energía", value: formatCents(price.gas) },
    { label: "Subtotal", value: formatCents(price.base) },
    { label: "Margen", value: `${Number(price.margin_pct)}%` },
  ];

  return (
    <Flex direction="column" gap={4}>
      <Table.Root size="sm">
        <Table.Body>
          {rows.map((row) => (
            <Table.Row key={row.label}>
              <Table.Cell color="fg.muted">{row.label}</Table.Cell>
              <Table.Cell
                textAlign="end"
                fontVariantNumeric="tabular-nums"
                w="40%"
              >
                {row.value}
              </Table.Cell>
            </Table.Row>
          ))}
          <Table.Row>
            <Table.Cell fontWeight="600">Precio final</Table.Cell>
            <Table.Cell
              textAlign="end"
              fontSize="xl"
              fontWeight="600"
              fontVariantNumeric="tabular-nums"
            >
              {formatCents(price.rounded)}
            </Table.Cell>
          </Table.Row>
        </Table.Body>
      </Table.Root>

      {product.servings > 1 && product.price_per_serving !== null ? (
        <Flex justify="space-between" color="fg.muted">
          <Text>Precio por porción</Text>
          <Text fontVariantNumeric="tabular-nums">
            {formatCents(product.price_per_serving)}
          </Text>
        </Flex>
      ) : null}

      {Number(price.final) !== Number(price.rounded) ? (
        <Text fontSize="sm" color="fg.muted">
          Redondeo aplicado: de {formatCents(price.final)} a{" "}
          {formatCents(price.rounded)}.
        </Text>
      ) : null}
    </Flex>
  );
}
