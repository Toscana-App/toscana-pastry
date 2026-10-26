/** GA4 consent-gated (F4 — RF-P11-15).

El script de GA4 se carga SOLO tras consentimiento explícito del
usuario (persistido en localStorage). `trackEvent` es no-op hasta que
el consentimiento está otorgado. El ID de medición se toma de
NEXT_PUBLIC_GA4_MEASUREMENT_ID; sin él, todo queda desactivado.
*/

const CONSENT_KEY = "toscana_ga4_consent";
const MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA4_MEASUREMENT_ID;

let gtagLoaded = false;

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

/** Devuelve si el consentimiento fue otorgado (solo en cliente). */
export function hasConsent(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(CONSENT_KEY) === "granted";
}

/**
 * Otorga o retira el consentimiento. Al otorgar, inyecta el script de
 * GA4 una sola vez. Sin ID de medición configurado, no hace nada.
 */
export function setConsent(granted: boolean): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CONSENT_KEY, granted ? "granted" : "denied");
  if (!granted) return;
  if (!MEASUREMENT_ID) return;
  if (gtagLoaded) return;
  gtagLoaded = true;

  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag ?? function gtag(...args: unknown[]) {
    window.dataLayer?.push(args);
  };
  window.gtag("js", new Date());
  window.gtag("config", MEASUREMENT_ID, { send_to: MEASUREMENT_ID });

  const script = document.createElement("link");
  script.rel = "preload";
  script.as = "script";
  script.href = `https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}`;
  document.head.appendChild(script);

  const tag = document.createElement("script");
  tag.src = `https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}`;
  tag.async = true;
  document.head.appendChild(tag);
}

/**
 * Registra un evento de GA4. No-op si no hay consentimiento otorgado
 * o si no hay medición configurada.
 */
export function trackEvent(name: string, params: Record<string, unknown> = {}): void {
  if (typeof window === "undefined") return;
  if (!hasConsent()) return;
  if (!MEASUREMENT_ID || !gtagLoaded) return;
  window.gtag?.("event", name, params);
}
