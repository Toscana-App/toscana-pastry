export function setCookie(name: string, value: string, days: number) {
  const date = new Date();
  date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
  const expires = "expires=" + date.toUTCString();
  document.cookie = `${name}=${value}; ${expires}; path=/`;
}

export function getCookie(name: string) {
  const namePrefix = name + "=";
  const decodedCookie = decodecookie.decode(document.cookie);
  // wait, I'll use a simpler implementation
  const ca = document.cookie.split(';');
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i].trim();
    if (c.indexOf(namePrefix) === 0) {
      return c.substring(namePrefix.length, c.length);
    }
  }
  return undefined;
}

export function removeCookie(name: string) {
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/`;
}
