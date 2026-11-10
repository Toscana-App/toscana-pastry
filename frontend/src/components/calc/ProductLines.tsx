"use client";

import { useState } from "react";
import {
  Button,
  Flex,
  Input,
  Select,
  Table,
  Text,
  IconButton,
  FormatNumber,
} from "@chakra-ui/react";
import { createListCollection } from "@ark-ui/react";
import { toaster } from "@/lib/toaster";
import type {
  Material,
  ProductLineMaterialIn,
  ProductLineLaborIn,
  ProductLineExtraCostIn,
} from "@/types/calc";

interface ProductLinesProps {
  materials?: Material[];
  materialLines?: ProductLineMaterialIn[];
  laborLines?: ProductLineLaborIn[];
  extraCostLines?: ProductLineExtraCostIn[];
  onLinesChange?: (
    materials: ProductLineMaterialIn[],
    labor: ProductLineLaborIn[],
    extraCosts: ProductLineExtraCostIn[]
  ) => void;
  showPreview?: boolean;
}

export function computeLinePreviews(
  materials: Material[] | undefined,
  materialLines: ProductLineMaterialIn[],
  laborLines: ProductLineLaborIn[],
  extraCostLines: ProductLineExtraCostIn[]
) {
  const materialTotals = materialLines.map((line) => {
    const mat = materials?.find((m) => m.id === line.material_id);
    const unit = mat && mat.unit_cost != null ? Number(mat.unit_cost) : 0;
    const qty = Number(line.quantity_used) || 0;
    return unit * qty;
  });
  const laborTotals = laborLines.map((line) => {
    const rate = Number(line.hourly_rate) || 0;
    const minutes = Number(line.minutes_required) || 0;
    return (rate * minutes) / 60;
  });
  const extraTotals = extraCostLines.map((line) => {
    const cost = Number(line.unit_cost) || 0;
    const qty = Number(line.quantity) || 0;
    return cost * qty;
  });
  const grandTotal =
    materialTotals.reduce((a, b) => a + b, 0) +
    laborTotals.reduce((a, b) => a + b, 0) +
    extraTotals.reduce((a, b) => a + b, 0);
  return { materialTotals, laborTotals, extraTotals, grandTotal };
}

function MaterialLineForm({
  onAdd,
  materials,
}: {
  onAdd: (line: ProductLineMaterialIn) => void;
  materials: Material[];
}) {
  const [selectedMaterial, setSelectedMaterial] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("");
  const materialOptions = materials.filter(m => m.status === 'active');
  const materialCollection = createListCollection({
    items: materialOptions.map(m => ({ value: m.id, label: m.name }))
  });

  const handleAdd = () => {
    if (!selectedMaterial || !quantity) {
      toaster.create({ title: "Seleccione un material e ingrese la cantidad", type: "warning" });
      return;
    }
    const qty = parseFloat(quantity);
    if (isNaN(qty) || qty <= 0) {
      toaster.create({ title: "La cantidad debe ser un número positivo", type: "warning" });
      return;
    }
    onAdd({ material_id: selectedMaterial, quantity_used: qty.toString() });
    setSelectedMaterial("");
    setQuantity("");
  };

  return (
    <Flex direction="column" gap={2} p={3} borderWidth="1px" borderRadius="md">
      <Text fontWeight="bold">Materiales</Text>
      <Flex gap={2} direction={{ base: "column", sm: "row" }} wrap="wrap">
        <Select.Root
          collection={materialCollection}
          value={[selectedMaterial]}
          onValueChange={(details) => {
            const next = details.value[0];
            if (next) setSelectedMaterial(next);
          }}
        >
          <Select.Trigger aria-label="Material">
            <Select.ValueText placeholder="Elegí un material…" />
          </Select.Trigger>
          <Select.Positioner>
            <Select.Content>
              {materialOptions.map(m => (
                <Select.Item key={m.id} item={{ value: m.id, label: m.name }}>
                  {m.name}
                </Select.Item>
              ))}
            </Select.Content>
          </Select.Positioner>
        </Select.Root>
        <Input
          name="quantity_used"
          aria-label="Cantidad"
          autoComplete="off"
          inputMode="decimal"
          placeholder="Cantidad…"
          type="number"
          min="0.01"
          step="0.01"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
        <Button variant="outline" onClick={handleAdd}>Agregar</Button>
      </Flex>
    </Flex>
  );
}

