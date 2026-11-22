"use client";

import { Container, Heading } from "@chakra-ui/react";
import LeadForm from "@/components/contact/LeadForm";

export default function ContactoPage() {
  return (
    <Container maxW="2xl" py={10}>
      <Heading as="h1" fontSize="2xl" mb={6}>
        Contacto
      </Heading>
      <LeadForm />
    </Container>
  );
}
