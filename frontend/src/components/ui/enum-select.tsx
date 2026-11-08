import { chakra } from "@chakra-ui/react";

const StyledSelect = chakra("select", {
  base: {
    width: "100%",
    height: "2.5rem",
    paddingInline: "0.75rem",
    borderRadius: "md",
    borderWidth: "1px",
    borderColor: "border",
    background: "transparent",
    fontSize: "sm",
    outline: "none",
    _focusVisible: {
      borderColor: "brand.solid",
      boxShadow: "0 0 0 1px var(--chakra-colors-brand-600)",
    },
    _disabled: { opacity: 0.5, cursor: "not-allowed" },
  },
});

interface EnumSelectProps
  extends Omit<React.ComponentPropsWithoutRef<"select">, "children"> {
  options: readonly string[];
  placeholder?: string;
}

export function EnumSelect({ options, placeholder, ...rest }: EnumSelectProps) {
  return (
    <StyledSelect {...rest}>
      {placeholder ? <option value="">{placeholder}</option> : null}
      {options.map((option) => (
        <option key={option} value={option}>
          {option}
        </option>
      ))}
    </StyledSelect>
  );
}
