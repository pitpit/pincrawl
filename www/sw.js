// Service Worker for handling push notifications

const CACHE_NAME = 'pincrawl-v1';

// Cache important assets for offline functionality
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll([
                '/static/favicon.ico',
                '/static/img/logo-64x64.png'
            ]).catch(err => console.log('Cache failed, continuing anyway:', err));
        }).then(() => self.skipWaiting())
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
self.addEventListener('activate', (event) => {
    event.waitUntil(
        Promise.all([
            self.clients.claim(),
            // Clean up old caches
            caches.keys().then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== CACHE_NAME) {
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
        ])
    );
});

// Handle fetch events to keep SW active
self.addEventListener('fetch', (event) => {
    // Only cache GET requests for assets
    if (event.request.method !== 'GET') return;

    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});
