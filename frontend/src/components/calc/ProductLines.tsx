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
} from "@chakra-ui/react";
import { createListCollection } from "@ark-ui/react";
import { toaster } from "@/lib/toaster";
import type {
  Material,
  ProductLineMaterialIn,
  ProductLineLaborIn,
  ProductLineExtraCostIn,
  ProductLineMaterialOut,
} from "@/types/calc";

interface ProductLinesProps {
  materials?: Material[];
  laborLines?: ProductLineLaborIn[];
  extraCostLines?: ProductLineExtraCostIn[];
  onLinesChange?: (
    materials: ProductLineMaterialIn[],
    labor: ProductLineLaborIn[],
    extraCosts: ProductLineExtraCostIn[]
  ) => void;
  showPreview?: boolean;
}

// Form for material lines
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
          <Select.Trigger>
            <Select.ValueText placeholder="_placeholder" />
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
          placeholder="Cantidad"
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

// Form for labor lines
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
          placeholder="Nombre de actividad"
          maxLength={120}
          value={activityName}
          onChange={(e) => setActivityName(e.target.value)}
        />
        <Input
          placeholder="Tarifa por hora"
          type="number"
          min="0"
          step="0.01"
          value={hourlyRate}
          onChange={(e) => setHourlyRate(e.target.value)}
        />
        <Input
          placeholder="Minutos requeridos"
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

// Form for extra cost lines
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
          placeholder="Nombre del concepto"
          maxLength={120}
          value={conceptName}
          onChange={(e) => setConceptName(e.target.value)}
        />
        <Input
          placeholder="Costo unitario"
          type="number"
          min="0"
          step="0.01"
          value={unitCost}
          onChange={(e) => setUnitCost(e.target.value)}
        />
        <Input
          placeholder="Cantidad"
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

