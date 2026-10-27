"use client";

/** Step 3 — Delivery (RF-P11-06): date ≥ today + min_lead_days, mode. */

import {
  Box,
  Button,
  Flex,
  Field,
  Input,
  SegmentGroup,
  Stack,
  Text,
} from "@chakra-ui/react";
import { DeliveryMode } from "@/types/orders";
import { DeliveryData } from "./checkoutTypes";

/** Tenant min_lead_days (default 2 — RF-P11-06; not exposed in the API yet). */
const MIN_LEAD_DAYS = 2;

function todayPlus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function StepDelivery({
  data,
  addressSet,
  onChange,
  onNext,
  onBack,
}: {
  data: DeliveryData;
  addressSet: boolean;
  onChange: (data: DeliveryData) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const minDate = todayPlus(MIN_LEAD_DAYS);
  const dateInvalid =
    data.date === "" || data.date < minDate || data.date > todayPlus(90);

  const missingAddress = data.delivery_mode === "delivery" && !addressSet;
  const canContinue = !dateInvalid && !missingAddress;

  return (
    <Stack gap={4} maxW="md">
      <Field.Root invalid={dateInvalid}>
        <Field.Label>Fecha de entrega</Field.Label>
        <Input
          type="date"
          value={data.date}
          min={minDate}
          max={todayPlus(90)}
          aria-describedby="delivery-date-hint"
          onChange={(e) => onChange({ ...data, date: e.target.value })}
        />
        <Field.HelperText id="delivery-date-hint">
          Mínimo {MIN_LEAD_DAYS} días de anticipación.
        </Field.HelperText>
      </Field.Root>

      <Field.Root>
        <Field.Label>Modalidad</Field.Label>
        <SegmentGroup.Root
          value={data.delivery_mode}
          onValueChange={(details) =>
            onChange({
              ...data,
              delivery_mode: details.value as DeliveryMode,
            })
          }
        >
          <SegmentGroup.Items
            items={[
              { value: "delivery", label: "A domicilio" },
              { value: "pickup", label: "Retiro" },
            ]}
          />
        </SegmentGroup.Root>
      </Field.Root>

      {missingAddress && (
        <Box
          borderWidth="1px"
          borderColor="orange.300"
          bg="orange.50"
          rounded="md"
          p={3}
        >
          <Text fontSize="sm" color="orange.700">
            Para entrega a domicilio necesitás una dirección: volvé al paso 2
            para elegirla o crearla.
          </Text>
        </Box>
      )}

      <Flex justify="space-between" gap={3}>
        <Button variant="outline" onClick={onBack}>
          Volver
        </Button>
        <Button colorPalette="brand" disabled={!canContinue} onClick={onNext}>
          Continuar
        </Button>
      </Flex>
    </Stack>
  );
}
