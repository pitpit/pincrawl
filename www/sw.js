// Service Worker for handling push notifications

// Install event - activate immediately
self.addEventListener('install', (event) => {
    self.skipWaiting(); // Activate new SW immediately
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
    event.waitUntil(self.clients.claim());
});
