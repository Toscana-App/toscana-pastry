"use client";

/** Paso 4 — Pago (RF-P11-07): Mercado Pago o efectivo en la entrega.

La ejecución del pago online (redirect + polling) es F3; aquí el usuario
elige el método y lo queda snapshoteado en el pedido (C1).
*/

import {
  Box,
  Button,
  Flex,
  RadioGroup,
  Stack,
  Text,
} from "@chakra-ui/react";
import { PaymentMethod } from "@/types/orders";

export function StepPayment({
  value,
  onChange,
  onNext,
  onBack,
}: {
  value: PaymentMethod;
  onChange: (method: PaymentMethod) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  return (
    <Stack gap={4} maxW="md">
      <RadioGroup.Root
        value={value}
        onValueChange={(details) =>
          onChange(String(details.value) as PaymentMethod)
        }
      >
        <Stack gap={2} width="100%">
          <RadioGroup.Item value="mercadopago">
            <RadioGroup.ItemControl />
            <RadioGroup.ItemText as="div" width="100%">
              <Box
                borderWidth="1px"
                borderColor="border.muted"
                rounded="md"
                p={3}
                cursor="pointer"
                onClick={() => onChange("mercadopago")}
              >
                <Text fontWeight="semibold">Mercado Pago</Text>
                <Text fontSize="sm" color="fg.muted">
                  Pago online: tarjeta, transferencia o saldo. Redirigimos a la
                  pasarela segura.
                </Text>
              </Box>
            </RadioGroup.ItemText>
          </RadioGroup.Item>

          <RadioGroup.Item value="cash">
            <RadioGroup.ItemControl />
            <RadioGroup.ItemText as="div" width="100%">
              <Box
                borderWidth="1px"
                borderColor="border.muted"
                rounded="md"
                p={3}
                cursor="pointer"
                onClick={() => onChange("cash")}
              >
                <Text fontWeight="semibold">Efectivo</Text>
                <Text fontSize="sm" color="fg.muted">
                  Pagás en efectivo en la entrega (o en el retiro).
                </Text>
              </Box>
            </RadioGroup.ItemText>
          </RadioGroup.Item>
        </Stack>
      </RadioGroup.Root>

      <Flex justify="space-between" gap={3}>
        <Button variant="outline" onClick={onBack}>
          Volver
        </Button>
        <Button colorPalette="brand" onClick={onNext}>
          Continuar
        </Button>
      </Flex>
    </Stack>
  );
}
