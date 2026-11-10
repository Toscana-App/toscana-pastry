import { Box, Container, Flex, Link, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { BrandLogo } from "@/components/layout/BrandLogo";

export const PORTAL_CONTACT = {
  whatsappDisplay: "+54 9 3571 555328",
  whatsappUrl: "https://wa.me/5493571555328",
  email: "toscana2407@gmail.com",
} as const;

const FOOTER_LINKS = [
  { label: "Catálogo", href: "/" },
  { label: "Mis pedidos", href: "/my-orders" },
  { label: "Mi cuenta", href: "/profile" },
] as const;

export function PortalFooter() {
  return (
    <Box as="footer" mt={{ base: 12, md: 16 }} bg="bg.panel" borderTopWidth="1px" borderColor="border.muted">
      <Container maxW="5xl" py={{ base: 10, md: 12 }}>
        <Flex
          direction={{ base: "column", sm: "row" }}
          gap={{ base: 10, md: 12 }}
          justify="space-between"
        >
          <Box maxW="xs">
            <BrandLogo variant="horizontal" height={30} />
            <Text mt={4} fontSize="sm" color="fg.muted" lineHeight="tall" textWrap="pretty">
              Pastelería artesanal. Sin gluten, sanos y ricos.
            </Text>
          </Box>

          <Box>
            <Text fontSize="sm" fontWeight="semibold" color="fg" mb={3}>
              Enlaces
            </Text>
            <Box as="ul" listStyleType="none" display="flex" flexDirection="column" gap={2}>
              {FOOTER_LINKS.map(({ label, href }) => (
                <Box as="li" key={href}>
                  <Link asChild fontSize="sm" color="fg.muted" _hover={{ textDecoration: "underline", textUnderlineOffset: "3px" }}>
                    <NextLink href={href}>{label}</NextLink>
                  </Link>
                </Box>
              ))}
            </Box>
          </Box>

          <Box>
            <Text fontSize="sm" fontWeight="semibold" color="fg" mb={3}>
              Contactános
            </Text>
            <Box as="ul" listStyleType="none" display="flex" flexDirection="column" gap={2}>
              <Box as="li">
                <Link
                  href={PORTAL_CONTACT.whatsappUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  fontSize="sm"
                  color="fg.muted"
                  _hover={{ textDecoration: "underline", textUnderlineOffset: "3px" }}
                >
                  WhatsApp: {PORTAL_CONTACT.whatsappDisplay}
                </Link>
              </Box>
              <Box as="li">
                <Link
                  href={`mailto:${PORTAL_CONTACT.email}`}
                  fontSize="sm"
                  color="fg.muted"
                  _hover={{ textDecoration: "underline", textUnderlineOffset: "3px" }}
                >
                  {PORTAL_CONTACT.email}
                </Link>
              </Box>
            </Box>
          </Box>
        </Flex>

        <Box mt={10} pt={5} borderTopWidth="1px" borderColor="border.muted" textAlign="center">
          <Text fontSize="xs" color="fg.muted">
            © {new Date().getFullYear()} Toscana Pastry. Todos los derechos reservados.
          </Text>
        </Box>
      </Container>
    </Box>
  );
}
