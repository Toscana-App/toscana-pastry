"use client";

/** GA4 consent banner (F4 — RF-P11-15).

Shown only until the user decides (accept/decline). The decision is
persisted in localStorage; without a decision nothing is loaded.
*/

import { Alert, Button, Flex, Text } from "@chakra-ui/react";
import { useSyncExternalStore, useState } from "react";
import { setConsent } from "@/lib/analytics";

// useSyncExternalStore: snapshot = "has a decision been made?" with no effect.
function subscribe(onChange: () => void): () => void {
  // localStorage emits no events; the decision happens through the banner's
  // own buttons (which re-render via local state). Intentional no-op.
  void onChange;
  return () => {};
}

function getClientSnapshot(): boolean {
  return window.localStorage.getItem("toscana_ga4_consent") !== null;
}

function getServerSnapshot(): boolean {
  return true; // SSR does not show the banner (avoids hydration mismatch)
}

export function ConsentBanner() {
  const decided = useSyncExternalStore(
    subscribe,
    getClientSnapshot,
    getServerSnapshot
  );
  const [dismissed, setDismissed] = useState(false);

  if (decided || dismissed) return null;

  return (
    <Alert.Root
      status="info"
      bg="bg.muted"
      borderBottomWidth="1px"
      borderColor="border.muted"
      mx={0}
      mb={2}
      borderRadius="none"
    >
      <Alert.Indicator />
      <Alert.Content>
        <Flex
          direction={{ base: "column", md: "row" }}
          align={{ base: "flex-start", md: "center" }}
          justify="space-between"
          gap={3}
        >
          <Text fontSize="sm">
            Usamos analytics solo si nos das permiso. Tu pedido nunca
            depende de esto.
          </Text>
          <Flex gap={2}>
            <Button
              size="xs"
              variant="outline"
              onClick={() => {
                setConsent(false);
                setDismissed(true);
              }}
            >
              Preferir sin analytics
            </Button>
            <Button
              size="xs"
              colorPalette="brand"
              onClick={() => {
                setConsent(true);
                setDismissed(true);
              }}
            >
              Aceptar
            </Button>
          </Flex>
        </Flex>
      </Alert.Content>
    </Alert.Root>
  );
}
