"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Button,
  Flex,
  Input,
  Textarea,
  Select,
  Spinner,
  Heading,
  Text as UIText,
} from "@chakra-ui/react";
import { createListCollection } from "@ark-ui/react";
import { calcProductsService } from "@/services/calcProductsService";
import { calcMaterialsService } from "@/services/calcMaterialsService";
import { calcSettingsService } from "@/services/calcSettingsService";
import ProductLines from "./ProductLines";
import { toaster } from "@/lib/toaster";
import { centsToPesos, formatCents } from "@/lib/format";
import type {
  Category,
  Material,
  Product,
  ProductCostsResponse,
  ProductCreatePayload,
  ProductDetail,
  ProductUpdatePayload,
  ProductLineMaterialIn,
  ProductLineLaborIn,
  ProductLineExtraCostIn,
  ProductStatus,
  CategoryListResponse,
} from "@/types/calc";

// Hidratación (F2): el GET de detalle devuelve las líneas a nivel
// superior (sin envoltorio product_lines) y los montos en int de
// centavos; los inputs del editor trabajan en pesos (string).
function mapDetailLines(detail: ProductDetail) {
  return {
    materialLines: detail.materials.map((line) => ({
      material_id: line.material_id,
      quantity_used: line.quantity_used,
    })),
    laborLines: detail.labor.map((line) => ({
      activity_name: line.activity_name,
      hourly_rate: String(centsToPesos(line.hourly_rate)),
      minutes_required: line.minutes_required,
    })),
    extraCostLines: detail.extra_costs.map((line) => ({
      concept_name: line.concept_name,
      unit_cost: String(centsToPesos(line.unit_cost)),
      quantity: line.quantity,
    })),
  };
}

interface ProductEditorProps {
  initial?: Product;
  onSave?: (product: Product) => void;
}

