// Central place for all API calls.
// Uses the /api prefix which Vite proxies to http://localhost:8000 in dev.

const BASE = '/api'

// ── Auth token helpers ───────────────────────────────────────────────────

export function getToken() {
  try { return localStorage.getItem('sipsense_token') } catch { return null }
}

export function setAuth(token, username, refreshToken) {
  try {
    localStorage.setItem('sipsense_token', token)
    localStorage.setItem('sipsense_user', username)
    if (refreshToken) localStorage.setItem('sipsense_refresh', refreshToken)
  } catch { /* private browsing — auth won't persist across reloads */ }
}

export function clearAuth() {
  try {
    localStorage.removeItem('sipsense_token')
    localStorage.removeItem('sipsense_user')
    localStorage.removeItem('sipsense_refresh')
  } catch { /* private browsing */ }
}

function getRefreshToken() {
  try { return localStorage.getItem('sipsense_refresh') } catch { return null }
}

export function getUsername() {
  try { return localStorage.getItem('sipsense_user') } catch { return null }
}

export function isLoggedIn() {
  return !!getToken()
}

// ── Core request with auth, timeout, retry, and deduplication ───────────

const REQUEST_TIMEOUT_MS = 30000

// Deduplication: concurrent GET requests to the same path share a single in-flight promise
const _inflight = new Map()

async function request(path, options = {}, _retryCount = 0) {
  const method = (options.method || 'GET').toUpperCase()
  // Skip dedup when caller provides their own AbortSignal — the deduped
  // promise could be tied to a *different* caller's abort lifecycle,
  // causing "signal is aborted without reason" errors when the original
  // caller unmounts but the new caller's signal is still active.
  const dedupeKey = method === 'GET' && !options.signal ? path : null
  if (dedupeKey && _inflight.has(dedupeKey)) {
    return _inflight.get(dedupeKey)
  }
  const promise = _doRequest(path, options, _retryCount)
  if (dedupeKey) {
    _inflight.set(dedupeKey, promise)
    // Use .then(fn, fn) instead of .finally() to avoid creating an unhandled
    // rejection on the cleanup chain when the original promise rejects.
    promise.then(
      () => _inflight.delete(dedupeKey),
      () => _inflight.delete(dedupeKey),
    )
  }
  return promise
}

