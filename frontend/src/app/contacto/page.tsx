"use client";

import { Container, Heading } from "@chakra-ui/react";
import LeadForm from "@/components/contact/LeadForm";

/** Página pública de contacto (F4 — captura de lead, RF-P11-13). */
export default function ContactoPage() {
  return (
    <Container maxW="container.sm" py={10}>
      <Heading size="2xl" mb={6}>
        Contacto
      </Heading>
      <LeadForm />
    </Container>
  );
}
