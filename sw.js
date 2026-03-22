const CDN_CACHE = 'kimchi-cdn-v1';

// Install - nothing to pre-cache (local assets always fetched from network)
self.addEventListener('install', event => {
  self.skipWaiting();
});

// Activate - clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(key => key !== CDN_CACHE).map(key => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch - local assets: always network (no cache)
//         CDN resources: cache-first (they never change)
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = event.request.url;

  // CDN resources: cache-first (stable, versioned URLs)
  if (url.includes('cdnjs.cloudflare.com') || url.includes('cdn.jsdelivr.net')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          const clone = response.clone();
          caches.open(CDN_CACHE).then(cache => cache.put(event.request, clone));
          return response;
        });
      })
    );
    return;
  }

  // Local assets: always go to network, never cache
  // (ensures code changes reflect immediately on all devices)
  event.respondWith(fetch(event.request));
});
