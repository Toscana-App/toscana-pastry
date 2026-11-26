"use client";

import { Alert, Box, Button, Dialog, Flex, Input, Text } from "@chakra-ui/react";
import { useState } from "react";
import { toaster } from "@/lib/toaster";
import { uploadOrderReceipt } from "@/services/ordersService";
import type { OrderDetail } from "@/types/orders";

const ACCEPTED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"];
const ACCEPT = ".pdf,.jpg,.jpeg,.png";

function isAcceptedName(name: string): boolean {
  const lower = name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function ReceiptUploadDialog({
  orderId,
  open,
  onOpenChange,
  onUploaded,
}: {
  orderId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploaded: (order: OrderDetail) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);

  const pick = (candidate: File | null | undefined) => {
    if (!candidate) return;
    if (!isAcceptedName(candidate.name)) {
      setFile(null);
      setInvalid(true);
      return;
    }
    setInvalid(false);
    setFile(candidate);
  };

  const submit = async () => {
    if (!file || uploading) return;
    setUploading(true);
    try {
      const updated = await uploadOrderReceipt(orderId, file);
      setFile(null);
      onOpenChange(false);
      onUploaded(updated);
    } catch (error) {
      toaster.create({
        title: "No se pudo subir el comprobante",
        description: error instanceof Error ? error.message : "Intentá de nuevo",
        type: "error",
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(e) => onOpenChange(e.open)}
      role="alertdialog"
    >
      <Dialog.Backdrop />
      <Dialog.Positioner>
        <Dialog.Content overscrollBehavior="contain" maxW="sm">
          <Dialog.Header>
            <Dialog.Title>Subir comprobante</Dialog.Title>
          </Dialog.Header>
          <Dialog.Body>
            <Text fontSize="sm" color="fg.muted">
              PDF, JPG o PNG (máx. 5 MB).
            </Text>
            <Box
              mt={3}
              borderWidth="2px"
              borderStyle="dashed"
              borderColor={dragOver ? "brand" : "border.muted"}
              rounded="md"
              p={6}
              textAlign="center"
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                pick(e.dataTransfer.files?.[0]);
              }}
            >
              <Text fontSize="sm">Arrastrá el archivo acá o elegilo</Text>
              <Flex justify="center" mt={3}>
                <Button as="label" size="sm" variant="outline" cursor="pointer">
                  Elegir archivo
                  <Input
                    type="file"
                    accept={ACCEPT}
                    srOnly
                    onChange={(e) => pick(e.target.files?.[0])}
                  />
                </Button>
              </Flex>
              {file && (
                <Text fontSize="sm" mt={3} overflowWrap="anywhere">
                  {file.name}
                </Text>
              )}
              {invalid && (
                <Alert.Root status="error" mt={3} size="sm" textAlign="left">
                  <Alert.Indicator />
                  <Alert.Content>
                    <Alert.Description>
                      Formato no aceptado. Usá PDF, JPG o PNG.
                    </Alert.Description>
                  </Alert.Content>
                </Alert.Root>
              )}
            </Box>
          </Dialog.Body>
          <Dialog.Footer>
            <Button variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button
              colorPalette="brand"
              onClick={() => void submit()}
              loading={uploading}
              disabled={!file}
            >
              Subir
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  );
}