function LaborLineForm({
  onAdd,
}: {
  onAdd: (line: ProductLineLaborIn) => void;
}) {
  const [activityName, setActivityName] = useState<string>("");
  const [hourlyRate, setHourlyRate] = useState<string>("");
  const [minutesRequired, setMinutesRequired] = useState<string>("");

  const handleAdd = () => {
    if (!activityName || !hourlyRate || !minutesRequired) {
      toaster.create({ title: "Complete todos los campos del trabajo", type: "warning" });
      return;
    }
    const rate = parseFloat(hourlyRate);
    const minutes = parseFloat(minutesRequired);
    if (isNaN(rate) || rate < 0 || isNaN(minutes) || minutes < 0) {
      toaster.create({ title: "Valores numéricos inválidos", type: "warning" });
      return;
    }
    onAdd({
      activity_name: activityName,
      hourly_rate: rate.toString(),
      minutes_required: minutes.toString(),
    });
    setActivityName("");
    setHourlyRate("");
    setMinutesRequired("");
  };

  return (
    <Flex direction="column" gap={2} p={3} borderWidth="1px" borderRadius="md">
      <Text fontWeight="bold">Trabajo</Text>
      <Flex gap={2} direction={{ base: "column", sm: "row" }} wrap="wrap">
        <Input
          name="activity_name"
          aria-label="Nombre de actividad"
          autoComplete="off"
          placeholder="Nombre de actividad…"
          maxLength={120}
          value={activityName}
          onChange={(e) => setActivityName(e.target.value)}
        />
        <Input
          name="hourly_rate"
          aria-label="Tarifa por hora"
          autoComplete="off"
          inputMode="decimal"
          placeholder="Tarifa por hora…"
          type="number"
          min="0"
          step="0.01"
          value={hourlyRate}
          onChange={(e) => setHourlyRate(e.target.value)}
        />
        <Input
          name="minutes_required"
          aria-label="Minutos requeridos"
          autoComplete="off"
          inputMode="numeric"
          placeholder="Minutos requeridos…"
          type="number"
          min="0"
          step="1"
          value={minutesRequired}
          onChange={(e) => setMinutesRequired(e.target.value)}
        />
        <Button variant="outline" onClick={handleAdd}>Agregar trabajo</Button>
      </Flex>
    </Flex>
  );
}

function ExtraCostLineForm({
  onAdd,
}: {
  onAdd: (line: ProductLineExtraCostIn) => void;
}) {
  const [conceptName, setConceptName] = useState<string>("");
  const [unitCost, setUnitCost] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("");

  const handleAdd = () => {
    if (!conceptName || !unitCost || !quantity) {
      toaster.create({ title: "Complete todos los campos del costo extra", type: "warning" });
      return;
    }
    const cost = parseFloat(unitCost);
    const qty = parseFloat(quantity);
    if (isNaN(cost) || cost < 0 || isNaN(qty) || qty <= 0) {
      toaster.create({ title: "Valores numéricos inválidos", type: "warning" });
      return;
    }
    onAdd({
      concept_name: conceptName,
      unit_cost: cost.toString(),
      quantity: qty.toString(),
    });
    setConceptName("");
    setUnitCost("");
    setQuantity("");
  };

  return (
    <Flex direction="column" gap={2} p={3} borderWidth="1px" borderRadius="md">
      <Text fontWeight="bold">Costo Extra</Text>
      <Flex gap={2} direction={{ base: "column", sm: "row" }} wrap="wrap">
        <Input
          name="concept_name"
          aria-label="Nombre del concepto"
          autoComplete="off"
          placeholder="Nombre del concepto…"
          maxLength={120}
          value={conceptName}
          onChange={(e) => setConceptName(e.target.value)}
        />
        <Input
          name="unit_cost"
          aria-label="Costo unitario"
          autoComplete="off"
          inputMode="decimal"
          placeholder="Costo unitario…"
          type="number"
          min="0"
          step="0.01"
          value={unitCost}
          onChange={(e) => setUnitCost(e.target.value)}
        />
        <Input
          name="quantity"
          aria-label="Cantidad"
          autoComplete="off"
          inputMode="decimal"
          placeholder="Cantidad…"
          type="number"
          min="0.01"
          step="0.01"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
        <Button variant="outline" onClick={handleAdd}>Agregar costo</Button>
      </Flex>
    </Flex>
  );
}

