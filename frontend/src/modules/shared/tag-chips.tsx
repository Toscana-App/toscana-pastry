import { Badge, Flex, Text } from "@chakra-ui/react";

const MAX_VISIBLE_TAGS = 2;

interface TagChipsProps {
  tags: string[];
}

export function TagChips({ tags }: TagChipsProps) {
  if (tags.length === 0) return null;
  return (
    <Flex gap={1.5} wrap="wrap">
      {tags.slice(0, MAX_VISIBLE_TAGS).map((tag) => (
        <Badge key={tag} size="xs" variant="outline" colorPalette="gray">
          {tag}
        </Badge>
      ))}
      {tags.length > MAX_VISIBLE_TAGS ? (
        <Text fontSize="xs" color="fg.muted">
          +{tags.length - MAX_VISIBLE_TAGS}
        </Text>
      ) : null}
    </Flex>
  );
}
