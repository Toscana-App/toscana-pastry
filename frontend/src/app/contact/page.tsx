"use client";

import { Container, Heading } from "@chakra-ui/react";
import LeadForm from "@/components/contact/LeadForm";

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
