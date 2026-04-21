/* Service Worker for RS Dashboard PWA
 *
 * Cache strategy (fixes stale-bundle bug 2026-04-18):
 *   - Navigation / HTML:            NETWORK-FIRST (fresh shell every load;
 *                                   cache only as offline fallback).
 *   - Hashed assets (/assets/*):    cache-first (Vite puts a content hash in
 *                                   every filename, so a new bundle has a new
 *                                   URL — old cached versions are harmless).
 *   - API / data.json / tab-data:   NETWORK-FIRST (dashboard data must be
 *                                   current; cache only if offline).
 *   - Everything else (icons, etc.) stale-while-revalidate.
 *
 * Cache busting:
 *   `CACHE_NAME` is replaced at build time with a unique BUILD_ID by the
 *   `sw-cache-bust` plugin in vite.config.js. If the token is NOT replaced
 *   (dev mode or a hand-run of the file), we fall back to a timestamped name
 *   so every load wipes the previous cache — prevents sticky dev state.
 *
 *   Every `activate` event purges *all* other `rs-dashboard-*` caches so old
 *   deploys are reliably evicted.
 */

const BUILD_ID_TOKEN = '__BUILD_ID__';
const CACHE_PREFIX = 'rs-dashboard-';
const CACHE_NAME =
  BUILD_ID_TOKEN === ('__' + 'BUILD_ID__')
    ? `${CACHE_PREFIX}dev-${Date.now()}`
    : `${CACHE_PREFIX}${BUILD_ID_TOKEN}`;

/* Intentionally tiny precache — the shell is fetched network-first below. */
const PRECACHE_URLS = ['/favicon.svg', '/manifest.json'];

/* ---------- install ---------- */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .catch(() => {})
  );
  self.skipWaiting();
});

/* ---------- activate: purge EVERY old rs-dashboard-* cache ---------- */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

/* ---------- fetch helpers ---------- */
const putInCache = async (request, response) => {
  if (!response || !response.ok) return;
  try {
    const clone = response.clone();
    const cache = await caches.open(CACHE_NAME);
    await cache.put(request, clone);
  } catch {
    /* Some requests (e.g. chrome-extension://) can't be cached; ignore. */
  }
};

const networkFirst = async (request) => {
  try {
    const response = await fetch(request);
    putInCache(request, response);
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    /* For navigation, fall back to a cached shell if any. */
    if (request.mode === 'navigate') {
      const shell = await caches.match('/');
      if (shell) return shell;
    }
    throw new Error('offline and no cache');
  }
};

const cacheFirst = async (request) => {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  putInCache(request, response);
  return response;
};

const staleWhileRevalidate = async (request) => {
  const cached = await caches.match(request);
  const fetchPromise = fetch(request)
    .then((response) => {
      putInCache(request, response);
      return response;
    })
    .catch(() => cached);
  return cached || fetchPromise;
};

/* ---------- fetch routing ---------- */
self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  /* Navigation (top-level HTML) — always go to network first. */
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }

  /* Live data + API — always try network first. */
  if (
    url.pathname.startsWith('/api/') ||
    url.pathname === '/data.json' ||
    url.pathname.startsWith('/tab-data/')
  ) {
    event.respondWith(networkFirst(request));
    return;
  }

  /* Hashed Vite assets — immutable, safe to cache-first. */
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  /* Everything else — stale-while-revalidate. */
  event.respondWith(staleWhileRevalidate(request));
});

/* ---------- messages (used by page to force activation) ---------- */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
