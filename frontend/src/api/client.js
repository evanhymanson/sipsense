// Central place for all API calls.
// Uses the /api prefix which Vite proxies to http://localhost:8000 in dev.

const BASE = '/api'

// ── Auth token helpers ───────────────────────────────────────────────────

export function getToken() {
  return localStorage.getItem('sipsense_token')
}

export function setAuth(token, username) {
  localStorage.setItem('sipsense_token', token)
  localStorage.setItem('sipsense_user', username)
}

export function clearAuth() {
  localStorage.removeItem('sipsense_token')
  localStorage.removeItem('sipsense_user')
}

export function getUsername() {
  return localStorage.getItem('sipsense_user')
}

export function isLoggedIn() {
  return !!getToken()
}

// ── Core request with auth ───────────────────────────────────────────────

async function request(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  // If token expired / invalid, clear auth so UI can redirect to login
  if (res.status === 401) {
    clearAuth()
    throw new Error('Session expired. Please log in again.')
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  // 204 No Content — return null
  if (res.status === 204) return null
  return res.json()
}

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
  listWhiskeys: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null)
    ).toString()
    return request(`/whiskeys/${qs ? '?' + qs : ''}`)
  },
  getWhiskey: (id) => request(`/whiskeys/${id}`),
  getSimilar: (id, top_n = 5) => request(`/whiskeys/${id}/similar?top_n=${top_n}`),
  getBlurb: (id) => request(`/whiskeys/${id}/blurb`),
  getRatings: (id) => request(`/whiskeys/${id}/ratings`),
  rateWhiskey: (id, body) =>
    request(`/whiskeys/${id}/rate`, { method: 'POST', body: JSON.stringify(body) }),
  getValuePicks: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null)
    ).toString()
    return request(`/whiskeys/value-picks${qs ? '?' + qs : ''}`)
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

  // ── Learn ────────────────────────────────────────────────────────────────
  listCategories: () => request('/learn/categories'),
  getCategory: (slug) => request(`/learn/categories/${slug}`),
  listDistilleries: () => request('/learn/distilleries'),
  getDistillery: (slug) => request(`/learn/distilleries/${slug}`),
  getGlossary: () => request('/learn/glossary'),

  // ── Flight Builder ───────────────────────────────────────────────────────
  listFlightThemes: () => request('/flights/'),
  getFlight: (theme, max_price = 0, count = 4) =>
    request(`/flights/${theme}?max_price=${max_price}&count=${count}`),

  // ── Gift Finder ──────────────────────────────────────────────────────────
  findGift: (body) => request('/gift/', { method: 'POST', body: JSON.stringify(body) }),

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

  // ── Blind Tasting ────────────────────────────────────────────────────────
  getChallenge: (difficulty = 'easy') => request(`/blind-tasting/challenge?difficulty=${difficulty}`),
  submitGuess: (body) =>
    request('/blind-tasting/guess', { method: 'POST', body: JSON.stringify(body) }),

  // ── Daily Discovery ──────────────────────────────────────────────────────
  getDailyDiscovery: () => request('/daily/'),

  // ── Feed ───────────────────────────────────────────────────────────────
  getFeed: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null)
    ).toString()
    return request(`/feed/${qs ? '?' + qs : ''}`)
  },

  // ── Social (Toasts & Profiles) ────────────────────────────────────────
  addToast: (ratingId) =>
    request(`/ratings/${ratingId}/toast`, { method: 'POST' }),
  removeToast: (ratingId) =>
    request(`/ratings/${ratingId}/toast`, { method: 'DELETE' }),
  getUserProfile: (username) =>
    request(`/users/${username}/profile`),

  // ── AI Features ─────────────────────────────────────────────────────────
  getAiTastingNotes: (whiskeyId) => request(`/whiskeys/${whiskeyId}/ai-tasting-notes`),
  getAiPalateSummary: () => request('/palate/me/ai-summary'),
  getExplainedRecommendations: (top_n = 6) =>
    request(`/recommendations/explained?top_n=${top_n}`),

  // ── Chat — returns raw Response for SSE stream ───────────────────────────
  chatStream: (messages, session_id = null, user_location = null) => {
    const headers = { 'Content-Type': 'application/json' }
    const token = getToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    const body = { messages, session_id }
    if (user_location) {
      body.user_location = user_location
    }
    return fetch(`${BASE}/chat/`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    })
  },
}
