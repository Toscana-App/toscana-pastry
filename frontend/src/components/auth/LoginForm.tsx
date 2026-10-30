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
import { ApiError } from "@/lib/api";
import { GoogleIcon } from "@/components/ui/google-icon";
import { gooeyToast } from "goey-toast";
import { useSearchParams } from "next/navigation";
import { postLoginTarget, safeRedirectTarget } from "@/lib/portalRoutes";
import { UserRole } from "@/types/auth";

/**
 * Client-side email validation for the login form (P1, spec line 77):
 * the error renders inline under the input (Alert danger via Field.Error),
 * so the native browser bubble is disabled with noValidate.
 */
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const validateEmail = (value: string): string | null => {
  if (!value.trim()) return "El email es obligatorio.";
  if (!EMAIL_PATTERN.test(value.trim()))
    return "¡Ups! El email no es válido.";
  return null;
};

/** Server-side failures are never shown verbatim (they can be English). */
const describeApiError = (error: unknown): string => {
  if (error instanceof ApiError && error.status >= 500)
    return "Algo salió mal en el servidor. Intenta de nuevo.";
  if (error instanceof Error && error.message)
    return error.message;
  return "Intenta de nuevo.";
};

/**
 * Post-login navigation is a full page load, not router.push: the session
 * lives in cookies and AuthContext only reads it on mount, so a
 * client-side navigation to a ProtectedRoute (e.g. /admin) would see a
 * stale "unauthenticated" state and bounce back to /login.
 */
const goPostLogin = (target: string) => {
  window.location.assign(target);
};

export default function LoginForm() {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
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
    const error = validateEmail(email);
    if (error) {
      setEmailError(error);
      return;
    }
    setEmailError(null);
    setLoading(true);
    try {
      // authService persiste access_token y refresh_token en cookies.
      const data = await authService.loginWithMagicLink(email);
      gooeyToast.success("¡Link de acceso enviado!", {
        description: "Revisa tu correo para ingresar.",
      });
      goPostLogin(resolvePostLogin(data.role));
    } catch (error) {
      gooeyToast.error("¡Ups! No se pudo iniciar sesión", {
        description: describeApiError(error),
      });
    } finally {
      setLoading(false);
    }
  };

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

        <form onSubmit={handleMagicLink} noValidate style={{ width: "100%" }}>
          <Stack gap={4}>
            <Field.Root required invalid={emailError !== null}>
              <Field.Label>
                Correo electrónico
                <Field.RequiredIndicator />
              </Field.Label>
              <Input
                type="email"
                placeholder="you@example.com"
                aria-describedby={emailError ? "email-error" : undefined}
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (emailError) setEmailError(null);
                }}
              />
              {emailError && (
                <Field.ErrorText id="email-error">{emailError}</Field.ErrorText>
              )}
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
