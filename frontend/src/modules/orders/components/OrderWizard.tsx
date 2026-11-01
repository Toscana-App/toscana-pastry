"use client";

import {
  Alert,
  Box,
  Button,
  Flex,
  Field,
  Heading,
  HStack,
  Input,
  Skeleton,
  Stack,
  Text,
  chakra,
} from "@chakra-ui/react";
import NextLink from "next/link";
import { formatCents, formatPct } from "@/lib/format";
import { useOrderWizard } from "../hooks/useOrderWizard";

interface OrderWizardProps {
  /** Cuando se pasa, el wizard edita ese pedido (solo estado nuevo). */
  orderId?: string;
}

/**
 * Select nativo estilizado (misma convención de EnumSelect de F5) para
 * pickers de registros (id + label): clientes y productos.
 */
const StyledOptionSelect = chakra("select", {
  base: {
    width: "100%",
    height: "2.5rem",
    paddingInline: "0.75rem",
    borderRadius: "md",
    borderWidth: "1px",
    borderColor: "border",
    background: "transparent",
    fontSize: "sm",
    outline: "none",
    _focusVisible: {
      borderColor: "brand.solid",
      boxShadow: "0 0 0 1px var(--chakra-colors-brand-600)",
    },
  },
});

interface OptionSelectProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  "aria-label": string;
  options: Array<{ value: string; label: string }>;
}

function OptionSelect({ value, onChange, placeholder, "aria-label": label, options }: OptionSelectProps) {
  return (
    <StyledOptionSelect
      value={value}
      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onChange(e.target.value)}
      aria-label={label}
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </StyledOptionSelect>
  );
}

/**
 * Wizard de pedidos (Fase 6, UC-02/UC-04) — /pedidos/nuevo y edición.
 *
 * - Cliente: selector con búsqueda o alta inline (dedupe nombre+teléfono:
 *   un 409 del backend adopta el cliente existente, no es un error).
 * - Líneas: producto + qty + porciones (opcional) + nota. El precio NUNCA se
 *   edita: el backend lo calcula (RNF-P6-03).
 * - Preview en vivo (debounce 500 ms, admin): POST /orders/preview, mismo
 *   cálculo que el create, sin persistir.
 * - Crear/confirmar devuelve 409 con stock insuficiente → se muestra el
 *   detalle y no se descuenta nada (RNF-P6-04).
 */
