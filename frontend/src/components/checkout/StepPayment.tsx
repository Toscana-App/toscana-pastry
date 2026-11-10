"use client";


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
            <RadioGroup.ItemHiddenInput />
            <RadioGroup.ItemControl />
            <RadioGroup.ItemText as="div" width="100%">
              <Box
                borderWidth="1px"
                borderColor="border.muted"
                rounded="md"
                p={3}
                cursor="pointer"
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
            <RadioGroup.ItemHiddenInput />
            <RadioGroup.ItemControl />
            <RadioGroup.ItemText as="div" width="100%">
              <Box
                borderWidth="1px"
                borderColor="border.muted"
                rounded="md"
                p={3}
                cursor="pointer"
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
