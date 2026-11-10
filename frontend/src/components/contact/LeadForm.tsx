"use client";


import {
  Alert,
  Box,
  Button,
  Card,
  Field,
  Flex,
  Input,
  RadioGroup,
  Stack,
  Textarea,
} from "@chakra-ui/react";
import { useState } from "react";
import { createLead } from "@/services/leadsService";
import { CustomerType } from "@/types/leads";

function LeadForm() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [customerType, setCustomerType] = useState<CustomerType>("consumer");
  const [message, setMessage] = useState("");
  const [phone, setPhone] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [location, setLocation] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await createLead({
        name: name.trim(),
        email: email.trim(),
        customer_type: customerType,
        message: message.trim(),
        phone: phone.trim() || null,
        business_name:
          customerType === "business" ? businessName.trim() || null : null,
        location:
          customerType === "business" ? location.trim() || null : null,
      });
      setSent(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No se pudo enviar el mensaje"
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (sent) {
    return (
      <Card.Root>
        <Card.Body>
          <Stack align="center" gap={3} py={8} textAlign="center">
            <Alert.Root status="success">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Title>¡Mensaje enviado!</Alert.Title>
                <Alert.Description>
                  Te vamos a responder a {email} lo antes posible.
                </Alert.Description>
              </Alert.Content>
            </Alert.Root>
          </Stack>
        </Card.Body>
      </Card.Root>
    );
  }

  const canSubmit =
    name.trim() !== "" && email.trim() !== "" && message.trim() !== "";

  return (
    <Card.Root>
      <Card.Body>
        <Stack gap={4}>
          <Flex gap={3} wrap="wrap">
            <Box flex="1" minW="220px">
              <Field.Root>
                <Field.Label>Nombre</Field.Label>
                <Input
                  name="name"
                  autoComplete="name"
                  placeholder="Tu nombre…"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </Field.Root>
            </Box>
            <Box flex="1" minW="220px">
              <Field.Root>
                <Field.Label>Email</Field.Label>
                <Input
                  type="email"
                  name="email"
                  autoComplete="email"
                  inputMode="email"
                  spellCheck={false}
                  placeholder="tu@email.com…"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field.Root>
            </Box>
          </Flex>

          <Field.Root>
            <Field.Label>Soy…</Field.Label>
            <RadioGroup.Root
              value={customerType}
              onValueChange={(details) =>
                setCustomerType(details.value as CustomerType)
              }
            >
              <RadioGroup.Item value="consumer">
                <RadioGroup.ItemHiddenInput />
                <RadioGroup.ItemControl />
                <RadioGroup.ItemText>
                  Consumidora (quiero hacer un pedido)
                </RadioGroup.ItemText>
              </RadioGroup.Item>
              <RadioGroup.Item value="business">
                <RadioGroup.ItemHiddenInput />
                <RadioGroup.ItemControl />
                <RadioGroup.ItemText>
                  Negocio (quiero revender)
                </RadioGroup.ItemText>
              </RadioGroup.Item>
            </RadioGroup.Root>
          </Field.Root>

          {customerType === "business" && (
            <Flex gap={3} wrap="wrap">
              <Box flex="1" minW="220px">
                <Field.Root>
                  <Field.Label>Razón social</Field.Label>
                  <Input
                    name="business_name"
                    autoComplete="organization"
                    placeholder="Nombre del negocio…"
                    value={businessName}
                    onChange={(e) => setBusinessName(e.target.value)}
                  />
                </Field.Root>
              </Box>
              <Box flex="1" minW="220px">
                <Field.Root>
                  <Field.Label>Ubicación</Field.Label>
                  <Input
                    name="location"
                    autoComplete="off"
                    placeholder="Ciudad, provincia…"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                  />
                </Field.Root>
              </Box>
            </Flex>
          )}

          <Box>
            <Field.Root>
              <Field.Label>Mensaje</Field.Label>
              <Textarea
                rows={4}
                name="message"
                autoComplete="off"
                placeholder="Contanos qué necesitás…"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </Field.Root>
          </Box>

          <Box>
            <Field.Root>
              <Field.Label>Teléfono (opcional)</Field.Label>
              <Input
                type="tel"
                name="phone"
                autoComplete="tel"
                inputMode="tel"
                placeholder="11 2345 6789…"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </Field.Root>
          </Box>

          {error && (
            <Alert.Root status="error" aria-live="polite">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Description>{error}</Alert.Description>
              </Alert.Content>
            </Alert.Root>
          )}

          <Flex justify="flex-end">
            <Button
              colorPalette="brand"
              loading={submitting}
              disabled={!canSubmit}
              onClick={() => void submit()}
            >
              Enviar mensaje
            </Button>
          </Flex>
        </Stack>
      </Card.Body>
    </Card.Root>
  );
}

export default LeadForm;
