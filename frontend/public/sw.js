const SHELL_CACHE = "toscana-pastry-shell-v1";
const RUNTIME_CACHE = "toscana-pastry-runtime-v1";
const SHELL_URLS = ["/"];
const IMAGE_SUFFIX_RE = /\.(?:png|jpe?g|webp|gif|svg|ico|avif)(?:\?.*)?$/i;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== SHELL_CACHE && key !== RUNTIME_CACHE)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const isStaticAsset = url.pathname.startsWith("/_next/static/");
  const isImage = IMAGE_SUFFIX_RE.test(url.pathname);
  const isNavigation = request.mode === "navigate";

  if (isStaticAsset || isImage) {
    event.respondWith(
      caches.open(RUNTIME_CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        if (cached) return cached;
        const response = await fetch(request);
        if (response.ok || response.status === 404) {
          cache.put(request, response.clone());
        }
        return response;
      })
    );
    return;
  }

  if (isNavigation) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const snapshot = new Request(request.url, { method: "GET" });
            caches
              .open(SHELL_CACHE)
              .then((cache) => cache.put(snapshot, response.clone()))
              .catch(() => undefined);
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(request);
          if (cached) return cached;
          const home = await caches.match(new Request("/"));
          if (home) return home;
          return Response.error();
        })
    );
  }
});
