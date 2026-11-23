"use client";

import { useState } from "react";
import { Badge, Button, CloseButton, Flex, Input, Text } from "@chakra-ui/react";

const MAX_TAGS = 10;
const MAX_TAG_LENGTH = 30;

interface TagsInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  invalid?: boolean;
  errorText?: string;
}

export function TagsInput({
  value,
  onChange,
  invalid,
  errorText,
}: TagsInputProps) {
  const [draft, setDraft] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const full = value.length >= MAX_TAGS;

  function addTag() {
    const tag = draft.trim();
    if (!tag) return;
    if (tag.length > MAX_TAG_LENGTH) {
      setLocalError(`Máximo ${MAX_TAG_LENGTH} caracteres por tag`);
      return;
    }
    if (value.some((item) => item.toLowerCase() === tag.toLowerCase())) {
      setLocalError("Ese tag ya está cargado");
      return;
    }
    if (full) {
      setLocalError(`Máximo ${MAX_TAGS} tags`);
      return;
    }
    onChange([...value, tag]);
    setDraft("");
    setLocalError(null);
  }

  function removeTag(index: number) {
    onChange(value.filter((_, position) => position !== index));
    setLocalError(null);
  }

  return (
    <Flex direction="column" gap={2}>
      <Flex gap={2} align="flex-start">
        <Input
          autoComplete="off"
          value={draft}
          placeholder={full ? "Máximo alcanzado" : "Ej: sin gluten"}
          disabled={full}
          aria-invalid={invalid || Boolean(localError)}
          onChange={(event) => {
            setDraft(event.target.value);
            setLocalError(null);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addTag();
            }
            if (event.key === "Backspace" && draft === "" && value.length > 0) {
              removeTag(value.length - 1);
            }
          }}
        />
        <Button
          type="button"
          variant="outline"
          onClick={addTag}
          disabled={full || draft.trim().length === 0}
        >
          Agregar
        </Button>
      </Flex>

      {value.length > 0 ? (
        <Flex gap={2} wrap="wrap">
          {value.map((tag, index) => (
            <Badge key={`${tag}-${index}`} variant="subtle" size="md" gap={1}>
              {tag}
              <CloseButton
                size="2xs"
                aria-label={`Quitar tag ${tag}`}
                onClick={() => removeTag(index)}
              />
            </Badge>
          ))}
        </Flex>
      ) : (
        <Text fontSize="sm" color="fg.muted">
          Sin tags. Sirven para filtrar el catálogo (ej: sin gluten, vegano).
        </Text>
      )}

      {invalid && errorText ? (
        <Text fontSize="sm" color="fg.error">
          {errorText}
        </Text>
      ) : null}
      {localError ? (
        <Text fontSize="sm" color="fg.error">
          {localError}
        </Text>
      ) : null}
    </Flex>
  );
}
