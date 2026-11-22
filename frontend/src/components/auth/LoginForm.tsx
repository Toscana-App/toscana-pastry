"use client"

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Heading,
  Separator,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useRouter, useSearchParams } from "next/navigation";
import { authService } from "@/services/authService";
import { ApiError } from "@/lib/api";
import { gooeyToast } from "goey-toast";
import { GoogleIcon } from "@/components/ui/google-icon";
import { postLoginTarget, safeRedirectTarget } from "@/lib/portalRoutes";
import { useAuth } from "@/contexts/AuthContext";
import type { GoogleGsiCredentialResponse } from "@/types/google";

const describeApiError = (error: unknown): string => {
  if (error instanceof ApiError && error.status >= 500)
    return "Algo salió mal en el servidor. Intenta de nuevo.";
  if (error instanceof Error && error.message) return error.message;
  return "Intenta de nuevo.";
};

// The GIS script is injected by the login page from Google's CDN (RNF-P1-08).
// This component only waits for it to land in window.google.
const GIS_RETRY_ATTEMPTS = 20;
const GIS_RETRY_DELAY_MS = 150;

const NO_ACCOUNT_FALLBACK =
  "No pudimos vincular tu cuenta de Google. Volvé a intentar.";

export default function LoginForm({
  googleClientId,
}: {
  googleClientId?: string;
}) {
  const [gsiReady, setGsiReady] = useState(false);
  const [nonce, setNonce] = useState<string | null>(null);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [signingIn, setSigningIn] = useState(false);
  const buttonRef = useRef<HTMLDivElement | null>(null);
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refresh } = useAuth();

  const resolvePostLogin = (role: Parameters<typeof postLoginTarget>[0]) =>
    safeRedirectTarget(
      searchParams.get("from"),
      postLoginTarget(role),
    );

  // 1) Probe for the GIS global (bounded retry, honest failure).
  useEffect(() => {
    if (!googleClientId) return;
    let cancelled = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const probe = () => {
      if (cancelled) return;
      if (window.google?.accounts?.id) {
        setGsiReady(true);
        return;
      }
      attempts += 1;
      if (attempts >= GIS_RETRY_ATTEMPTS) {
        setGoogleError(
          "No pudimos cargar el acceso con Google. Recargá la página.",
        );
        return;
      }
      timer = setTimeout(probe, GIS_RETRY_DELAY_MS);
    };

    probe();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [googleClientId]);

  // 2) Ask the backend for the server-issued nonce (bound to a pre-auth cookie).
  useEffect(() => {
    if (!gsiReady || !googleClientId) return;
    let cancelled = false;
    authService
      .fetchGoogleNonce()
      .then(({ nonce }) => {
        if (!cancelled) setNonce(nonce);
      })
      .catch(() => {
        if (!cancelled)
          setGoogleError(
            "No pudimos preparar el acceso con Google. Recargá la página.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [gsiReady, googleClientId]);

  const handleCredential = useCallback(
    async (response: GoogleGsiCredentialResponse) => {
      setSigningIn(true);
      setGoogleError(null);
      try {
        const data = await authService.loginWithGoogleCredential(
          response.credential,
        );
        gooeyToast.success("¡Sesión iniciada!");
        await refresh();
        router.replace(resolvePostLogin(data.role));
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          const detail = (
            error.payload as
              | { detail?: { message?: string; state?: string } }
              | null
          )?.detail;
          if (
            detail &&
            (detail.state === "no_account" || detail.state === "link_pending")
          ) {
            setGoogleError(detail.message ?? NO_ACCOUNT_FALLBACK);
          } else {
            setGoogleError(NO_ACCOUNT_FALLBACK);
          }
        } else if (error instanceof ApiError && error.status === 401) {
          setGoogleError(
            "No pudimos validar tu cuenta de Google. Volvé a intentar.",
          );
        } else {
          gooeyToast.error("¡Ups! No se pudo iniciar sesión con Google", {
            description: describeApiError(error),
          });
        }
      } finally {
        setSigningIn(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [refresh, router, searchParams],
  );

  // 3) Initialize with the fetched nonce and render the button.
  useEffect(() => {
    if (!gsiReady || !nonce || !googleClientId || !buttonRef.current) return;
    const id = window.google?.accounts?.id;
    if (!id) return;
    id.initialize({
      client_id: googleClientId,
      callback: (response) => {
        void handleCredential(response);
      },
      auto_select: false,
      cancel_on_tap_outside: true,
      nonce,
    });
    id.renderButton(buttonRef.current, {
      theme: "outline",
      size: "large",
      text: "continue_with",
      width: "auto",
    });
  }, [gsiReady, nonce, googleClientId, handleCredential]);

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

        {googleClientId ? (
          <>
            <Box
              ref={buttonRef}
              width="full"
              minH={12}
              display="flex"
              justifyContent="center"
            >
              {signingIn && (
                <Text fontSize="sm" color="fg.muted">
                  Iniciando sesión…
                </Text>
              )}
            </Box>
            {googleError && (
              <Alert.Root status="error" width="full" borderRadius="md">
                <Alert.Content>
                  <Alert.Description fontSize="sm">
                    {googleError}
                  </Alert.Description>
                </Alert.Content>
              </Alert.Root>
            )}
          </>
        ) : (
          <Stack gap={2} width="full" align="center">
            <Box opacity={0.5}>
              <GoogleIcon />
            </Box>
            <Text color="fg.muted" textAlign="center" fontSize="sm">
              Acceso con Google no configurado
            </Text>
          </Stack>
        )}
      </Stack>
    </Box>
  );
}
