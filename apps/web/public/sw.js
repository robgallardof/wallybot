// WallyBot service worker: makes the app installable and keeps the shell usable on flaky
// networks. Financial data is never cached — /api and /health always go to the network.
const CACHE = "wallybot-shell-v1";
const SHELL = ["/icons/icon-192.png", "/icons/icon-512.png", "/icons/icon.svg", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/health/")) return;

  // Hashed build assets and icons never change in place: cache first.
  if (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(CACHE).then((cache) => cache.put(request, copy));
            }
            return response;
          }),
      ),
    );
    return;
  }

  // Pages carry a per-request CSP nonce, so they are not cached; offline gets a minimal notice.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(
        () =>
          new Response(
            '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WallyBot</title><body style="font-family:system-ui;background:#111113;color:#f5f5f7;display:grid;place-items:center;min-height:100vh;margin:0;text-align:center;padding:16px"><div><h1>Sin conexión</h1><p>WallyBot necesita conexión para mostrar datos actualizados.</p></div>',
            { headers: { "Content-Type": "text/html; charset=utf-8" } },
          ),
      ),
    );
  }
});
