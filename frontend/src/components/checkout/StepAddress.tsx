"use client";

/** Paso 2 — Dirección (RF-P11-05): elegir del libro o crear una nueva.

La nueva dirección se crea contra el libro (C2) al confirmar este paso.
La dirección es opcional aquí: la obligatoriedad la decide el paso 3
(modalidad delivery) según la spec.
*/

import { zodResolver } from "@hookform/resolvers/zod";
import {
  Box,
  Button,
  Field,
  Flex,
  Input,
  RadioGroup,
  Separator,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { toaster } from "@/lib/toaster";
import { createMyAddress } from "@/services/ordersService";
import { Address, addressToLine } from "@/types/orders";
import { AddressSelection } from "./checkoutTypes";

const newAddressSchema = z.object({
  street_line_1: z.string().min(1, "La calle es obligatoria"),
  street_line_2: z.string().optional().or(z.literal("")),
  city: z.string().optional().or(z.literal("")),
  postal_code: z.string().optional().or(z.literal("")),
  province: z.string().optional().or(z.literal("")),
  phone: z.string().optional().or(z.literal("")),
});

type NewAddressForm = z.infer<typeof newAddressSchema>;

export function StepAddress({
  addresses,
  initial,
  onNext,
}: {
  addresses: Address[];
  initial: AddressSelection | null;
  onNext: (data: AddressSelection) => void;
}) {
  const [selectedId, setSelectedId] = useState<string | "new" | null>(
    initial?.addressId ?? null
  );
  const [showNewForm, setShowNewForm] = useState(
    selectedId === "new" || addresses.length === 0
  );
  const [saving, setSaving] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<NewAddressForm>({
    resolver: zodResolver(newAddressSchema),
    defaultValues: {
      street_line_1: "",
      street_line_2: "",
      city: "",
      postal_code: "",
      province: "",
      phone: "",
    },
  });

  const handleSaveNew = handleSubmit(async (data) => {
    setSaving(true);
    try {
      const { address } = await createMyAddress({
        street_line_1: data.street_line_1,
        street_line_2: data.street_line_2 || null,
        city: data.city || null,
        postal_code: data.postal_code || null,
        province: data.province || null,
        phone: data.phone || null,
      });
      // Se guardó en el libro (C2): se elige en el pedido por su línea.
      onNext({ addressId: address.id, line: addressToLine(address) });
    } catch (error) {
      toaster.create({
        title: "No se pudo guardar la dirección",
        description:
          error instanceof Error ? error.message : "Intentá de nuevo",
        type: "error",
      });
    } finally {
      setSaving(false);
    }
  });

  const chooseSaved = (address: Address) => {
    setSelectedId(address.id);
    setShowNewForm(false);
    onNext({ addressId: address.id, line: addressToLine(address) });
  };

  const skip = () => {
    onNext({ addressId: null, line: "" });
  };

  return (
    <Stack gap={4} maxW="md">
      {addresses.length > 0 ? (
        <RadioGroup.Root
          value={selectedId === "new" ? null : selectedId}
          onValueChange={(details) => {
            if (details.value === null) return;
            const id = String(details.value);
            const address = addresses.find((a) => a.id === id);
            if (address) {
              chooseSaved(address);
            }
          }}
          disabled={saving}
        >
          <Stack gap={2} width="100%">
            {addresses.map((address) => (
              <Box
                key={address.id}
                borderWidth="1px"
                borderColor="border.muted"
                rounded="md"
                p={3}
              >
                <RadioGroup.Item value={address.id}>
                  <RadioGroup.ItemControl />
                  <RadioGroup.ItemText as="div" width="100%">
                    <Flex
                      align="center"
                      justify="space-between"
                      gap={2}
                      onClick={() => chooseSaved(address)}
                      cursor="pointer"
                    >
                      <Text fontSize="sm">{addressToLine(address)}</Text>
                      {address.is_default && (
                        <Text fontSize="xs" color="brand.600">
                          Principal
                        </Text>
                      )}
                    </Flex>
                  </RadioGroup.ItemText>
                </RadioGroup.Item>
              </Box>
            ))}

            <RadioGroup.Item value="new">
              <RadioGroup.ItemControl />
              <RadioGroup.ItemText as="div" width="100%">
                <Text
                  fontSize="sm"
                  fontWeight="semibold"
                  cursor="pointer"
                  onClick={() => setShowNewForm(true)}
                >
                  ➕ Usar una nueva dirección
                </Text>
              </RadioGroup.ItemText>
            </RadioGroup.Item>
          </Stack>
        </RadioGroup.Root>
      ) : (
        <Text color="fg.muted" fontSize="sm">
          Todavía no tenés direcciones guardadas.
        </Text>
      )}

      {/* Formulario de nueva dirección */}
      {showNewForm && (
        <Box
          borderWidth="1px"
          borderColor="border.muted"
          rounded="md"
          p={4}
        >
          <Stack gap={3}>
            <Field.Root invalid={!!errors.street_line_1}>
              <Field.Label>Calle y número *</Field.Label>
              <Input
                placeholder="Av. Siempreviva 742"
                aria-describedby={
                  errors.street_line_1 ? "addr-street1-error" : undefined
                }
                {...register("street_line_1")}
              />
              <Field.ErrorText id="addr-street1-error">
                {errors.street_line_1?.message}
              </Field.ErrorText>
            </Field.Root>

            <Field.Root>
              <Field.Label>Piso / departamento</Field.Label>
              <Input placeholder="Opcional" {...register("street_line_2")} />
            </Field.Root>

            <Flex gap={3} wrap="wrap">
              <Field.Root>
                <Field.Label>Ciudad</Field.Label>
                <Input placeholder="Opcional" {...register("city")} />
              </Field.Root>
              <Field.Root>
                <Field.Label>Código postal</Field.Label>
                <Input placeholder="Opcional" {...register("postal_code")} />
              </Field.Root>
              <Field.Root>
                <Field.Label>Provincia</Field.Label>
                <Input placeholder="Opcional" {...register("province")} />
              </Field.Root>
            </Flex>

            <Field.Root>
              <Field.Label>Teléfono de contacto</Field.Label>
              <Input placeholder="Opcional" {...register("phone")} />
            </Field.Root>

            <Flex gap={3} justify="flex-end" wrap="wrap">
              <Button variant="outline" onClick={skip} disabled={saving}>
                Omitir (retiro)
              </Button>
              <Button
                colorPalette="brand"
                loading={saving}
                onClick={handleSaveNew}
              >
                Guardar y continuar
              </Button>
            </Flex>
          </Stack>
        </Box>
      )}

      {addresses.length > 0 && !showNewForm && (
        <Flex justify="flex-end">
          <Button variant="ghost" onClick={skip} disabled={saving}>
            Continuar sin dirección (retiro)
          </Button>
        </Flex>
      )}

      <Separator />
      <Text fontSize="xs" color="fg.muted">
        Si elegís entrega a domicilio en el próximo paso, la dirección será
        obligatoria.
      </Text>
    </Stack>
  );
}