// Display component for lines
function LinesDisplay({
  materials,
  labor,
  extraCosts,
  onRemoveMaterial,
  onRemoveLabor,
  onRemoveExtraCost,
}: {
  materials: ProductLineMaterialOut[];
  labor: ProductLineLaborIn[];
  extraCosts: ProductLineExtraCostIn[];
  onRemoveMaterial: (index: number) => void;
  onRemoveLabor: (index: number) => void;
  onRemoveExtraCost: (index: number) => void;
}) {
  return (
    <Flex direction="column" gap={4}>
      {materials.length > 0 && (
        <Flex direction="column">
          <Text fontWeight="bold" mb={2}>Materiales</Text>
          <Table.Root size="sm">
            <Table.Header>
              <Table.ColumnHeader>Material</Table.ColumnHeader>
              <Table.ColumnHeader>Cantidad</Table.ColumnHeader>
              <Table.ColumnHeader>Costo Unitario</Table.ColumnHeader>
              <Table.ColumnHeader>Costo Total</Table.ColumnHeader>
              <Table.ColumnHeader></Table.ColumnHeader>
            </Table.Header>
            <Table.Body>
              {materials.map((line, index) => (
                <Table.Row key={index}>
                  <Table.Cell>{line.material_name}</Table.Cell>
                  <Table.Cell>{line.quantity_used}</Table.Cell>
                  <Table.Cell>{line.unit_cost_snapshot}</Table.Cell>
                  <Table.Cell>{line.line_total_cost}</Table.Cell>
                  <Table.Cell>
                    <IconButton
                      size="sm"
                      variant="ghost"
                      aria-label="Eliminar"
                      onClick={() => onRemoveMaterial(index)}
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

      {labor.length > 0 && (
        <Flex direction="column">
          <Text fontWeight="bold" mb={2}>Trabajo</Text>
          <Table.Root size="sm">
            <Table.Header>
              <Table.ColumnHeader>Actividad</Table.ColumnHeader>
              <Table.ColumnHeader>Tarifa/Hora</Table.ColumnHeader>
              <Table.ColumnHeader>Minutos</Table.ColumnHeader>
              <Table.ColumnHeader>Costo Total</Table.ColumnHeader>
              <Table.ColumnHeader></Table.ColumnHeader>
            </Table.Header>
            <Table.Body>
              {labor.map((line, index) => (
                <Table.Row key={index}>
                  <Table.Cell>{line.activity_name}</Table.Cell>
                  <Table.Cell>{line.hourly_rate}</Table.Cell>
                  <Table.Cell>{line.minutes_required}</Table.Cell>
                  <Table.Cell>0.00</Table.Cell>
                  <Table.Cell>
                    <IconButton
                      size="sm"
                      variant="ghost"
                      aria-label="Eliminar"
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
              <Table.ColumnHeader>Costo Unitario</Table.ColumnHeader>
              <Table.ColumnHeader>Cantidad</Table.ColumnHeader>
              <Table.ColumnHeader>Costo Total</Table.ColumnHeader>
              <Table.ColumnHeader></Table.ColumnHeader>
            </Table.Header>
            <Table.Body>
              {extraCosts.map((line, index) => (
                <Table.Row key={index}>
                  <Table.Cell>{line.concept_name}</Table.Cell>
                  <Table.Cell>{line.unit_cost}</Table.Cell>
                  <Table.Cell>{line.quantity}</Table.Cell>
                  <Table.Cell>0.00</Table.Cell>
                  <Table.Cell>
                    <IconButton
                      size="sm"
                      variant="ghost"
                      aria-label="Eliminar"
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

      {materials.length === 0 && labor.length === 0 && extraCosts.length === 0 && (
        <Flex p={4} bg="bg.subtle" borderRadius="md" justify="center">
          <Text color="fg.muted">No hay líneas agregadas aún</Text>
        </Flex>
      )}
    </Flex>
  );
}

export default function ProductLines({
  materials,
  laborLines = [],
  extraCostLines = [],
  onLinesChange,
}: ProductLinesProps) {
  const [materialLines, setMaterialLines] = useState<ProductLineMaterialIn[]>([]);
  const [laborLinesState, setLaborLinesState] = useState<ProductLineLaborIn[]>(laborLines);
  const [extraCostLinesState, setExtraCostLinesState] = useState<ProductLineExtraCostIn[]>(extraCostLines);

  const handleAddMaterial = (line: ProductLineMaterialIn) => {
    setMaterialLines(prev => [...prev, line]);
    onLinesChange?.(
      [...materialLines, line],
      laborLinesState,
      extraCostLinesState
    );
  };

  const handleRemoveMaterial = (index: number) => {
    setMaterialLines(prev => prev.filter((_, i) => i !== index));
    onLinesChange?.(
      materialLines.filter((_, i) => i !== index),
      laborLinesState,
      extraCostLinesState
    );
  };

  const handleAddLabor = (line: ProductLineLaborIn) => {
    setLaborLinesState(prev => [...prev, line]);
    onLinesChange?.(
      materialLines,
      [...laborLinesState, line],
      extraCostLinesState
    );
  };

  const handleRemoveLabor = (index: number) => {
    setLaborLinesState(prev => prev.filter((_, i) => i !== index));
    onLinesChange?.(
      materialLines,
      laborLinesState.filter((_, i) => i !== index),
      extraCostLinesState
    );
  };

  const handleAddExtraCost = (line: ProductLineExtraCostIn) => {
    setExtraCostLinesState(prev => [...prev, line]);
    onLinesChange?.(
      materialLines,
      laborLinesState,
      [...extraCostLinesState, line]
    );
  };

  const handleRemoveExtraCost = (index: number) => {
    setExtraCostLinesState(prev => prev.filter((_, i) => i !== index));
    onLinesChange?.(
      materialLines,
      laborLinesState,
      extraCostLinesState.filter((_, i) => i !== index)
    );
  };

  const materialLinesDisplay = materialLines.map((line, index) => ({
    ...line,
    material_name: materials?.find(m => m.id === line.material_id)?.name || '',
    unit_cost_snapshot: materials?.find(m => m.id === line.material_id)?.unit_cost || '0.00',
    line_total_cost: '0.00',
    sort_order: index,
  })) as ProductLineMaterialOut[];

  return (
    <Flex direction="column" gap={4}>
      <MaterialLineForm
        onAdd={handleAddMaterial}
        materials={materials || []}
      />

      <LaborLineForm onAdd={handleAddLabor} />

      <ExtraCostLineForm onAdd={handleAddExtraCost} />

      {materialLinesDisplay.length > 0 || laborLinesState.length > 0 || extraCostLinesState.length > 0 ? (
        <Flex direction="column" gap={4}>
          <LinesDisplay
            materials={materialLinesDisplay}
            labor={laborLinesState}
            extraCosts={extraCostLinesState}
            onRemoveMaterial={handleRemoveMaterial}
            onRemoveLabor={handleRemoveLabor}
            onRemoveExtraCost={handleRemoveExtraCost}
          />
        </Flex>
      ) : null}
    </Flex>
  );
}