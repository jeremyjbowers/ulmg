// ABOUTME: Same-origin service worker for the site. Browsers will not register one from the CDN.
// ABOUTME: Network first. A cached copy is only a fallback, and only after a response that succeeded.

const CACHE_NAME = 'ulmg-static-v1';
const URLS_TO_CACHE = [
  '/',
  '/favicon-32x32.png',
  '/favicon-16x16.png',
  '/apple-touch-icon.png'
];

function remember(cache, url) {
  return fetch(url).then((response) => {
    if (response.ok) return cache.put(url, response);
  }).catch(() => {});
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => Promise.all(URLS_TO_CACHE.map((url) => remember(cache, url))))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((key) => {
      if (key !== CACHE_NAME) return caches.delete(key);
    })))
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).then((response) => {
      const path = new URL(event.request.url).pathname;
      if (response.ok && URLS_TO_CACHE.indexOf(path) !== -1) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
      }
      return response;
    }).catch(() => caches.match(event.request))
  );
});
