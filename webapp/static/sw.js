/* Homelib service worker.
 *
 * Its one job is to make the catalogue readable with no network -- standing in
 * a bookshop wondering whether you already own the thing in your hand.
 *
 * Note this only ever runs on https (or localhost): browsers refuse to register
 * a worker on a plain-http origin.  Over http the application still works, and
 * still keeps an offline copy of the data in localStorage; what is missing then
 * is the shell, so the page itself will not open without the server.
 */

const VERSION = 'homelib-v2';

// Where the application is mounted, worked out from this file's own address:
// '/' on port 8888, '/homelib/' when nginx serves it beside the thermometer.
// Everything below is written against BASE, so one worker covers both, and the
// browser gives each address its own registration.
const BASE = self.location.pathname.replace(/sw\.js$/, '');
const SHELL = [
  BASE,
  BASE + 'static/app.css',
  BASE + 'static/app.js',
  BASE + 'static/i18n.js',
  BASE + 'static/icon.svg',
  BASE + 'manifest.webmanifest'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(VERSION)
      .then(cache => cache.addAll(SHELL))
      .then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        // Only our own: cache storage is shared with everything else served
        // from this host, and the thermometer's pages are next door.
        keys.filter(k => k.startsWith('homelib-') && k !== VERSION)
            .map(k => caches.delete(k))))
      .then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;   // writes have no offline meaning
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // The catalogue: fresh when we can reach the Pi, the last copy when we
  // cannot.  Never the other way round -- a stale shelf location is the one
  // thing this application must not show.
  if (url.pathname === BASE + 'api/catalog') {
    event.respondWith(
      fetch(request)
        .then(response => {
          const copy = response.clone();
          caches.open(VERSION).then(cache => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request)
          .then(hit => hit || new Response('{"error":"offline"}', {
            status: 503, headers: { 'Content-Type': 'application/json' } }))));
    return;
  }

  // Anything else live goes to the network only.
  if (url.pathname.startsWith(BASE + 'api/')) return;

  // The shell: answer from the cache at once, and refresh it in the background.
  // Plain cache-first would pin whatever was cached the day it was installed,
  // so a redeploy would never reach a phone that had already installed the app;
  // this way the next opening picks up the new version by itself.
  const cacheable = url.pathname === BASE
                    || url.pathname.startsWith(BASE + 'static/')
                    || url.pathname === BASE + 'manifest.webmanifest';
  event.respondWith(
    caches.match(request).then(hit => {
      const network = fetch(request).then(response => {
        if (response.ok && cacheable) {
          const copy = response.clone();
          caches.open(VERSION).then(cache => cache.put(request, copy));
        }
        return response;
      }).catch(() => hit || caches.match(BASE));
      return hit || network;
    }));
});
