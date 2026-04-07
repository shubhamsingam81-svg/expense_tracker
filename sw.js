const CACHE_NAME = 'expense-tracker-v4';
const ASSETS_TO_CACHE = [
    './index.html',
    './style.css',
    './app.js',
    './chart.js',
    './manifest.json'
];

const ASSET_PATHS = [
    './',
    ...ASSETS_TO_CACHE,
    './icons/icon-192.png',
    './icons/icon-512.png'
];

self.addEventListener('install', event => {
    console.log('[SW] Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('[SW] Caching assets');
            return cache.addAll(ASSET_PATHS).catch(err => {
                console.warn('[SW] Some assets failed to cache:', err);
                return cache.addAll(ASSETS_TO_CACHE);
            });
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') return;
    
    event.respondWith(
        caches.match(event.request).then(cached => {
            if (cached) return cached;
            
            return fetch(event.request).then(response => {
                if (response && response.status === 200 && response.type === 'basic') {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            }).catch(() => {
                if (cached) return cached;
                return new Response('Offline - Resource not cached', { status: 503 });
            });
        })
    );
});