function LinesDisplay({
  materials,
  materialLines,
  labor,
  extraCosts,
  showPreview,
  previews,
  onRemoveMaterial,
  onRemoveLabor,
  onRemoveExtraCost,
}: {
  materials: Material[];
  materialLines: ProductLineMaterialIn[];
  labor: ProductLineLaborIn[];
  extraCosts: ProductLineExtraCostIn[];
  showPreview: boolean;
  previews: ReturnType<typeof computeLinePreviews>;
  onRemoveMaterial: (index: number) => void;
  onRemoveLabor: (index: number) => void;
  onRemoveExtraCost: (index: number) => void;
}) {
  const fmt = (pesos: number) => <FormatNumber value={pesos} style="currency" currency="ARS" />;
  return (
    <Flex direction="column" gap={4}>
      {materialLines.length > 0 && (
        <Flex direction="column">
          <Text fontWeight="bold" mb={2}>Materiales</Text>
          <Table.Root size="sm">
            <Table.Header>
              <Table.ColumnHeader>Material</Table.ColumnHeader>
              <Table.ColumnHeader>Cantidad</Table.ColumnHeader>
              {showPreview && <Table.ColumnHeader>Costo Unitario</Table.ColumnHeader>}
              {showPreview && <Table.ColumnHeader>Total</Table.ColumnHeader>}
              <Table.ColumnHeader></Table.ColumnHeader>
            </Table.Header>
            <Table.Body>
              {materialLines.map((line, index) => {
                const mat = materials.find((m) => m.id === line.material_id);
                return (
                  <Table.Row key={index}>
                    <Table.Cell>{mat?.name || line.material_id}</Table.Cell>
                    <Table.Cell fontVariantNumeric="tabular-nums">{line.quantity_used}</Table.Cell>
                    {showPreview && (
                      <Table.Cell fontVariantNumeric="tabular-nums">
                        {mat?.unit_cost != null ? fmt(Number(mat.unit_cost)) : "-"}
                      </Table.Cell>
                    )}
                    {showPreview && (
                      <Table.Cell fontVariantNumeric="tabular-nums">{fmt(previews.materialTotals[index] ?? 0)}</Table.Cell>
                    )}
                    <Table.Cell>
                      <IconButton
                        size="sm"
                        variant="ghost"
                        aria-label="Eliminar material"
                        onClick={() => onRemoveMaterial(index)}
                      >
                        ✕
                      </IconButton>
                    </Table.Cell>
                  </Table.Row>
                );
              })}
            </Table.Body>
          </Table.Root>
        </Flex>
      )}

      {labor.length > 0 && (
        <Flex direction="column">
          <Text fontWeight="bold" mb={2}>Trabajo</Text>
          <Table.Root size="sm">
            <Table.Header>
              <Table.ColumnHeader>Actividad</Table.ColumnHeader>
              {showPreview && <Table.ColumnHeader>Tarifa/Hora</Table.ColumnHeader>}
              <Table.ColumnHeader>Minutos</Table.ColumnHeader>
              {showPreview && <Table.ColumnHeader>Total</Table.ColumnHeader>}
              <Table.ColumnHeader></Table.ColumnHeader>
            </Table.Header>
            <Table.Body>
              {labor.map((line, index) => (
                <Table.Row key={index}>
                  <Table.Cell>{line.activity_name}</Table.Cell>
                  {showPreview && <Table.Cell fontVariantNumeric="tabular-nums">{fmt(Number(line.hourly_rate))}</Table.Cell>}
                  <Table.Cell fontVariantNumeric="tabular-nums">{line.minutes_required}</Table.Cell>
                  {showPreview && (
                    <Table.Cell fontVariantNumeric="tabular-nums">{fmt(previews.laborTotals[index] ?? 0)}</Table.Cell>
                  )}
                  <Table.Cell>
                    <IconButton
                      size="sm"
                      variant="ghost"
                      aria-label="Eliminar trabajo"
                      onClick={() => onRemoveLabor(index)}
                    >
                      ✕
                    </IconButton>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Flex>
      )}

      {extraCosts.length > 0 && (
        <Flex direction="column">
          <Text fontWeight="bold" mb={2}>Costos Extras</Text>
          <Table.Root size="sm">
            <Table.Header>
              <Table.ColumnHeader>Concepto</Table.ColumnHeader>
              {showPreview && <Table.ColumnHeader>Costo Unitario</Table.ColumnHeader>}
              <Table.ColumnHeader>Cantidad</Table.ColumnHeader>
              {showPreview && <Table.ColumnHeader>Total</Table.ColumnHeader>}
              <Table.ColumnHeader></Table.ColumnHeader>
            </Table.Header>
            <Table.Body>
              {extraCosts.map((line, index) => (
                <Table.Row key={index}>
                  <Table.Cell>{line.concept_name}</Table.Cell>
                  {showPreview && <Table.Cell fontVariantNumeric="tabular-nums">{fmt(Number(line.unit_cost))}</Table.Cell>}
                  <Table.Cell fontVariantNumeric="tabular-nums">{line.quantity}</Table.Cell>
                  {showPreview && (
                    <Table.Cell fontVariantNumeric="tabular-nums">{fmt(previews.extraTotals[index] ?? 0)}</Table.Cell>
                  )}
                  <Table.Cell>
                    <IconButton
                      size="sm"
                      variant="ghost"
                      aria-label="Eliminar costo extra"
                      onClick={() => onRemoveExtraCost(index)}
                    >
                      ✕
                    </IconButton>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Flex>
      )}

      {materialLines.length === 0 && labor.length === 0 && extraCosts.length === 0 && (
        <Flex p={4} bg="bg.subtle" borderRadius="md" justify="center">
          <Text color="fg.muted">No hay líneas agregadas aún</Text>
        </Flex>
      )}

      {showPreview &&
        (materialLines.length > 0 || labor.length > 0 || extraCosts.length > 0) && (
          <Flex justify="flex-end" p={3} bg="bg.subtle" borderRadius="md">
            <Text fontWeight="bold" fontVariantNumeric="tabular-nums" aria-live="polite">Total estimado: {fmt(previews.grandTotal)}</Text>
          </Flex>
        )}
    </Flex>
  );
}

export default function ProductLines({
  materials,
  materialLines = [],
  laborLines = [],
  extraCostLines = [],
  onLinesChange,
  showPreview = false,
}: ProductLinesProps) {
  const handleAddMaterial = (line: ProductLineMaterialIn) => {
    onLinesChange?.([...materialLines, line], laborLines, extraCostLines);
  };

  const handleRemoveMaterial = (index: number) => {
    onLinesChange?.(
      materialLines.filter((_, i) => i !== index),
      laborLines,
      extraCostLines
    );
  };

  const handleAddLabor = (line: ProductLineLaborIn) => {
    onLinesChange?.(materialLines, [...laborLines, line], extraCostLines);
  };

  const handleRemoveLabor = (index: number) => {
    onLinesChange?.(
      materialLines,
      laborLines.filter((_, i) => i !== index),
      extraCostLines
    );
  };

  const handleAddExtraCost = (line: ProductLineExtraCostIn) => {
    onLinesChange?.(materialLines, laborLines, [...extraCostLines, line]);
  };

  const handleRemoveExtraCost = (index: number) => {
    onLinesChange?.(
      materialLines,
      laborLines,
      extraCostLines.filter((_, i) => i !== index)
    );
  };

  const previews = computeLinePreviews(
    materials,
    materialLines,
    laborLines,
    extraCostLines
  );

  return (
    <Flex direction="column" gap={4}>
      <MaterialLineForm
        onAdd={handleAddMaterial}
        materials={materials || []}
      />

      <LaborLineForm onAdd={handleAddLabor} />

      <ExtraCostLineForm onAdd={handleAddExtraCost} />

      {(materialLines.length > 0 || laborLines.length > 0 || extraCostLines.length > 0) ? (
        <LinesDisplay
          materials={materials || []}
          materialLines={materialLines}
          labor={laborLines}
          extraCosts={extraCostLines}
          showPreview={showPreview}
          previews={previews}
          onRemoveMaterial={handleRemoveMaterial}
          onRemoveLabor={handleRemoveLabor}
          onRemoveExtraCost={handleRemoveExtraCost}
        />
      ) : null}
    </Flex>
  );
}