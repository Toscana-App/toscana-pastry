import Script from "next/script";
import { headers } from "next/headers";
import { Suspense } from "react";
import {
  Box,
  Button,
  Container,
  Heading,
  Separator,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react";

import LoginForm from "@/components/auth/LoginForm";
import { BrandLogo } from "@/components/layout/BrandLogo";
import { GoogleIcon } from "@/components/ui/google-icon";

function LoginFormPlaceholder() {
  return (
    <Box
      width="100%"
      maxW="400px"
      p={8}
      borderRadius="lg"
      borderWidth="1px"
      borderColor="border"
      boxShadow="lg"
      bg="bg.panel"
    >
      <Stack gap={6} align="center">
        <Heading as="h1" fontSize="2xl">Iniciar sesión</Heading>
        <Text color="fg.muted" textAlign="center">
          Continúa con tu cuenta de Google
        </Text>
        <Separator />
        <Button variant="outline" size="lg" width="full" disabled>
          <GoogleIcon />
          Continuar con Google
        </Button>
      </Stack>
    </Box>
  );
}

// Server component: the GIS client id is a runtime env var shared with the
// backend (RNF-P1-08: single source of truth, never NEXT_PUBLIC). Reading
// headers() keeps the segment dynamic (the `dynamic` route segment config is
// not compatible with nextConfig.cacheComponents), so the value comes from
// the running server, not baked in at build time.
export const metadata = {
  other: { "google-client-id": process.env.GOOGLE_CLIENT_ID || undefined },
};

export default function LoginPage() {
  headers();
  const googleClientId = process.env.GOOGLE_CLIENT_ID ?? "";
  return (
    <>
      {/* Always from Google's CDN, never vendored (RNF-P1-08). */}
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="beforeInteractive"
      />
      <Container
        maxW="2xl"
        py={20}
        display="flex"
        alignItems="center"
        justifyContent="center"
        minH="100dvh"
      >
        <VStack gap={8} width="full" align="center">
          <BrandLogo variant="vertical" height={150} priority />
          <Suspense fallback={<LoginFormPlaceholder />}>
            <LoginForm googleClientId={googleClientId || undefined} />
          </Suspense>
        </VStack>
      </Container>
    </>
  );
}
