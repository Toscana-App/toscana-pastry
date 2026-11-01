"use client";

/** Step 1 — Contact (RF-P11-04): pre-filled from the user, E.164 phone. */

import { zodResolver } from "@hookform/resolvers/zod";
import { Button, Flex, Field, Input, Stack, Text } from "@chakra-ui/react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { normalizePhoneE164 } from "@/lib/phone";
import { ContactData } from "./checkoutTypes";

const phoneE164 = z
  .string()
  .min(1, "El teléfono es obligatorio")
  .refine((v) => normalizePhoneE164(v) !== null, {
    message: "Teléfono inválido (mín. 10 dígitos)",
  });

const contactSchema = z.object({
  name: z.string().min(1, "El nombre es obligatorio"),
  phone: phoneE164,
  email: z.string().email("Email inválido"),
});

type ContactForm = z.infer<typeof contactSchema>;

export function StepContact({
  userEmail,
  onNext,
}: {
  userEmail: string | null;
  onNext: (data: ContactData) => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ContactForm>({
    resolver: zodResolver(contactSchema),
    defaultValues: { name: "", phone: "", email: userEmail ?? "" },
  });

  return (
    <Stack gap={4} maxW="md">
      <Text color="fg.muted">
        Datos de contacto precargados desde tu cuenta.
      </Text>

      <Field.Root invalid={!!errors.name}>
        <Field.Label htmlFor="contact-name">Nombre</Field.Label>
        <Input
          id="contact-name"
          placeholder="Tu nombre"
          aria-invalid={!!errors.name}
          aria-describedby={errors.name ? "contact-name-error" : undefined}
          {...register("name")}
        />
        <Field.ErrorText id="contact-name-error">
          {errors.name?.message}
        </Field.ErrorText>
      </Field.Root>

      <Field.Root invalid={!!errors.phone}>
        <Field.Label htmlFor="contact-phone">
          Teléfono (WhatsApp)
        </Field.Label>
        <Input
          id="contact-phone"
          placeholder="+54 9 11 5555-5555"
          inputMode="tel"
          aria-invalid={!!errors.phone}
          aria-describedby={
            errors.phone ? "contact-phone-error" : "contact-phone-hint"
          }
          {...register("phone")}
        />
        <Field.HelperText id="contact-phone-hint">
          Formato local o internacional; se normaliza a +54.
        </Field.HelperText>
        <Field.ErrorText id="contact-phone-error">
          {errors.phone?.message}
        </Field.ErrorText>
      </Field.Root>

      <Field.Root invalid={!!errors.email}>
        <Field.Label htmlFor="contact-email">Email</Field.Label>
        <Input
          id="contact-email"
          type="email"
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? "contact-email-error" : undefined}
          {...register("email")}
        />
        <Field.ErrorText id="contact-email-error">
          {errors.email?.message}
        </Field.ErrorText>
      </Field.Root>

      <Flex justify="flex-end">
        <Button
          colorPalette="brand"
          onClick={handleSubmit((values) =>
            onNext({
              name: values.name.trim(),
              phone: normalizePhoneE164(values.phone)!,
              email: values.email.trim(),
            })
          )}
        >
          Continuar
        </Button>
      </Flex>
    </Stack>
  );
}
