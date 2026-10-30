"use client"

import { useState } from "react";
import {
  Box,
  Button,
  Field,
  Input,
  Stack,
  Heading,
  Text,
  Separator,
} from "@chakra-ui/react";
import { authService } from "@/services/authService";
import { GoogleIcon } from "@/components/ui/google-icon";
import { toaster } from "@/lib/toaster";
import { useRouter, useSearchParams } from "next/navigation";
import { postLoginTarget, safeRedirectTarget } from "@/lib/portalRoutes";
import { UserRole } from "@/types/auth";

export default function LoginForm() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();

  /**
   * Post-login landing (F1 — p11 portal shell):
   * - valid `?from` (internal relative route) → there
   * - otherwise by role: admin → /admin, portal → /products
   */
  const resolvePostLogin = (role: UserRole): string =>
    safeRedirectTarget(searchParams.get("from"), postLoginTarget(role));

  const handleMagicLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      // authService persiste access_token y refresh_token en cookies.
      const data = await authService.loginWithMagicLink(email);
      toaster.create({
        title: "Link de acceso enviado",
        description: "Revisá tu correo para ingresar.",
        type: "success",
      });
      router.push(resolvePostLogin(data.role));
    } catch (error) {
      toaster.create({
        title: "No se pudo iniciar sesión",
        description: error instanceof Error ? error.message : "Intentá de nuevo",
        type: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setLoading(true);
    try {
      const data = await authService.loginWithGoogle("google_test_id");
      toaster.create({
        title: "¡Sesión iniciada!",
        type: "success",
      });
      router.push(resolvePostLogin(data.role));
    } catch (error) {
      toaster.create({
        title: "No se pudo iniciar sesión con Google",
        description: error instanceof Error ? error.message : "Intentá de nuevo",
        type: "error",
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
      borderColor="gray.200"
      boxShadow="lg"
      bg="white"
    >
      <Stack gap={6} align="center">
        <Heading fontSize="2xl" color="brand.600">
          Iniciar sesión
        </Heading>
        <Text color="gray.500" textAlign="center">
          Elige un método para continuar
        </Text>
        <Separator />

        <form onSubmit={handleMagicLink} style={{ width: "100%" }}>
          <Stack gap={4}>
            <Field.Root required>
              <Field.Label>
                Correo electrónico
                <Field.RequiredIndicator />
              </Field.Label>
              <Input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field.Root>
            <Button
              type="submit"
              colorPalette="brand"
              loading={loading}
              width="full"
            >
              Enviar link de acceso
            </Button>
          </Stack>
        </form>

        <Text fontSize="sm" color="gray.500">o</Text>

        <Button
          onClick={handleGoogleLogin}
          loading={loading}
          variant="outline"
          width="full"
        >
          <GoogleIcon />
          Continuar con Google
        </Button>
      </Stack>
    </Box>
  );
}
