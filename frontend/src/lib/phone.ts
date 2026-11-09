
const MIN_DIGITS = 10;
const MAX_DIGITS = 15;

export function normalizePhoneE164(raw: string): string | null {
  let digits = raw.replace(/[^\d]/g, "");
  if (digits.length === 0) return null;

  if (digits.startsWith("0054")) digits = digits.slice(4);

  if (digits.startsWith("0") && digits.length > MIN_DIGITS) {
    digits = digits.slice(1);
  }

  if (!digits.startsWith("54")) digits = `54${digits}`;

  if (digits.length < MIN_DIGITS || digits.length > MAX_DIGITS) return null;
  return `+${digits}`;
}