export default function ProductEditor({ initial, onSave }: ProductEditorProps) {
  const router = useRouter();

  const [name, setName] = useState(initial?.name || "");
  const [sku, setSku] = useState(initial?.sku || "");
  const [categoryId, setCategoryId] = useState<string>(initial?.category_id || "");
  const [description, setDescription] = useState(initial?.description || "");
  const [notes, setNotes] = useState(initial?.notes || "");
  const [marginPercent, setMarginPercent] = useState(initial?.margin_percent || "");
  const [discountPercent, setDiscountPercent] = useState(initial?.discount_percent || "");
  const [taxPercent, setTaxPercent] = useState(initial?.tax_percent || "");
  const [status, setStatus] = useState<ProductStatus>(initial?.status || "draft");

  const [saving, setSaving] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [recalculating, setRecalculating] = useState(false);

  const [materials, setMaterials] = useState<Material[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [materialLines, setMaterialLines] = useState<ProductLineMaterialIn[]>([]);
  const [laborLines, setLaborLines] = useState<ProductLineLaborIn[]>([]);
  const [extraCostLines, setExtraCostLines] = useState<ProductLineExtraCostIn[]>([]);

  const [showPreview, setShowPreview] = useState(false);
  // F3: tras crear, el editor queda en modo edición con el id recién
  // creado (no volver al listado). `costs` alimenta el panel de costos.
  const [savedId, setSavedId] = useState<string | null>(initial?.id || null);
  const [costs, setCosts] = useState<ProductCostsResponse | null>(null);

  const categoryCollection = createListCollection({
    items: categories.map(c => ({ value: c.id, label: c.name }))
  });

  const statusCollection = createListCollection({
    items: [
      { value: "draft", label: "Borrador" },
      { value: "active", label: "Activo" },
      { value: "archived", label: "Archivado" },
    ],
  });

  useEffect(() => {
    // Fetch categories
    calcSettingsService.listCategories("product-categories")
      .then((response: CategoryListResponse) => setCategories(response.items))
      .catch(() => {
        toaster.create({ title: "Error cargando categorías", type: "error" });
      });

    // Fetch materials for the lines
    calcMaterialsService.listMaterials({ status: "active" })
      .then(response => setMaterials(response.items))
      .catch(() => {
        toaster.create({ title: "Error cargando materiales", type: "error" });
      });

    // If editing, fetch product data (GET detail: lineas a nivel
    // superior, montos en int de centavos).
    if (initial?.id) {
      calcProductsService.getProduct(initial.id)
        .then((productData: ProductDetail) => {
          setSavedId(productData.product.id);
          setCosts(productData.costs);
          setName(productData.product.name);
          setSku(productData.product.sku || "");
          setCategoryId(productData.product.category_id || "");
          setDescription(productData.product.description || "");
          setNotes(productData.product.notes || "");
          setMarginPercent(productData.product.margin_percent);
          setDiscountPercent(productData.product.discount_percent);
          setTaxPercent(productData.product.tax_percent);
          setStatus(productData.product.status as ProductStatus);

          const lines = mapDetailLines(productData);
          setMaterialLines(lines.materialLines);
          setLaborLines(lines.laborLines);
          setExtraCostLines(lines.extraCostLines);
        })
        .catch(() => {
          toaster.create({ title: "Error cargando producto", type: "error" });
          router.back();
        })
        .finally(() => setFetching(false));
    }
  }, [initial?.id, router]);

  const handleSave = async () => {
    if (!name.trim()) {
      toaster.create({ title: "El nombre es requerido", type: "warning" });
      return;
    }

    setSaving(true);
    try {
      const payload: ProductCreatePayload | ProductUpdatePayload = {
        name: name.trim(),
        sku: sku.trim() || undefined,
        category_id: categoryId || undefined,
        description: description.trim() || undefined,
        notes: notes.trim() || undefined,
        margin_percent: marginPercent || undefined,
        discount_percent: discountPercent || undefined,
        tax_percent: taxPercent || undefined,
        status,
        materials: materialLines,
        labor: laborLines,
        extra_costs: extraCostLines,
      };

      if (savedId) {
        // F3: update — quedarse en el editor, refrescar costos y ofrecer
        // "Ver" en el toast.
        const result = await calcProductsService.updateProduct(savedId, payload as ProductUpdatePayload);
        setCosts(result.costs);
        onSave?.(result.product);
        toaster.create({
          title: "Producto actualizado exitosamente",
          type: "success",
          action: {
            label: "Ver",
            onClick: () => router.push(`/admin/calculator/products/${savedId}`),
          },
        });
      } else {
        // F3: create — no volver al listado; el editor pasa a modo
        // edición con el id recién creado.
        const result = await calcProductsService.createProduct(payload as ProductCreatePayload);
        setSavedId(result.product.id);
        setCosts(result.costs);
        setMarginPercent(result.product.margin_percent);
        setDiscountPercent(result.product.discount_percent);
        setTaxPercent(result.product.tax_percent);
        setStatus(result.product.status as ProductStatus);
        onSave?.(result.product);
        toaster.create({ title: "Producto creado exitosamente", type: "success" });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Error guardando producto";
      toaster.create({ title: message, type: "error" });
    } finally {
      setSaving(false);
    }
  };

  const handleRecalculate = async () => {
    if (!savedId) return;
    try {
      setRecalculating(true);
      const result = await calcProductsService.recalculateProduct(savedId);
      setCosts(result.costs);
      setMarginPercent(result.product.margin_percent);
      setDiscountPercent(result.product.discount_percent);
      setTaxPercent(result.product.tax_percent);
      setStatus(result.product.status as ProductStatus);
      toaster.create({ title: "Precios recalculados", type: "success" });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Error recalculando precios";
      toaster.create({ title: message, type: "error" });
    } finally {
      setRecalculating(false);
    }
  };

  const handleLinesChange = (
    materials: ProductLineMaterialIn[],
    labor: ProductLineLaborIn[],
    extraCosts: ProductLineExtraCostIn[]
  ) => {
    setMaterialLines(materials);
    setLaborLines(labor);
    setExtraCostLines(extraCosts);
  };

  if (fetching) {
    return (
      <Flex justify="center" align="center" minH="400px">
        <Spinner size="xl" />
      </Flex>
    );
  }

  return (
    <Flex direction="column" gap={6} maxW="1200px" mx="auto" p={6}>
      <Flex justify="space-between" align="center">
        <Heading as="h1" size="xl">
          {initial?.id ? "Editar Producto" : "Nuevo Producto"}
        </Heading>
        <Button variant="ghost" onClick={() => router.back()}>
          Cancelar
        </Button>
      </Flex>

      <Flex direction={{ base: "column", lg: "row" }} gap={6}>
        <Flex direction="column" gap={4} flex={1}>
          <Heading as="h2" size="md">Información Básica</Heading>

          <Flex direction="column" gap={3}>
            <Flex direction={{ base: "column", sm: "row" }} gap={3}>
              <Flex direction="column" flex={1}>
                <UIText fontSize="sm" mb={1}>Nombre *</UIText>
                <Input
                  placeholder="Nombre del producto"
                  maxLength={120}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </Flex>
              <Flex direction="column" flex={1}>
                <UIText fontSize="sm" mb={1}>SKU</UIText>
                <Input
                  placeholder="Código de producto (opcional)"
                  maxLength={40}
                  value={sku}
                  onChange={(e) => setSku(e.target.value)}
                />
              </Flex>
            </Flex>

            <Flex direction={{ base: "column", sm: "row" }} gap={3}>
              <Flex direction="column" flex={1}>
                <UIText fontSize="sm" mb={1}>Categoría</UIText>
                <Select.Root
                  collection={categoryCollection}
                  value={[categoryId]}
                  onValueChange={(details) => {
                    const next = details.value[0];
                    if (next) setCategoryId(next);
                  }}
                >
                  <Select.Trigger>
                    <Select.ValueText placeholder="_placeholder" />
                  </Select.Trigger>
                  <Select.Positioner>
                    <Select.Content>
                      {categories.map(c => (
                        <Select.Item key={c.id} item={{ value: c.id, label: c.name }}>
                          {c.name}
                        </Select.Item>
                      ))}
                    </Select.Content>
                  </Select.Positioner>
                </Select.Root>
              </Flex>
              <Flex direction="column" flex={1}>
                <UIText fontSize="sm" mb={1}>Estado</UIText>
                <Select.Root
                  collection={statusCollection}
                  value={[status]}
                  onValueChange={(details) => {
                    const next = details.value[0];
                    if (next) setStatus(next as ProductStatus);
                  }}
                >
                  <Select.Trigger>
                    <Select.ValueText placeholder="_placeholder" />
                  </Select.Trigger>
                  <Select.Positioner>
                    <Select.Content>
                      {statusCollection.items.map(item => (
                        <Select.Item key={item.value} item={{ value: item.value, label: item.label }}>
                          {item.label}
                        </Select.Item>
                      ))}
                    </Select.Content>
                  </Select.Positioner>
                </Select.Root>
              </Flex>
            </Flex>

            <Flex direction={{ base: "column", sm: "row" }} gap={3}>
              <Flex direction="column" flex={1}>
                <UIText fontSize="sm" mb={1}>Margen %</UIText>
                <Input
                  placeholder="%"
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={marginPercent}
                  onChange={(e) => setMarginPercent(e.target.value)}
                />
              </Flex>
              <Flex direction="column" flex={1}>
                <UIText fontSize="sm" mb={1}>Descuento %</UIText>
                <Input
                  placeholder="%"
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={discountPercent}
                  onChange={(e) => setDiscountPercent(e.target.value)}
                />
              </Flex>
              <Flex direction="column" flex={1}>
                <UIText fontSize="sm" mb={1}>Impuesto %</UIText>
                <Input
                  placeholder="%"
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={taxPercent}
                  onChange={(e) => setTaxPercent(e.target.value)}
                />
              </Flex>
            </Flex>

            <Flex direction="column">
              <UIText fontSize="sm" mb={1}>Descripción</UIText>
              <Textarea
                placeholder="Descripción del producto (opcional)"
                rows={2}
                maxLength={500}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </Flex>

            <Flex direction="column">
              <UIText fontSize="sm" mb={1}>Notas</UIText>
              <Textarea
                placeholder="Notas internas (opcional)"
                rows={2}
                maxLength={500}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </Flex>
          </Flex>
        </Flex>
      </Flex>

      <Flex direction="column" gap={4}>
        <Heading as="h2" size="md">Líneas de Producto</Heading>
        <ProductLines
          materials={materials}
          materialLines={materialLines}
          laborLines={laborLines}
          extraCostLines={extraCostLines}
          onLinesChange={handleLinesChange}
          showPreview={showPreview}
        />
      </Flex>

      {costs && (
        <Flex direction="column" gap={2} p={4} bg="bg.subtle" borderRadius="md" maxW="420px">
          <Heading as="h3" size="sm">Costos (motor)</Heading>
          <Flex gap={4}><UIText flex={1}>Costo total:</UIText><UIText fontWeight="bold">{formatCents(costs.product_total_cost)}</UIText></Flex>
          <Flex gap={4}><UIText flex={1}>Ganancia:</UIText><UIText fontWeight="bold">{formatCents(costs.profit_amount)}</UIText></Flex>
          <Flex gap={4}><UIText flex={1}>Descuento:</UIText><UIText fontWeight="bold">{formatCents(costs.discount_amount)}</UIText></Flex>
          <Flex gap={4}><UIText flex={1}>Ganancia ajustada:</UIText><UIText fontWeight="bold">{formatCents(costs.adjusted_profit_amount)}</UIText></Flex>
          <Flex gap={4}><UIText flex={1}>Impuesto:</UIText><UIText fontWeight="bold">{formatCents(costs.tax_amount)}</UIText></Flex>
          <Flex gap={4}><UIText flex={1}>Precio final:</UIText><UIText fontWeight="bold">{formatCents(costs.final_sale_price)}</UIText></Flex>
        </Flex>
      )}

      <Flex justify="flex-end" gap={3} mt={6}>
        <Button
          variant="ghost"
          onClick={() => setShowPreview(!showPreview)}
        >
          {showPreview ? "Ocultar" : "Mostrar"} Vista Previa
        </Button>
        {savedId && (
          <Button variant="outline" onClick={handleRecalculate} loading={recalculating}>
            Recalcular
          </Button>
        )}
        <Button variant="outline" onClick={() => router.back()} disabled={saving}>
          Cancelar
        </Button>
        <Button colorPalette="brand"
          onClick={handleSave}
          loading={saving}
          disabled={!name.trim()}
        >
          {savedId ? "Actualizar" : "Guardar"} Producto
        </Button>
      </Flex>
    </Flex>
  );
}