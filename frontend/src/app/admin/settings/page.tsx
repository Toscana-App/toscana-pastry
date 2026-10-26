"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Button,
  Card,
  Container,
  Field,
  Flex,
  Heading,
  Input,
  Spinner,
  Text,
  VStack,
} from "@chakra-ui/react";
import { useAuth } from "@/contexts/AuthContext";
import { fetchSettings, updateSettings } from "@/services/pricingService";
import { toaster } from "@/lib/toaster";
import type { SettingsResponse, SettingsUpdatePayload } from "@/types/pricing";

/** The consumer markup percentage range. */
const MARKUP_MIN = 0;
const MARKUP_MAX = 100;

export default function AdminSettingsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [markupInput, setMarkupInput] = useState("");
  const [markupError, setMarkupError] = useState<string | null>(null);

  const isAdmin = user?.role === "admin";

  // Guard: only admins may access this page (same pattern as ProtectedRoute).
  useEffect(() => {
    if (!authLoading && !isAdmin) {
      router.replace("/unauthorized");
    }
  }, [authLoading, isAdmin, router]);

  // Fetch settings only for admins. The backend GET /tenant/settings is not
  // admin-only, so non-admins must never issue this request before redirect.
  useEffect(() => {
    if (authLoading || !isAdmin) return;

    let cancelled = false;

    async function loadSettings() {
      try {
        const data = await fetchSettings();
        if (!cancelled) {
          setSettings(data);
          setMarkupInput(data.consumer_markup_pct);
        }
      } catch (error) {
        if (cancelled) return;
        toaster.create({
          title: "Error",
          description:
            error instanceof Error ? error.message : "Could not load settings.",
          type: "error",
        });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadSettings();
    return () => {
      cancelled = true;
    };
  }, [authLoading, isAdmin]);

  /** Validate the markup input value. */
  function validateMarkup(value: string): string | null {
    if (value === "") return "Required";

    const num = Number(value);
    if (isNaN(num)) return "Must be a number";
    if (num < MARKUP_MIN)
      return `Minimum is ${MARKUP_MIN}`;
    if (num > MARKUP_MAX)
      return `Maximum is ${MARKUP_MAX}`;

    return null;
  }

  /** Handle input change — validate in real time. */
  function handleMarkupChange(e: React.ChangeEvent<HTMLInputElement>) {
    const value = e.target.value;
    setMarkupInput(value);
    setMarkupError(validateMarkup(value));
  }

  /** Save the markup to the backend. */
  async function handleSave() {
    if (!settings) return;

    const validationError = validateMarkup(markupInput);
    if (validationError) {
      setMarkupError(validationError);
      return;
    }

    setSaving(true);
    try {
      const payload: SettingsUpdatePayload = {
        ...settings,
        consumer_markup_pct: markupInput,
      };

      const updated = await updateSettings(payload);
      setSettings(updated);
      toaster.create({
        title: "Settings saved",
        description: `Consumer markup set to ${markupInput}%.`,
        type: "success",
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Could not save settings.";

      // Surface backend 403 / 422 clearly.
      if (message.includes("403") || message.includes("Forbidden")) {
        toaster.create({
          title: "Access denied",
          description:
            "Only administrators can change tenant settings.",
          type: "error",
        });
      } else if (message.includes("422")) {
        toaster.create({
          title: "Invalid value",
          description: message,
          type: "error",
        });
      } else {
        toaster.create({
          title: "Error",
          description: message,
          type: "error",
        });
      }
    } finally {
      setSaving(false);
    }
  }

  if (authLoading || !isAdmin || loading) {
    return (
      <Flex align="center" justify="center" py={16}>
        <Spinner size="xl" />
      </Flex>
    );
  }

  return (
    <Container py={10} maxW="container.sm">
      <VStack align="start" gap={6}>
        <Heading size="3xl">Tenant Settings</Heading>

        <Card.Root width="full">
          <Card.Body width="full">
            <VStack align="start" gap={4} width="full">
            <Field.Root width="full" invalid={!!markupError}>
              <Field.Label>Consumer Markup</Field.Label>
              <Flex align="end" gap={2}>
                <Input
                  type="number"
                  value={markupInput}
                  onChange={handleMarkupChange}
                  min={MARKUP_MIN}
                  max={MARKUP_MAX}
                  width="160px"
                />
                <Text fontSize="lg" fontWeight="bold">
                  %
                </Text>
              </Flex>
              <Field.HelperText>
                Markup percentage applied to revendedores prices to compute
                consumer final prices. Range: {MARKUP_MIN}–{MARKUP_MAX}%.
              </Field.HelperText>
              <Field.ErrorText>{markupError}</Field.ErrorText>
            </Field.Root>

            <Button
              colorPalette="brand"
              size="sm"
              onClick={handleSave}
              loading={saving}
              disabled={!!markupError}
            >
              Save
            </Button>
            </VStack>
          </Card.Body>
        </Card.Root>

        {/* Current value display */}
        {settings && (
          <Text fontSize="sm" color="fg.muted">
            Current value:{" "}
            <Text as="span" fontWeight="bold">
              {settings.consumer_markup_pct}%
            </Text>
          </Text>
        )}
      </VStack>
    </Container>
  );
}
