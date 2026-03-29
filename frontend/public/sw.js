// SipSense Service Worker — cache-first for static assets, network-first for API
const CACHE_NAME = 'sipsense-__BUILD_ID__'
const STATIC_ASSETS = ['/', '/manifest.json']

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  )
  self.skipWaiting()
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', (e) => {
  const { request } = e
  const url = new URL(request.url)

  // Skip non-GET and API/auth requests
  if (request.method !== 'GET' || url.pathname.startsWith('/api')) return

  // For navigation requests (HTML pages), try network first, fall back to cache
  if (request.mode === 'navigate') {
    e.respondWith(
      fetch(request)
        .then((res) => {
          const clone = res.clone()
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone))
          return res
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match('/')))
    )
    return
  }

  // For static assets (JS, CSS, images), cache-first
  e.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request).then((res) => {
          // Only cache same-origin successful responses
          if (res.ok && url.origin === self.location.origin) {
            const clone = res.clone()
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone))
          }
          return res
        })
    )
  )
})

// ── Push Notifications ────────────────────────────────────────────────────

self.addEventListener('push', (e) => {
  if (!e.data) return

  let payload
  try {
    payload = e.data.json()
  } catch {
    payload = { title: 'SipSense', body: e.data.text(), url: '/alerts' }
  }

  const { title, body, url, icon, tag } = payload

  e.waitUntil(
    self.registration.showNotification(title || 'SipSense', {
      body: body || '',
      icon: icon || '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      tag: tag || 'sipsense',
      data: { url: url || '/alerts' },
      vibrate: [100, 50, 200],
    })
  )
})

self.addEventListener('notificationclick', (e) => {
  e.notification.close()

  const targetUrl = e.notification.data?.url || '/alerts'

  e.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clients) => {
        // If app is already open, focus it and navigate
        for (const client of clients) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            client.focus()
            client.postMessage({ type: 'NAVIGATE', url: targetUrl })
            return
          }
        }
        // Otherwise open a new window
        if (self.clients.openWindow) {
          return self.clients.openWindow(targetUrl)
        }
      })
  )
})