import { Flex, Text } from "@chakra-ui/react";
import { formatDateTime, formatSignedQty } from "@/lib/format";
import type { StockMovement } from "../types";

const REASON_LABEL: Record<string, string> = {
  compra: "Compra",
  merma: "Merma",
  ajuste: "Ajuste",
};

const DETAIL_LIMIT = 50;

export function MovementsList({ movements }: { movements: StockMovement[] }) {
  if (movements.length === 0) {
    return (
      <Text color="fg.muted">
        Todavía no hay movimientos registrados para este ingrediente.
      </Text>
    );
  }

  return (
    <Flex direction="column" gap={3}>
      <Flex
        direction="column"
        borderWidth="1px"
        borderColor="border"
        rounded="md"
        divideY="1px"
      >
        {movements.map((movement) => {
          const isIncoming = Number(movement.qty_delta) > 0;
          return (
            <Flex
              key={movement.id}
              justify="space-between"
              align="center"
              gap={3}
              px={4}
              py={3}
              flexWrap="wrap"
            >
              <Text
                fontWeight="600"
                color={isIncoming ? "green.fg" : "red.fg"}
                minW="4rem"
                fontVariantNumeric="tabular-nums"
              >
                {formatSignedQty(movement.qty_delta)}
              </Text>
              <Flex direction="column" flex="1 1 8rem" minW={0}>
                <Text fontWeight="500">
                  {REASON_LABEL[movement.reason] ?? movement.reason}
                </Text>
                {movement.ref ? (
                  <Text fontSize="sm" color="fg.muted" overflowWrap="anywhere">
                    Ref: {movement.ref}
                  </Text>
                ) : null}
              </Flex>
              <Text fontSize="sm" color="fg.muted" fontVariantNumeric="tabular-nums">
                {formatDateTime(movement.created_at)}
              </Text>
            </Flex>
          );
        })}
      </Flex>

      {movements.length >= DETAIL_LIMIT ? (
        <Text fontSize="sm" color="fg.muted">
          Se muestran los últimos {DETAIL_LIMIT} movimientos.
        </Text>
      ) : null}
    </Flex>
  );
}