async function _doRequest(path, options = {}, _retryCount = 0) {
  const token = getToken()
  const isFormData = options.body instanceof FormData
  const headers = { ...(isFormData ? {} : { 'Content-Type': 'application/json' }), ...options.headers }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Set up timeout via AbortController (unless caller provided their own signal)
  let timeoutId
  const fetchOpts = { ...options, headers }
  if (!fetchOpts.signal) {
    const controller = new AbortController()
    fetchOpts.signal = controller.signal
    timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  }

  let res
  try {
    res = await fetch(`${BASE}${path}`, fetchOpts)
  } catch (err) {
    if (timeoutId) clearTimeout(timeoutId)
    // Retry once on network error (not on user-initiated abort)
    if (_retryCount === 0 && err.name !== 'AbortError') {
      return request(path, options, 1)
    }
    if (err.name === 'AbortError') {
      if (!options.signal) {
        throw new Error('Request timed out. Please try again.')
      }
      // Caller-provided signal was aborted (component unmount, navigation, etc.)
      // Re-throw as AbortError so callers can detect it, but with a clean message
      const abort = new DOMException('Request cancelled', 'AbortError')
      throw abort
    }
    throw err
  }
  if (timeoutId) clearTimeout(timeoutId)

  // If token expired / invalid, try silent refresh before forcing logout
  if (res.status === 401) {
    const refreshToken = getRefreshToken()
    if (refreshToken && _retryCount === 0) {
      try {
        const refreshRes = await fetch(`${BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
        if (refreshRes.ok) {
          const data = await refreshRes.json()
          setAuth(data.access_token, data.username, data.refresh_token)
          // Retry the original request with the new token
          return request(path, options, 1)
        }
      } catch { /* refresh failed, fall through to logout */ }
    }
    clearAuth()
    window.dispatchEvent(new CustomEvent('auth:expired'))
    throw new Error('Session expired. Please log in again.')
  }

  // Retry once on server errors (5xx)
  if (res.status >= 500 && _retryCount === 0) {
    return request(path, options, 1)
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Request failed (${res.status})`)
  }
  // 204 No Content — return null
  if (res.status === 204) return null
  return res.json()
}

/**
 * Helper for components to create an AbortController-linked fetch.
 * Usage in useEffect:
 *   const controller = new AbortController()
 *   api.listWhiskeys(params, { signal: controller.signal })
 *   return () => controller.abort()
 */

export const api = {
  // ── Auth ─────────────────────────────────────────────────────────────────
  register: (username, email, password) =>
    request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, email, password }),
    }),
  login: (username, password) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  getMe: () => request('/auth/me'),

  // ── Whiskeys ─────────────────────────────────────────────────────────────
  listWhiskeys: (params = {}, opts = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null)
    ).toString()
    return request(`/whiskeys/${qs ? '?' + qs : ''}`, opts)
  },
  getWhiskeyCount: () => request('/whiskeys/count'),
  getWhiskey: (id) => request(`/whiskeys/${id}`),
  getSimilar: (id, top_n = 5) => request(`/whiskeys/${id}/similar?top_n=${top_n}`),
  getBlurb: (id) => request(`/whiskeys/${id}/blurb`),
  getRatings: (id, { sort_by = 'recent', skip = 0, limit = 50 } = {}) =>
    request(`/whiskeys/${id}/ratings?sort_by=${sort_by}&skip=${skip}&limit=${limit}`),
  getReviewSummary: (id) => request(`/whiskeys/${id}/review-summary`),
  getFlavorTags: () => request(`/whiskeys/flavor-tags`),
  rateWhiskey: (id, body) =>
    request(`/whiskeys/${id}/rate`, { method: 'POST', body: JSON.stringify(body) }),
  getValuePicks: (params = {}, opts = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null)
    ).toString()
    return request(`/whiskeys/value-picks${qs ? '?' + qs : ''}`, opts)
  },

  // ── Recommendations (now GET, uses token for user identity) ──────────────
  getRecommendations: (top_n = 5) =>
    request(`/recommendations/?top_n=${top_n}`),

  // ── Taste quiz ───────────────────────────────────────────────────────────
  submitQuiz: (answers, top_n = 6) =>
    request(`/quiz/?top_n=${top_n}`, {
      method: 'POST',
      body: JSON.stringify(answers),
    }),

  // ── Favorites (now uses token, no user_id in URL) ────────────────────────
  addFavorite: (whiskey_id) =>
    request(`/favorites/${whiskey_id}`, { method: 'POST' }),
  removeFavorite: (whiskey_id) =>
    request(`/favorites/${whiskey_id}`, { method: 'DELETE' }),
  getFavorites: () => request('/favorites/me'),
  getFavoriteIds: () => request('/favorites/me/ids'),

  // ── My Palate (now uses token) ───────────────────────────────────────────
  getPalate: () => request('/palate/me'),

  // ── Compare ──────────────────────────────────────────────────────────────
  compareBottles: (id_a, id_b) => request(`/compare/?id_a=${id_a}&id_b=${id_b}`),

  // ── Stores ───────────────────────────────────────────────────────────────
  getNearbyStores: (lat, lng, radius = 5000) =>
    request(`/stores/nearby?lat=${lat}&lng=${lng}&radius=${radius}`),
  getStoresForWhiskey: (whiskeyId, lat, lng, radius = 5000) =>
    request(`/stores/whiskey/${whiskeyId}?lat=${lat}&lng=${lng}&radius=${radius}`),
  reportAvailability: (storeOsmId, body) =>
    request(`/stores/${storeOsmId}/report`, { method: 'POST', body: JSON.stringify(body) }),
  getStoreAvailability: (storeOsmId, whiskeyId = null) => {
    const qs = whiskeyId ? `?whiskey_id=${whiskeyId}` : ''
    return request(`/stores/${storeOsmId}/availability${qs}`)
  },

  // ── Trending ────────────────────────────────────────────────────────────
  getTrending: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null)
    ).toString()
    return request(`/trending/${qs ? '?' + qs : ''}`)
  },
  getNewArrivals: (limit = 12) => request(`/trending/new-arrivals?limit=${limit}`),

  // ── Pairings ───────────────────────────────────────────────────────────
  getPairings: (whiskeyId) => request(`/pairings/${whiskeyId}`),

  // ── Collection (My Shelf) ──────────────────────────────────────────────
  getCollection: (status = null) => {
    const qs = status ? `?status=${status}` : ''
    return request(`/collection/${qs}`)
  },
  getCollectionStats: () => request('/collection/stats'),
  addToCollection: (body) =>
    request('/collection/', { method: 'POST', body: JSON.stringify(body) }),
  updateCollectionItem: (itemId, body) =>
    request(`/collection/${itemId}`, { method: 'PATCH', body: JSON.stringify(body) }),
  removeFromCollection: (itemId) =>
    request(`/collection/${itemId}`, { method: 'DELETE' }),

  // ── Personality ───────────────────────────────────────────────────────────
  getPersonality: () => request('/personality/me'),

  // ── Daily Discovery ──────────────────────────────────────────────────────
  getDailyDiscovery: () => request('/daily/'),

  // ── Feed ───────────────────────────────────────────────────────────────
  getFeed: (params = {}, opts = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null)
    ).toString()
    return request(`/feed/${qs ? '?' + qs : ''}`, opts)
  },

  // ── Social (Toasts & Profiles) ────────────────────────────────────────
  addToast: (ratingId) =>
    request(`/ratings/${ratingId}/toast`, { method: 'POST' }),
  removeToast: (ratingId) =>
    request(`/ratings/${ratingId}/toast`, { method: 'DELETE' }),
  markHelpful: (ratingId) =>
    request(`/ratings/${ratingId}/helpful`, { method: 'POST' }),
  unmarkHelpful: (ratingId) =>
    request(`/ratings/${ratingId}/helpful`, { method: 'DELETE' }),
  getUserProfile: (username) =>
    request(`/users/${username}/profile`),
  getUserRatings: (username, { sort_by = 'recent', skip = 0, limit = 10 } = {}) =>
    request(`/users/${username}/ratings?sort_by=${sort_by}&skip=${skip}&limit=${limit}`),
  followUser: (username) =>
    request(`/users/${username}/follow`, { method: 'POST' }),
  unfollowUser: (username) =>
    request(`/users/${username}/follow`, { method: 'DELETE' }),
  getFollowers: (username) =>
    request(`/users/${username}/followers`),
  getFollowing: (username) =>
    request(`/users/${username}/following`),
  searchUsers: (q) =>
    request(`/users/search?q=${encodeURIComponent(q)}`),

  // ── Check-in Comments ──────────────────────────────────────────────────
  addCheckInComment: (ratingId, text) =>
    request(`/ratings/${ratingId}/comment`, { method: 'POST', body: JSON.stringify({ text }) }),
  getCheckInComments: (ratingId, { skip = 0, limit = 50 } = {}) =>
    request(`/ratings/${ratingId}/comments?skip=${skip}&limit=${limit}`),
  deleteCheckInComment: (commentId) =>
    request(`/ratings/comments/${commentId}`, { method: 'DELETE' }),

  // ── AI Social ─────────────────────────────────────────────────────────
  getPalateMatch: (username) => request(`/palate/match/${username}`),
  getSuggestedUsers: (limit = 5) => request(`/users/suggested?limit=${limit}`),

  // ── AI Features ─────────────────────────────────────────────────────────
  getAiTastingNotes: (whiskeyId) => request(`/whiskeys/${whiskeyId}/ai-tasting-notes`),
  getAiPalateSummary: () => request('/palate/me/ai-summary'),
  getExplainedRecommendations: (top_n = 6) =>
    request(`/recommendations/explained?top_n=${top_n}`),

  // ── Barcode Scanner ─────────────────────────────────────────────────────
  lookupBarcode: (upc) => request(`/whiskeys/barcode/${encodeURIComponent(upc)}`),

  // ── Price Context ──────────────────────────────────────────────────────
  getPriceContext: (whiskeyId) => request(`/whiskeys/${whiskeyId}/price-context`),

  // ── Buy Links ──────────────────────────────────────────────────────────
  getBuyLinks: (whiskeyId) => request(`/whiskeys/${whiskeyId}/buy-links`),

  // ── Journal / Image Upload ─────────────────────────────────────────────
  uploadRatingImage: (ratingId, file) => {
    const formData = new FormData()
    formData.append('file', file)
    const token = getToken()
    const headers = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch(`${BASE}/ratings/${ratingId}/image`, {
      method: 'POST',
      headers,
      body: formData,
    }).then(res => {
      if (!res.ok) throw new Error('Image upload failed')
      return res.json()
    })
  },
  getJournal: () => request('/journal/me'),

  // ── Share Card ─────────────────────────────────────────────────────────
  getShareCardUrl: (ratingId) => `${BASE}/share/rating/${ratingId}`,
  getWhiskeyShareCardUrl: (whiskeyId) => `${BASE}/share/whiskey/${whiskeyId}`,

  // ── Label scan ─────────────────────────────────────────────────────────
  scanLabel: (imageFile) => {
    const form = new FormData()
    form.append('file', imageFile)
    return request('/scan/label', { method: 'POST', body: form })
  },

  // ── Watchlist & Alerts ─────────────────────────────────────────────────
  watchWhiskey: (id) => request(`/watchlist/${id}`, { method: 'POST' }),
  unwatchWhiskey: (id) => request(`/watchlist/${id}`, { method: 'DELETE' }),
  getWatchStatus: (id) => request(`/watchlist/status/${id}`),
  getWatchlist: () => request('/watchlist/'),
  getAlerts: ({ skip = 0, limit = 50 } = {}) => request(`/watchlist/alerts?skip=${skip}&limit=${limit}`),
  getUnreadAlertCount: () => request('/watchlist/alerts/unread-count'),
  markAlertRead: (alertId) => request(`/watchlist/alerts/${alertId}/read`, { method: 'POST' }),
  markAllAlertsRead: () => request('/watchlist/alerts/read-all', { method: 'POST' }),

  // ── Discover ──────────────────────────────────────────────────────────
  getGraphData: () => request('/discover/graph'),

  // ── Journeys ───────────────────────────────────────────────────────────
  listJourneys: () => request('/journeys/'),
  getJourney: (slug) => request(`/journeys/${slug}`),
  startJourney: (slug) => request(`/journeys/${slug}/start`, { method: 'POST' }),
  completeStep: (slug, stepNumber) =>
    request(`/journeys/${slug}/steps/${stepNumber}/complete`, { method: 'POST' }),
  getMyJourneys: () => request('/journeys/me'),

  // ── Videos ──────────────────────────────────────────────────────────────
  getVideoFeed: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null)
    ).toString()
    return request(`/videos/feed${qs ? '?' + qs : ''}`)
  },
  getVideo: (id) => request(`/videos/${id}`),
  deleteVideo: (id) => request(`/videos/${id}`, { method: 'DELETE' }),
  uploadVideo: (formData) => {
    const token = getToken()
    const headers = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch(`${BASE}/videos/upload`, {
      method: 'POST',
      headers,
      body: formData,
    }).then(res => {
      if (!res.ok) throw new Error('Video upload failed')
      return res.json()
    })
  },
  toastVideo: (id) => request(`/videos/${id}/toast`, { method: 'POST' }),
  untoastVideo: (id) => request(`/videos/${id}/toast`, { method: 'DELETE' }),
  addVideoComment: (id, text) =>
    request(`/videos/${id}/comment`, { method: 'POST', body: JSON.stringify({ text }) }),
  getVideoComments: (id, { skip = 0, limit = 50 } = {}) =>
    request(`/videos/${id}/comments?skip=${skip}&limit=${limit}`),
  deleteVideoComment: (commentId) =>
    request(`/videos/comments/${commentId}`, { method: 'DELETE' }),
  recordVideoView: (id) => request(`/videos/${id}/view`, { method: 'POST' }),
  getUserVideos: (username, params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null)
    ).toString()
    return request(`/videos/user/${username}${qs ? '?' + qs : ''}`)
  },
  getWhiskeyVideos: (whiskeyId, params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null)
    ).toString()
    return request(`/videos/whiskey/${whiskeyId}${qs ? '?' + qs : ''}`)
  },

  // ── Affiliate ──────────────────────────────────────────────────────────
  recordAffiliateClick: (body) =>
    request('/affiliate/click', { method: 'POST', body: JSON.stringify(body) }),

  // ── Sponsored ────────────────────────────────────────────────────────
  trackSponsoredImpression: (placementId) =>
    request(`/sponsored/${placementId}/impression`, { method: 'POST' }),
  trackSponsoredClick: (placementId) =>
    request(`/sponsored/${placementId}/click`, { method: 'POST' }),

  // ── Subscription ──────────────────────────────────────────────────────
  getSubscriptionStatus: () => request('/subscription/status'),
  getFeatureComparison: () => request('/subscription/features'),
  activatePremium: () => request('/subscription/activate', { method: 'POST' }),
  cancelSubscription: () => request('/subscription/cancel', { method: 'POST' }),

  // ── Analytics (Admin) ──────────────────────────────────────────────────
  getAnalyticsOverview: () => request('/analytics/overview'),
  getAnalyticsFunnel: () => request('/analytics/funnel'),
  getAnalyticsTopWhiskeys: (days = 30, limit = 20) =>
    request(`/analytics/top-whiskeys?days=${days}&limit=${limit}`),
  getAnalyticsFeatureAdoption: (days = 30) =>
    request(`/analytics/feature-adoption?days=${days}`),
  getAnalyticsPerformance: (days = 7) =>
    request(`/analytics/performance?days=${days}`),

  // ── Match Scores ────────────────────────────────────────────────────────
  getMatchScores: (whiskeyIds) =>
    request('/match-scores/batch', {
      method: 'POST',
      body: JSON.stringify(whiskeyIds),
    }),

  // ── Top Lists ──────────────────────────────────────────────────────────
  getTopLists: () => request('/toplists/'),
  getTopList: (slug, limit = 20) => request(`/toplists/${slug}?limit=${limit}`),

  // ── Chat — returns raw Response for SSE stream ───────────────────────────
  chatStream: (messages, session_id = null, user_location = null, signal = null) => {
    const headers = { 'Content-Type': 'application/json' }
    const token = getToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    const body = { messages, session_id }
    if (user_location) {
      body.user_location = user_location
    }
    const opts = { method: 'POST', headers, body: JSON.stringify(body) }
    if (signal) opts.signal = signal
    return fetch(`${BASE}/chat/`, opts)
  },
}
