// Minimal service worker for PWA "Add to Home Screen". Network-only (no cache).
self.addEventListener('install', function (e) {
  self.skipWaiting();
});
self.addEventListener('activate', function (e) {
  e.waitUntil(self.clients.claim());
});
self.addEventListener('fetch', function () {
  // Pass through to network only
});
