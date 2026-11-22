"use client";

import { Flex, Text } from "@chakra-ui/react";
import NextLink from "next/link";

export function TabLink({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  return (
    <NextLink href={href} aria-current={active ? "page" : undefined}>
      <Flex
        px={4}
        py={3}
        minH="44px"
        align="center"
        whiteSpace="nowrap"
        borderBottomWidth="2px"
        borderColor={active ? "brand.solid" : "transparent"}
        _hover={{ bg: "bg.muted" }}
        transition="background-color 150ms ease-out"
        _motionReduce={{ transition: "none" }}
      >
        <Text
          fontSize="sm"
          fontWeight={active ? "bold" : "normal"}
          color={active ? "brand.fg" : "fg.muted"}
        >
          {label}
        </Text>
      </Flex>
    </NextLink>
  );
}
