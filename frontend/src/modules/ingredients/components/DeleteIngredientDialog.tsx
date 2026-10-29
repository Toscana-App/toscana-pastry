"use client";

import { Button, Dialog, Text } from "@chakra-ui/react";
import type { DeleteImpact } from "../types";

interface DeleteIngredientDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ingredientName: string;
  /**
   * Impacto devuelto por el backend (409): el ingrediente está en uso.
   * Cuando viene, la eliminación no está permitida y solo se puede cerrar.
   */
  impact: DeleteImpact | null;
  deleting: boolean;
  onConfirm: () => void;
}

/**
 * Confirmación de borrado (Fase 4, WU6, UC-05).
 *
 * Dos estados:
 * - Sin impacto: confirmación normal (borrado irreversible).
 * - Con impacto (409): el ingrediente es parte de N recetas; el sistema no
 *   permite borrarlo. El diálogo lo explica y no ofrece confirmar.
 */
export function DeleteIngredientDialog({
  open,
  onOpenChange,
  ingredientName,
  impact,
  deleting,
  onConfirm,
}: DeleteIngredientDialogProps) {
  const blocked = impact !== null;

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(e) => onOpenChange(e.open)}
      role="alertdialog"
    >
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content>
          <Dialog.Header>
            <Dialog.Title>
              {blocked ? "No se puede eliminar" : `¿Eliminar «${ingredientName}»?`}
            </Dialog.Title>
          </Dialog.Header>
          <Dialog.Body>
            {blocked ? (
              <Text>
                Este ingrediente es parte de {impact?.impacted_recipes}{" "}
                {impact?.impacted_recipes === 1 ? "receta" : "recetas"}. Para
                eliminarlo, primero quitálo de{" "}
                {impact?.impacted_recipes === 1 ? "esa receta" : "esas recetas"}.
              </Text>
            ) : (
              <Text>
                Se va a eliminar el ingrediente y su historial de movimientos.
                Esta acción no se puede deshacer.
              </Text>
            )}
          </Dialog.Body>
          <Dialog.Footer>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              {blocked ? "Cerrar" : "Cancelar"}
            </Button>
            {!blocked ? (
              <Button colorPalette="red" onClick={onConfirm} loading={deleting}>
                Eliminar
              </Button>
            ) : null}
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
