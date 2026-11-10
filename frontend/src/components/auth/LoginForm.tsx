"use client"

import { useState } from "react";
import {
  Box,
  Button,
  Stack,
  Heading,
  Text,
  Separator,
} from "@chakra-ui/react";
import { authService } from "@/services/authService";
import { ApiError } from "@/lib/api";
import { GoogleIcon } from "@/components/ui/google-icon";
import { gooeyToast } from "goey-toast";
import { useSearchParams } from "next/navigation";
import { postLoginTarget, safeRedirectTarget } from "@/lib/portalRoutes";
import { UserRole } from "@/types/auth";

const describeApiError = (error: unknown): string => {
  if (error instanceof ApiError && error.status >= 500)
    return "Algo salió mal en el servidor. Intenta de nuevo.";
  if (error instanceof Error && error.message)
    return error.message;
  return "Intenta de nuevo.";
};

const goPostLogin = (target: string) => {
  window.location.assign(target);
};

export default function LoginForm() {
  const [loading, setLoading] = useState(false);
  const searchParams = useSearchParams();

  const resolvePostLogin = (role: UserRole): string =>
    safeRedirectTarget(searchParams.get("from"), postLoginTarget(role));

  const handleGoogleLogin = async () => {
    setLoading(true);
    try {
      const data = await authService.loginWithGoogle("google_test_id");
      gooeyToast.success("¡Sesión iniciada!");
      goPostLogin(resolvePostLogin(data.role));
    } catch (error) {
      gooeyToast.error("¡Ups! No se pudo iniciar sesión con Google", {
        description: describeApiError(error),
      });
    } finally {
      setLoading(false);
    }
  };

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
        <Heading as="h1" fontSize="2xl">
          Iniciar sesión
        </Heading>
        <Text color="fg.muted" textAlign="center">
          Continúa con tu cuenta de Google
        </Text>
        <Separator />

        <Button
          onClick={handleGoogleLogin}
          loading={loading}
          variant="outline"
          size="lg"
          width="full"
        >
          <GoogleIcon />
          Continuar con Google
        </Button>
      </Stack>
    </Box>
  );
}
