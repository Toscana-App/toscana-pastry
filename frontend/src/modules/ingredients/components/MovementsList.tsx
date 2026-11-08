import { Flex, Text } from "@chakra-ui/react";
import { formatDateTime, formatSignedQty } from "@/lib/format";
import type { StockMovement } from "../types";

/**
 * Etiquetas legibles de los motivos del contrato. El alta y la importación
 * registran el stock inicial como `compra` con ref "inicial", así que también
 * se muestra como "Compra · inicial".
 */
const REASON_LABEL: Record<string, string> = {
  compra: "Compra",
  merma: "Merma",
  ajuste: "Ajuste",
};

/** El detalle trae como máximo los últimos 50 movimientos (límite del backend). */
const DETAIL_LIMIT = 50;

/**
 * Historial de movimientos de stock (Fase 4, WU6).
 *
 * Cada fila: delta con signo (verde entra, rojo sale), motivo, referencia
 * opcional y fecha local. Vienen del más reciente al más antiguo.
 */
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
              >
                {formatSignedQty(movement.qty_delta)}
              </Text>
              <Flex direction="column" flex="1 1 8rem">
                <Text fontWeight="500">
                  {REASON_LABEL[movement.reason] ?? movement.reason}
                </Text>
                {movement.ref ? (
                  <Text fontSize="sm" color="fg.muted">
                    Ref: {movement.ref}
                  </Text>
                ) : null}
              </Flex>
              <Text fontSize="sm" color="fg.muted">
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
