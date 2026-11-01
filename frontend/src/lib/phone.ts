/** E.164 phone normalization with +54 default (RF-P11-04 / C7).

The backend normalizes to E.164 (+54 default); the frontend validates the
same contract before sending to surface inline errors.
*/

const MIN_DIGITS = 10;
const MAX_DIGITS = 15;

/**
 * Converts free-form input to E.164 assuming +54 by default:
 * - "+54 9 11 5555-5555" → "+5491155555555"
 * - "011 5555-5555"      → "+541155555555" (local 00/0 prefixes are dropped)
 * - "9115555555"         → "+549115555555"
 * Returns null when there are not enough digits to be valid.
 */
export function normalizePhoneE164(raw: string): string | null {
  let digits = raw.replace(/[^\d]/g, "");
  if (digits.length === 0) return null;

  // Explicit international prefix 0054.
  if (digits.startsWith("0054")) digits = digits.slice(4);

  // Argentine national prefix "0" (011/0221/0341...) → drop it.
  if (digits.startsWith("0") && digits.length > MIN_DIGITS) {
    digits = digits.slice(1);
  }

  // If it already starts with 54 (country AR), the user typed +54/0054.
  if (!digits.startsWith("54")) digits = `54${digits}`;

  if (digits.length < MIN_DIGITS || digits.length > MAX_DIGITS) return null;
  return `+${digits}`;
}
