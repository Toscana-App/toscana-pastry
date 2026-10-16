import { chakra } from "@chakra-ui/react";

/**
 * Select nativo estilizado (Fase 4).
 *
 * Los enums del contrato son cortos y cerrados (unidad kg|g|L|ml|unidad,
 * motivo de stock, dificultad): un `<select>` nativo es más simple, accesible y
 * predecible que un listbox custom, y se integra directo con react-hook-form
 * (los props de `register` se esparcen sobre el propio elemento, sin
 * sincronizar estado a mano).
 */
const StyledSelect = chakra("select", {
  base: {
    width: "100%",
    height: "2.5rem",
    paddingInline: "0.75rem",
    borderRadius: "md",
    borderWidth: "1px",
    borderColor: "gray.200",
    background: "transparent",
    fontSize: "sm",
    outline: "none",
    _focusVisible: {
      borderColor: "brand.600",
      boxShadow: "0 0 0 1px var(--chakra-colors-brand-600)",
    },
    _disabled: { opacity: 0.5, cursor: "not-allowed" },
  },
});

interface EnumSelectProps
  extends Omit<React.ComponentPropsWithoutRef<"select">, "children"> {
  /** Opciones (una por valor del enum del contrato). */
  options: readonly string[];
  /** Etiqueta vacía inicial; sin ella queda seleccionada la primera opción. */
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
