"use client";

import { Button, Dialog, Text } from "@chakra-ui/react";

interface DeleteProductDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  productName: string;
  deleting: boolean;
  onConfirm: () => void;
}

/**
 * Confirmación de borrado de producto (Fase 5, RF-P4-08).
 *
 * El borrado NO se bloquea aunque haya pedidos históricos: es un soft delete
 * (el producto sale del catálogo, los pedidos quedan intactos). El diálogo
 * advierte justamente eso antes de confirmar.
 */
export function DeleteProductDialog({
  open,
  onOpenChange,
  productName,
  deleting,
  onConfirm,
}: DeleteProductDialogProps) {
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
            <Dialog.Title>¿Eliminar «{productName}»?</Dialog.Title>
          </Dialog.Header>
          <Dialog.Body>
            <Text>
              El producto deja de aparecer en el catálogo y no se puede usar en
              pedidos nuevos. Los pedidos históricos no se modifican.
            </Text>
            <Text mt={2} color="fg.muted" fontSize="sm">
              Esta acción no se puede deshacer.
            </Text>
          </Dialog.Body>
          <Dialog.Footer>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button colorPalette="red" onClick={onConfirm} loading={deleting}>
              Eliminar
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