export function OrderWizard({ orderId }: OrderWizardProps) {
  const {
    isAdmin,
    customerId,
    setCustomerId,
    customerMode,
    setCustomerMode,
    customerQuery,
    newName,
    setNewName,
    newPhone,
    setNewPhone,
    date,
    setDate,
    margin,
    setMargin,
    items,
    products,
    customerOptions,
    preview,
    stockError,
    submitError,
    submitting,
    loadingDetail,
    updateItem,
    addItem,
    removeItem,
    submit,
  } = useOrderWizard(orderId);


  if (loadingDetail) {
    return (
      <Stack gap={3} maxW="640px">
        <Skeleton h="32px" />
        <Skeleton h="64px" />
        <Skeleton h="64px" />
        <Skeleton h="64px" />
      </Stack>
    );
  }

  return (
    <Flex direction="column" gap={5}>
      <Flex align="center" justify="space-between" gap={3}>
        <Heading fontSize="2xl">{orderId ? "Editar pedido" : "Nuevo pedido"}</Heading>
        <Button variant="ghost" asChild>
          <NextLink href="/pedidos">Volver al listado</NextLink>
        </Button>
      </Flex>

      <Stack gap={6} maxW="960px">
        {/* Cliente */}
        <Box borderWidth="1px" borderColor="border" rounded="md" p={4}>
          <Heading size="sm" mb={3}>
            Cliente
          </Heading>
          <HStack gap={2} wrap="wrap">
            <Button
              size="sm"
              variant={customerMode === "existing" ? "solid" : "outline"}
              colorPalette={customerMode === "existing" ? "brand" : "gray"}
              aria-pressed={customerMode === "existing"}
              onClick={() => setCustomerMode("existing")}
            >
              Cliente existente
            </Button>
            <Button
              size="sm"
              variant={customerMode === "new" ? "solid" : "outline"}
              colorPalette={customerMode === "new" ? "brand" : "gray"}
              aria-pressed={customerMode === "new"}
              onClick={() => setCustomerMode("new")}
            >
              Nuevo cliente
            </Button>
          </HStack>

          {customerMode === "existing" ? (
            <Field.Root mt={3} maxW="420px">
              <Field.Label>Cliente</Field.Label>
              <OptionSelect
                value={customerId}
                onChange={setCustomerId}
                placeholder="Buscar por nombre o teléfono…"
                aria-label="Elegir cliente"
                options={customerOptions}
              />
              <Field.ErrorText>
                {customerId === "" ? "Elegí un cliente" : ""}
              </Field.ErrorText>
              {customerQuery !== "" ? (
                <Field.HelperText mt={1}>
                  Búsqueda: {customerQuery}
                </Field.HelperText>
              ) : null}
            </Field.Root>
          ) : (
            <HStack gap={3} mt={3} wrap="wrap">
              <Field.Root w="100%" maxW="280px">
                <Field.Label>Nombre</Field.Label>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Cliente"
                  aria-label="Nombre del nuevo cliente"
                />
              </Field.Root>
              <Field.Root w="100%" maxW="200px">
                <Field.Label>Teléfono</Field.Label>
                <Input
                  value={newPhone}
                  onChange={(e) => setNewPhone(e.target.value)}
                  placeholder="11-2233-4455"
                  aria-label="Teléfono del nuevo cliente"
                />
              </Field.Root>
            </HStack>
          )}
          <Text color="fg.muted" fontSize="sm" mt={2}>
            Si el cliente ya existe (mismo nombre y teléfono), se usa el
            existente.
          </Text>
        </Box>

        {/* Fecha + margen */}
        <HStack gap={3} wrap="wrap">
          <Field.Root w="100%" maxW="220px">
            <Field.Label>Fecha del pedido</Field.Label>
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              aria-label="Fecha del pedido"
            />
          </Field.Root>
          <Field.Root w="100%" maxW="220px">
            <Field.Label>Margen % (opcional)</Field.Label>
            <Input
              type="number"
              min={0}
              max={200}
              value={margin}
              onChange={(e) => setMargin(e.target.value)}
              placeholder="vacío = margen del negocio"
              aria-label="Margen por pedido en porcentaje"
            />
            {preview.status === "done" && preview.data ? (
              <Field.HelperText mt={1}>
                Margen aplicado: {formatPct(preview.data.margin_pct)}
                {margin === ""
                  ? ` (margen del negocio: ${formatPct(preview.data.tenant_margin_pct)})`
                  : ""}
              </Field.HelperText>
            ) : null}
          </Field.Root>
        </HStack>

        {/* Líneas */}
        <Box borderWidth="1px" borderColor="border" rounded="md" p={4}>
          <HStack mb={3}>
            <Heading size="sm">Ítems</Heading>
          </HStack>
          <Stack gap={3}>
            {items.map((item, idx) => (
              <Flex key={item.key} gap={3} wrap="wrap" align="end">
                <Field.Root w="100%" maxW="280px" flex={1}>
                  <Field.Label>Producto {idx + 1}</Field.Label>
                  <OptionSelect
                    value={item.product_id}
                    onChange={(v) => updateItem(item.key, { product_id: v })}
                    placeholder="Elegir producto…"
                    aria-label={`Producto de la línea ${idx + 1}`}
                    options={products.map((p) => ({
                      value: p.id,
                      label: p.name + (p.complete ? "" : " (sin precio)"),
                    }))}
                  />
                </Field.Root>
                <Field.Root w="110px">
                  <Field.Label>Cant.</Field.Label>
                  <Input
                    type="number"
                    min={1}
                    max={99}
                    value={item.qty}
                    onChange={(e) => updateItem(item.key, { qty: e.target.value })}
                    aria-label={`Cantidad de la línea ${idx + 1}`}
                  />
                </Field.Root>
                <Field.Root w="130px">
                  <Field.Label>Porciones</Field.Label>
                  <Input
                    type="number"
                    min={1}
                    max={999}
                    value={item.portions}
                    onChange={(e) => updateItem(item.key, { portions: e.target.value })}
                    placeholder="del producto"
                    aria-label={`Porciones de la línea ${idx + 1}`}
                  />
                </Field.Root>
                <Field.Root w="100%" maxW="260px" flex={1}>
                  <Field.Label>Nota</Field.Label>
                  <Input
                    value={item.note}
                    onChange={(e) => updateItem(item.key, { note: e.target.value })}
                    placeholder="opcional"
                    aria-label={`Nota de la línea ${idx + 1}`}
                  />
                </Field.Root>
                <Button
                  variant="ghost"
                  colorPalette="red"
                  aria-label={`Quitar línea ${idx + 1}`}
                  onClick={() => removeItem(item.key)}
                  disabled={items.length === 1}
                >
                  Quitar
                </Button>
              </Flex>
            ))}
          </Stack>
          <Button variant="outline" mt={3} onClick={addItem}>
            + Agregar ítem
          </Button>
          <Text color="fg.muted" fontSize="sm" mt={2}>
            Sin porciones = las del producto (el precio escala por factor de
            porciones).
          </Text>
        </Box>

        {/* Preview en vivo */}
        {isAdmin ? (
          <Box borderWidth="1px" borderColor="border" rounded="md" p={4}>
            <Heading size="sm" mb={3}>
              Cotización
            </Heading>
            {preview.status === "idle" ? (
              <Text color="fg.muted">Elegí al menos un producto para cotizar.</Text>
            ) : null}
            {preview.status === "loading" ? (
              <Skeleton h="80px" />
            ) : null}
            {preview.status === "error" ? (
              <Alert.Root status="error">
                <Alert.Content>
                  <Alert.Description>{preview.error}</Alert.Description>
                </Alert.Content>
              </Alert.Root>
            ) : null}
            {preview.status === "done" && preview.data ? (
              <Stack gap={3}>
                {preview.data.items.map((item, idx) => (
                  <Box key={`${item.product_id}-${idx}`} px={3} py={2} bg="bg.subtle" rounded="sm">
                    <HStack justify="space-between" wrap="wrap">
                      <Text fontWeight="600">
                        {item.product_name} × {item.qty}
                      </Text>
                      <Text fontVariantNumeric="tabular-nums">
                        {formatCents(item.rounded)}
                      </Text>
                    </HStack>
                    <Text fontSize="sm" color="fg.muted" mt={1}>
                      Base {formatCents(item.price.base)} · Margen{" "}
                      {formatPct(item.price.margin_pct)} · Final{" "}
                      {formatCents(item.price.final)}
                    </Text>
                    {!item.complete ? (
                      <Alert.Root status="warning" mt={2}>
                        <Alert.Content>
                          <Alert.Description>
                            Insumos sin precio: {item.missing_ingredients.join(", ")}.
                            Se cotiza con costo 0 para esos insumos.
                          </Alert.Description>
                        </Alert.Content>
                      </Alert.Root>
                    ) : null}
                  </Box>
                ))}
                <HStack justify="space-between" pt={1}>
                  <Text fontWeight="600">Total</Text>
                  <Text fontWeight="700" fontVariantNumeric="tabular-nums">
                    {formatCents(preview.data.total)}
                  </Text>
                </HStack>
              </Stack>
            ) : null}
          </Box>
        ) : null}

        {/* Stock insuficiente (409) */}
        {stockError ? (
          <Alert.Root status="error">
            <Alert.Content>
              <Alert.Title>Stock insuficiente</Alert.Title>
              <Alert.Description>
                No se pudo {orderId ? "guardar" : "crear"} el pedido. Nada se
                descontó del stock.
              </Alert.Description>
              <Box mt={2}>
                {stockError.insufficient_stock.map((s) => (
                  <Text key={s.ingredient_id} fontSize="sm">
                    {s.ingredient_name}: disponible {s.available.toLocaleString("es-AR")}
                    , requerido {s.required.toLocaleString("es-AR")}
                  </Text>
                ))}
              </Box>
            </Alert.Content>
          </Alert.Root>
        ) : null}

        {submitError ? (
          <Alert.Root status="error">
            <Alert.Content>
              <Alert.Description>{submitError}</Alert.Description>
            </Alert.Content>
          </Alert.Root>
        ) : null}

        <HStack gap={3}>
          <Button
            colorPalette="brand"
            loading={submitting}
            onClick={() => {
              void submit();
            }}
          >
            {orderId ? "Guardar cambios" : "Crear pedido"}
          </Button>
          {orderId ? (
            <Text fontSize="sm" color="fg.muted">
              Solo se puede editar un pedido en estado nuevo.
            </Text>
          ) : null}
        </HStack>
      </Stack>
    </Flex>
  );
}
