"use client";

import { useState } from "react";
import { Button, Flex, Input, Select, Text, Textarea } from "@chakra-ui/react";
import { createListCollection } from "@ark-ui/react";
import type {
  Category,
  Material,
  MaterialCreatePayload,
  MaterialUpdatePayload,
  Supplier,
} from "@/types/calc";

// Form reutilizado para alta (card encima de la tabla) y edición
// (diálogo con el material precargado). Emite payloads vía onSubmit:
// en modo alta, MaterialCreatePayload con campos vacíos omitidos; en modo
// edición, MaterialUpdatePayload con SOLO los campos tocados (null en
// precio/cantidad limpia el dato, RF-P2CC-04). Nunca incluye unit_cost
// ni status (extra="forbid" → 422, RF-P2CC-02/03).
interface MaterialFormProps {
  initial?: Material;
  categories: Category[];
  suppliers: Supplier[];
  onSubmit: (payload: MaterialCreatePayload | MaterialUpdatePayload) => void;
  busy?: boolean;
  submitLabel?: string;
}

// Input numérico crudo → number | null (vacío → null; inválido → null).
// Valor centinela de la opción vacía de categoría/proveedor (→ null en PATCH).
const NONE = "__none__";

function parseAmount(raw: string): number | null {
  const value = raw.trim();
  if (value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export default function MaterialForm({
  initial,
  categories,
  suppliers,
  onSubmit,
  busy = false,
  submitLabel = "Guardar",
}: MaterialFormProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [internalCode, setInternalCode] = useState(
    initial?.internal_code ?? ""
  );
  const [categoryId, setCategoryId] = useState(initial?.category_id ?? "");
  const [supplierId, setSupplierId] = useState(initial?.supplier_id ?? "");
  const [unitOfMeasure, setUnitOfMeasure] = useState(
    initial?.unit_of_measure ?? ""
  );
  const categoryCollection = createListCollection({
    items: [
      { value: NONE, label: "Sin categoría" },
      ...categories.map((c) => ({ value: c.id, label: c.name })),
    ],
  });
  const supplierCollection = createListCollection({
    items: [
      { value: NONE, label: "Sin proveedor" },
      ...suppliers.map((s) => ({ value: s.id, label: s.name })),
    ],
  });

  const [price, setPrice] = useState(initial?.purchase_total_price ?? "");
  const [quantity, setQuantity] = useState(initial?.package_quantity ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [error, setError] = useState("");

  function handleSubmit() {
    const trimmedName = name.trim();
    if (!trimmedName || busy) return;
    setError("");

    const priceValue = parseAmount(price);
    const quantityValue = parseAmount(quantity);
    // Validación client-side: no depender del 422 del backend.
    if (priceValue !== null && priceValue < 0) {
      setError("El precio del paquete no puede ser negativo.");
      return;
    }
    if (quantityValue !== null && quantityValue <= 0) {
      setError("La cantidad por paquete debe ser mayor a 0.");
      return;
    }

    if (initial) {
      // Edición: PATCH con solo los campos tocados (el backend usa
      // exclude_unset). Precio/cantidad: input vacío → null explícita
      // (elimina el dato en el servidor, RF-P2CC-04).
      const payload: MaterialUpdatePayload = {};
      if (trimmedName !== initial.name) payload.name = trimmedName;
      assignTouchedText(payload, "internal_code", internalCode, initial.internal_code);
      assignTouchedText(payload, "category_id", categoryId, initial.category_id);
      assignTouchedText(payload, "supplier_id", supplierId, initial.supplier_id);
      assignTouchedText(payload, "unit_of_measure", unitOfMeasure, initial.unit_of_measure);
      assignTouchedText(payload, "notes", notes, initial.notes);
      const originalPrice =
        initial.purchase_total_price !== null
          ? Number(initial.purchase_total_price)
          : null;
      if (priceValue !== originalPrice) {
        payload.purchase_total_price = priceValue;
      }
      const originalQuantity =
        initial.package_quantity !== null
          ? Number(initial.package_quantity)
          : null;
      if (quantityValue !== originalQuantity) {
        payload.package_quantity = quantityValue;
      }
      // Sin cambios → no enviar (PATCH vacío → 422 en el backend).
      if (Object.keys(payload).length === 0) {
        setError("No hay cambios para guardar.");
        return;
      }
      onSubmit(payload);
    } else {
      // Alta: payload mínimo; los campos vacíos no se mandan.
      const payload: MaterialCreatePayload = { name: trimmedName };
      if (internalCode.trim()) payload.internal_code = internalCode.trim();
      if (categoryId) payload.category_id = categoryId;
      if (supplierId) payload.supplier_id = supplierId;
      if (unitOfMeasure.trim()) payload.unit_of_measure = unitOfMeasure.trim();
      if (priceValue !== null) payload.purchase_total_price = priceValue;
      if (quantityValue !== null) payload.package_quantity = quantityValue;
      if (notes.trim()) payload.notes = notes.trim();
      onSubmit(payload);
    }
  }

  return (
    <Flex as="form" direction="column" gap={3} onSubmit={(e) => {
      e.preventDefault();
      handleSubmit();
    }}>
      <Flex direction={{ base: "column", sm: "row" }} gap={3}>
        <Input
          aria-label="Nombre"
          placeholder="Nombre"
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          aria-label="Código interno"
          placeholder="Código interno (opcional)"
          maxLength={40}
          value={internalCode}
          onChange={(e) => setInternalCode(e.target.value)}
        />
      </Flex>
      <Flex direction={{ base: "column", sm: "row" }} gap={3}>
        <Select.Root
          collection={categoryCollection}
          value={[categoryId || NONE]}
          onValueChange={(details) => {
            const next = details.value[0];
            setCategoryId(!next || next === NONE ? "" : next);
          }}
        >
          <Select.Trigger aria-label="Categoría" minW="10rem">
            <Select.ValueText placeholder="Categoría (opcional)" />
          </Select.Trigger>
          <Select.Positioner>
            <Select.Content>
              <Select.Item item={{ value: NONE, label: "Sin categoría" }}>
                Sin categoría
              </Select.Item>
              {categories.map((c) => (
                <Select.Item key={c.id} item={{ value: c.id, label: c.name }}>
                  {c.name}
                </Select.Item>
              ))}
            </Select.Content>
          </Select.Positioner>
        </Select.Root>
        <Select.Root
          collection={supplierCollection}
          value={[supplierId || NONE]}
          onValueChange={(details) => {
            const next = details.value[0];
            setSupplierId(!next || next === NONE ? "" : next);
          }}
        >
          <Select.Trigger aria-label="Proveedor" minW="10rem">
            <Select.ValueText placeholder="Proveedor (opcional)" />
          </Select.Trigger>
          <Select.Positioner>
            <Select.Content>
              <Select.Item item={{ value: NONE, label: "Sin proveedor" }}>
                Sin proveedor
              </Select.Item>
              {suppliers.map((s) => (
                <Select.Item key={s.id} item={{ value: s.id, label: s.name }}>
                  {s.name}
                </Select.Item>
              ))}
            </Select.Content>
          </Select.Positioner>
        </Select.Root>
      </Flex>
      <Flex direction={{ base: "column", sm: "row" }} gap={3}>
        <Input
          aria-label="Unidad de medida"
          placeholder="Unidad de medida (kg, litro, unidad)"
          maxLength={20}
          value={unitOfMeasure}
          onChange={(e) => setUnitOfMeasure(e.target.value)}
        />
        <Input
          aria-label="Precio del paquete"
          placeholder="Precio del paquete (opcional)"
          type="number"
          step="0.01"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
        />
        <Input
          aria-label="Cantidad por paquete"
          placeholder="Cantidad por paquete (opcional)"
          type="number"
          step="0.01"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
      </Flex>
      <Textarea
        aria-label="Notas"
        placeholder="Notas (opcional)"
        rows={2}
        maxLength={500}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />
      {error && (
        <Text role="alert" color="red.fg" fontSize="sm">
          {error}
        </Text>
      )}
      <Flex justify="flex-end">
        <Button colorPalette="brand"
          type="submit"
          rounded="full"
          loading={busy}
          disabled={!name.trim()}
        >
          {submitLabel}
        </Button>
      </Flex>
    </Flex>
  );
}

// Asigna el campo en el payload solo si el input difiere del original;
// texto vacío con dato previo → null (limpia el dato).
function assignTouchedText(
  payload: MaterialUpdatePayload,
  field:
    | "internal_code"
    | "category_id"
    | "supplier_id"
    | "unit_of_measure"
    | "notes",
  input: string,
  original: string | null
) {
  const next = input.trim();
  const was = original ?? "";
  if (next !== was) {
    payload[field] = next === "" ? null : next;
  }
}
