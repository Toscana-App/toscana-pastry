"use client";

import { useEffect, useState } from "react";
import {
  Button,
  Field,
  Fieldset,
  Flex,
  Input,
  Switch,
  Text,
} from "@chakra-ui/react";
import { ApiError } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";
import { toaster } from "@/lib/toaster";
import { orderWindowService } from "../service";

export function OrderWindowSection() {
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [open, setOpen] = useState(true);
  const [reopensAt, setReopensAt] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    let active = true;
    orderWindowService
      .get()
      .then((w) => {
        if (!active) return;
        setOpen(w.open);
        setReopensAt(w.reopens_at ? w.reopens_at.slice(0, 16) : "");
        setMessage(w.message);
      })
      .catch((e: unknown) => {
        if (!active) return;
        if (e instanceof ApiError && e.status === 404) {
          setNotFound(true);
        } else {
          setLoadError("No se pudo cargar la ventana de pedidos.");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleSave() {
    setLocalError("");
    if (!open && !reopensAt) {
      setLocalError("Al cerrar la ventana, fijá la fecha y hora de reapertura.");
      return;
    }
    setSaving(true);
    try {
      const updated = await orderWindowService.update({
        open,
        reopens_at: open ? null : reopensAt,
        message,
      });
      if (updated.open) setReopensAt("");
      else if (updated.reopens_at)
        setReopensAt(updated.reopens_at.slice(0, 16));
      trackEvent("order_window_changed", { open: updated.open });
      toaster.create({ title: "Corte de pedidos guardado", type: "success" });
    } catch (e: unknown) {
      toaster.create({
        title: "Error al guardar",
        description: e instanceof Error ? e.message : "Intentá de nuevo.",
        type: "error",
      });
    } finally {
      setSaving(false);
    }
  }

  const disabled = notFound || loadError !== "";

  return (
    <Fieldset.Root
      borderWidth="1px"
      borderColor="gray.200"
      rounded="md"
      p={5}
      disabled={disabled}
    >
      <Fieldset.Legend fontWeight="600">Corte de pedidos</Fieldset.Legend>
      <Flex direction="column" gap={5} mt={4}>
        {notFound ? (
          <Text fontSize="sm" color="fg.muted">
            El backend de esta versión no expone la ventana de pedidos
            (GET /tenant/order-window → 404). Actualizá la API para habilitar
            el corte de pedidos.
          </Text>
        ) : loadError ? (
          <Text fontSize="sm" color="red.500">
            {loadError}
          </Text>
        ) : (
          <>
            <Flex align="center" gap={3}>
              <Switch.Root
                checked={open}
                onCheckedChange={(details) => {
                  setOpen(details.checked);
                  setLocalError("");
                }}
              >
                <Switch.HiddenInput />
                <Switch.Control>
                  <Switch.Thumb />
                </Switch.Control>
              </Switch.Root>
              <Text>
                {open
                  ? "Ventana de pedidos abierta"
                  : "Ventana de pedidos cerrada"}
              </Text>
            </Flex>

            <Field.Root invalid={!!localError} disabled={open}>
              <Field.Label>Reabre el (obligatorio al cerrar)</Field.Label>
              <Input
                type="datetime-local"
                value={reopensAt}
                onChange={(e) => {
                  setReopensAt(e.target.value);
                  setLocalError("");
                }}
              />
              <Field.ErrorText>{localError}</Field.ErrorText>
            </Field.Root>

            <Field.Root>
              <Field.Label>
                Mensaje para el portal (máx. 200 caracteres){" "}
                <Text as="span" color="fg.muted" fontWeight="400">
                  — {message.length}/200
                </Text>
              </Field.Label>
              <Input
                value={message}
                maxLength={200}
                placeholder="Ej.: Cerrado por mantenimiento, reabrimos mañana 20 h"
                onChange={(e) => setMessage(e.target.value)}
              />
            </Field.Root>

            <Flex gap={3} flexWrap="wrap">
              <Button
                type="button"
                colorPalette="brand"
                loading={saving}
                onClick={handleSave}
              >
                Guardar corte de pedidos
              </Button>
            </Flex>
          </>
        )}
      </Flex>
    </Fieldset.Root>
  );
}
