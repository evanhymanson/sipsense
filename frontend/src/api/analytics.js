/**
 * Lightweight frontend analytics — sends page views and timed events to the backend.
 * Uses navigator.sendBeacon for reliability (fires even on page unload).
 */

const TRACK_ENDPOINT = '/api/analytics/track'

// Debounce page view tracking to avoid double-fires from React StrictMode
let lastTrackedPath = null
let lastTrackedTime = 0

function _getAuthHeader() {
  try {
    const token = localStorage.getItem('sipsense_token')
    return token ? `Bearer ${token}` : null
  } catch {
    return null
  }
}

export function trackPageView(path) {
  const now = Date.now()
  if (path === lastTrackedPath && now - lastTrackedTime < 2000) return
  lastTrackedPath = path
  lastTrackedTime = now

  const payload = {
    event: 'page_view',
    path,
    referrer: document.referrer || null,
    timestamp: new Date().toISOString(),
  }

  // sendBeacon is fire-and-forget, works on page unload
  if (navigator.sendBeacon) {
    navigator.sendBeacon(TRACK_ENDPOINT, JSON.stringify(payload))
  } else {
    fetch(TRACK_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {})
  }
}

export function trackEvent(name, data = {}) {
  const payload = {
    event: name,
    data,
    path: window.location.pathname,
    timestamp: new Date().toISOString(),
  }
  if (navigator.sendBeacon) {
    navigator.sendBeacon(TRACK_ENDPOINT, JSON.stringify(payload))
  } else {
    fetch(TRACK_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {})
  }
}

// Time-on-page tracking
let pageEnteredAt = null

export function startPageTimer() {
  pageEnteredAt = Date.now()
}

export function endPageTimer(path) {
  if (pageEnteredAt) {
    const duration = Math.round((Date.now() - pageEnteredAt) / 1000)
    if (duration > 1 && duration < 3600) {
      trackEvent('time_on_page', { path, seconds: duration })
    }
    pageEnteredAt = null
  }
}
