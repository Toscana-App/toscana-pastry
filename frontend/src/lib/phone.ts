/** Normalización de teléfono E.164 con +54 default (RF-P11-04 / C7).

El backend normaliza a E.164 (+54 default); el frontend valida el mismo
contrato antes de enviar para dar errores inline.
*/

const MIN_DIGITS = 10;
const MAX_DIGITS = 15;

/**
 * Convierte input libre a E.164 asumiendo +54 por defecto:
 * - "+54 9 11 5555-5555" → "+5491155555555"
 * - "011 5555-5555"      → "+541155555555" (prefijo 00/0 local se descarta)
 * - "9115555555"         → "+549115555555"
 * Devuelve null si no hay suficientes dígitos para ser válido.
 */
export function normalizePhoneE164(raw: string): string | null {
  let digits = raw.replace(/[^\d]/g, "");
  if (digits.length === 0) return null;

  // Prefijo internacional explícito 0054.
  if (digits.startsWith("0054")) digits = digits.slice(4);

  // Prefijo nacional "0" argentino (011/0221/0341...) → lo descarta.
  if (digits.startsWith("0") && digits.length > MIN_DIGITS) {
    digits = digits.slice(1);
  }

  // Si ya empieza con 54 (país AR), el usuario escribió +54/0054.
  if (!digits.startsWith("54")) digits = `54${digits}`;

  if (digits.length < MIN_DIGITS || digits.length > MAX_DIGITS) return null;
  return `+${digits}`;
}
