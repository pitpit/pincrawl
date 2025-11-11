// Service Worker for handling push notifications and PWA caching

const CACHE_NAME = 'pincrawl-v1';
const urlsToCache = [
    '/',
    '/static/css/main.css',
    '/static/favicon.ico',
    '/static/manifest.json',
    '/static/img/logo-32x32.png',
    '/static/img/logo-64x64.png',
];

// Install event - cache resources
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                return cache.addAll(urlsToCache);
            })
    );
});

// Fetch event - serve from cache or network
self.addEventListener('fetch', (event) => {
    event.respondWith(
        caches.match(event.request)
            .then((response) => {
                // Return cached version or fetch from network
                return response || fetch(event.request);
            }
        )
    );
});

// Handles incoming push notifications and displays them to the user
self.addEventListener('push', function(event) {
    if (!event.data) return;

    let data;
    try {
        data = event.data.json();
    } catch (e) {
        console.error('Failed to parse push data:', e);
        return;
    }

    const options = {
        body: data.body,
        icon: '/static/favicon.ico',
        badge: '/static/img/logo-64x64.png',
        data: { url: data.url },
        requireInteraction: true,
        tag: `pincrawl-notification-${Date.now()}`,

        vibrate: [200, 100, 200], // Vibration pattern
        silent: false, // Don't make it silent
        renotify: true, // Show even if same tag exists
        timestamp: Date.now()
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// Handles user interactions with notifications (clicks on notification or action buttons)
self.addEventListener('notificationclick', function(event) {
    event.notification.close();

    if (event.action === 'dismiss') return;

    const urlToOpen = event.notification.data?.url || '/';

    event.waitUntil(
        clients.matchAll({ type: 'window' }).then(clientList => {
            const existingClient = clientList.find(client => client.url === urlToOpen);
            return existingClient?.focus() || clients.openWindow(urlToOpen);
        })
    );
});

// Activates the service worker and takes control of all clients
self.addEventListener('activate', function(event) {
    event.waitUntil(
        Promise.all([
            self.clients.claim(),
            // Clean up old caches
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        if (cacheName !== CACHE_NAME) {
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
        ])
    );
});
