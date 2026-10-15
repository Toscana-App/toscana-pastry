const isBrowser = typeof document !== "undefined";

export function setCookie(name: string, value: string, days: number) {
  if (!isBrowser) return;
  const date = new Date();
  date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
  const expires = "expires=" + date.toUTCString();
  document.cookie = `${name}=${value}; ${expires}; path=/; SameSite=Lax`;
}

export function getCookie(name: string): string | undefined {
  if (!isBrowser) return undefined;
  const namePrefix = name + "=";
  const ca = document.cookie.split(";");
  for (let i = 0; i < ca.length; i++) {
    const c = ca[i].trim();
    if (c.indexOf(namePrefix) === 0) {
      return c.substring(namePrefix.length, c.length);
    }
  }
  return undefined;
}

export function removeCookie(name: string) {
  if (!isBrowser) return;
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; SameSite=Lax`;
}
