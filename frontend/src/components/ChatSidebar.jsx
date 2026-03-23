import { useState, useRef, useEffect, useCallback, memo, lazy, Suspense } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { getCategoryEmoji } from '../constants'
import './ChatSidebar.css'

const CHAT_STORAGE_KEY = 'sipsense_chat_messages'
const MAX_CHAT_MESSAGES = 200

const STARTER_PROMPTS = [
  "Good beginner bourbon under $40?",
  "I love Lagavulin \u2014 what else should I try?",
  "Compare Maker's Mark vs Buffalo Trace",
  "Build me a scotch regions flight",
  "Find liquor stores in Chicago",
  "Best value picks right now?",
]

// Lazy-load Leaflet map to avoid bundle bloat when chat doesn't need it
const SidebarMap = lazy(() => import('./SidebarMap'))

// ── Compact whiskey card for the sidebar ─────────────────────────────────────

const SidebarWhiskeyCard = memo(function SidebarWhiskeyCard({ whiskey }) {
  const navigate = useNavigate()
  const stars = Math.round(whiskey.rating_avg || 0)
  const emoji = getCategoryEmoji(whiskey.category)

  return (
    <div
      className="sb-whiskey-card"
      onClick={() => navigate(`/whiskey/${whiskey.id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && navigate(`/whiskey/${whiskey.id}`)}
    >
      <div className="sb-card-top">
        <span className="sb-card-emoji">{emoji}</span>
        <div className="sb-card-info">
          <div className="sb-card-name">{whiskey.name}</div>
          <div className="sb-card-distillery">{whiskey.distillery}</div>
        </div>
      </div>
      <div className="sb-card-meta">
        {whiskey.category && <span className="sb-badge">{whiskey.category}</span>}
        {whiskey.price_usd && <span className={`sb-badge${whiskey.price_is_estimated ? ' sb-badge--estimated' : ''}`}>{whiskey.price_is_estimated ? '~' : ''}${Number(whiskey.price_usd).toFixed(2)}{whiskey.price_is_estimated ? ' Est.' : ''}</span>}
        {whiskey.rating_avg > 0 && (
          <span className="sb-badge sb-badge--rating">
            {'\u2605'.repeat(stars)}{'\u2606'.repeat(5 - stars)} {whiskey.rating_avg.toFixed(1)}
          </span>
        )}
      </div>
    </div>
  )
})

// ── Comparison table (generative UI) ─────────────────────────────────────────

const SidebarComparison = memo(function SidebarComparison({ whiskeys, rows }) {
  const navigate = useNavigate()
  if (!whiskeys || whiskeys.length < 2) return null
  const [w1, w2] = whiskeys

  return (
    <div className="sb-comparison">
      <div className="sb-comp-header">
        <div className="sb-comp-col sb-comp-col--name" onClick={() => navigate(`/whiskey/${w1.id}`)}>
          {w1.name}
        </div>
        <div className="sb-comp-vs">vs</div>
        <div className="sb-comp-col sb-comp-col--name" onClick={() => navigate(`/whiskey/${w2.id}`)}>
          {w2.name}
        </div>
      </div>
      {(rows || []).slice(0, 7).map(([label, v1, v2], i) => (
        <div key={i} className="sb-comp-row">
          <span className="sb-comp-label">{label}</span>
          <span className="sb-comp-val">{String(v1)}</span>
          <span className="sb-comp-val">{String(v2)}</span>
        </div>
      ))}
    </div>
  )
})

// ── Flight visualization (generative UI) ─────────────────────────────────────

const SidebarFlight = memo(function SidebarFlight({ story, whiskeys }) {
  const navigate = useNavigate()
  if (!whiskeys || whiskeys.length === 0) return null

  return (
    <div className="sb-flight">
      {story && <p className="sb-flight-story">{story}</p>}
      <div className="sb-flight-track">
        {whiskeys.map((w, i) => (
          <div key={w.id} className="sb-flight-stop">
            <div className="sb-flight-num">{i + 1}</div>
            <div
              className="sb-flight-bottle"
              onClick={() => navigate(`/whiskey/${w.id}`)}
              role="button"
              tabIndex={0}
              onKeyDown={e => e.key === 'Enter' && navigate(`/whiskey/${w.id}`)}
            >
              <div className="sb-flight-name">{w.name}</div>
              <div className="sb-flight-detail">
                {w.category}{w.region ? ` \u2022 ${w.region}` : ''}
                {w.price_usd ? ` \u2022 ${w.price_is_estimated ? '~' : ''}$${Number(w.price_usd).toFixed(2)}${w.price_is_estimated ? ' Est.' : ''}` : ''}
              </div>
            </div>
            {i < whiskeys.length - 1 && <div className="sb-flight-arrow">\u2192</div>}
          </div>
        ))}
      </div>
    </div>
  )
})

// ── Palate profile chart (generative UI) ──────────────────────────────────────

const SidebarPalateProfile = memo(function SidebarPalateProfile({ profile }) {
  if (!profile) return null

  const flavors = (profile.top_flavors || []).slice(0, 6)
  const maxCount = Math.max(...Object.values(profile.top_categories || { x: 1 }), 1)

  return (
    <div className="sb-palate">
      <div className="sb-palate-title">Your Palate Profile</div>

      {/* Category bars */}
      {Object.entries(profile.top_categories || {}).map(([cat, count]) => (
        <div key={cat} className="sb-palate-bar-row">
          <span className="sb-palate-bar-label">{cat}</span>
          <div className="sb-palate-bar-track">
            <div
              className="sb-palate-bar-fill"
              style={{ width: `${Math.round((count / maxCount) * 100)}%` }}
            />
          </div>
          <span className="sb-palate-bar-count">{count}</span>
        </div>
      ))}

      {/* Flavor tags */}
      {flavors.length > 0 && (
        <div className="sb-palate-flavors">
          {flavors.map(f => (
            <span key={f} className="sb-palate-flavor-tag">{f}</span>
          ))}
        </div>
      )}

      {/* Stats row */}
      <div className="sb-palate-stats">
        {profile.whiskeys_rated > 0 && (
          <span>{profile.whiskeys_rated} rated</span>
        )}
        {profile.favorites_count > 0 && (
          <span>{profile.favorites_count} favorites</span>
        )}
        {profile.avg_price_usd > 0 && (
          <span>~${Number(profile.avg_price_usd).toFixed(2)} avg</span>
        )}
      </div>
    </div>
  )
})

// ── Price alternatives (generative UI) ───────────────────────────────────────

const SidebarPriceAlternatives = memo(function SidebarPriceAlternatives({ reference, whiskeys }) {
  const navigate = useNavigate()
  if (!reference || !whiskeys?.length) return null

  return (
    <div className="sb-price-alt">
      <div className="sb-price-alt-ref">
        <span className="sb-price-alt-label">Instead of</span>
        <span
          className="sb-price-alt-name"
          onClick={() => navigate(`/whiskey/${reference.id}`)}
        >
          {reference.name}
        </span>
        <span className="sb-price-alt-price">{reference.price_is_estimated ? '~' : ''}${Number(reference.price_usd).toFixed(2)}{reference.price_is_estimated ? ' Est.' : ''}</span>
      </div>
      <div className="sb-price-alt-arrow">\u2193 Save money with</div>
      {whiskeys.slice(0, 4).map(w => (
        <div
          key={w.id}
          className="sb-price-alt-item"
          onClick={() => navigate(`/whiskey/${w.id}`)}
          role="button"
          tabIndex={0}
          onKeyDown={e => e.key === 'Enter' && navigate(`/whiskey/${w.id}`)}
        >
          <span className="sb-price-alt-item-name">{w.name}</span>
          <span className="sb-price-alt-item-price">
            {w.price_is_estimated ? '~' : ''}${Number(w.price_usd).toFixed(2)}{w.price_is_estimated ? ' Est.' : ''}
            <span className="sb-price-alt-savings">
              (-${(reference.price_usd - w.price_usd).toFixed(2)})
            </span>
          </span>
        </div>
      ))}
    </div>
  )
})

// ── Main ChatSidebar component ───────────────────────────────────────────────

export default function ChatSidebar({ isOpen, onClose }) {
  const [messages, setMessages] = useState(() => {
    try {
      const stored = localStorage.getItem(CHAT_STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        return parsed.map(m => ({ ...m, isStreaming: false }))
      }
    } catch { /* corrupted data, start fresh */ }
    return []
  })
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [userLocation, setUserLocation] = useState(null)
  const [gpsStatus, setGpsStatus] = useState('pending') // pending | active | denied | unavailable
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  // ── Streaming text buffer: accumulate SSE text chunks in a ref, flush via RAF ──
  const streamBufferRef = useRef('')
  const rafIdRef = useRef(null)

  const flushStreamBuffer = useCallback(() => {
    rafIdRef.current = null
    const text = streamBufferRef.current
    if (!text) return
    streamBufferRef.current = ''
    setMessages(prev => {
      const updated = [...prev]
      const last = { ...updated[updated.length - 1] }
      last.content += text
      updated[updated.length - 1] = last
      return updated
    })
  }, [])

  const appendStreamText = useCallback((text) => {
    streamBufferRef.current += text
    if (rafIdRef.current == null) {
      rafIdRef.current = requestAnimationFrame(flushStreamBuffer)
    }
  }, [flushStreamBuffer])

  function requestLocation(signal) {
    if (!navigator.geolocation) {
      fallbackIpLocation(signal)
      return
    }
    // If already denied, the browser won't re-prompt — check via Permissions API first
    if (navigator.permissions) {
      navigator.permissions.query({ name: 'geolocation' }).then(result => {
        if (signal?.aborted) return
        if (result.state === 'denied') {
          setGpsStatus('denied')
          return
        }
        doGeoRequest(signal)
      }).catch(() => { if (!signal?.aborted) doGeoRequest(signal) })
    } else {
      doGeoRequest(signal)
    }
  }

  async function fallbackIpLocation(signal) {
    const services = [
      { url: 'https://ipapi.co/json/', parse: (d) => d.latitude && d.longitude ? { lat: d.latitude, lng: d.longitude } : null },
      { url: 'https://ip-api.com/json/?fields=lat,lon,status', parse: (d) => d.status === 'success' ? { lat: d.lat, lng: d.lon } : null },
    ]
    for (const svc of services) {
      if (signal?.aborted) return
      try {
        const res = await fetch(svc.url, { signal })
        if (!res.ok) continue
        const data = await res.json()
        const pos = svc.parse(data)
        if (pos) {
          setUserLocation(pos)
          setGpsStatus('active')
          return
        }
      } catch { /* try next or aborted */ }
    }
    if (!signal?.aborted) setGpsStatus('unavailable')
  }

  function doGeoRequest(signal) {
    setGpsStatus('pending')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (signal?.aborted) return
        setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setGpsStatus('active')
      },
      (err) => {
        if (signal?.aborted) return
        if (err.code === err.PERMISSION_DENIED) {
          setGpsStatus('denied')
        } else {
          fallbackIpLocation(signal)
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
    )
  }

  // Grab user's real GPS location once on mount
  useEffect(() => {
    const controller = new AbortController()
    requestLocation(controller.signal)
    return () => controller.abort()
  }, [])

  // ── Throttled scroll: at most once per animation frame ──
  const scrollRafRef = useRef(null)
  useEffect(() => {
    if (scrollRafRef.current) return
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = null
      bottomRef.current?.scrollIntoView({ behavior: 'auto' })
    })
  }, [messages])

  // Persist completed messages to localStorage — skip entirely while streaming
  const saveTimerRef = useRef(null)
  useEffect(() => {
    if (messages.some(m => m.isStreaming)) return
    clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      try {
        const toStore = messages.slice(-MAX_CHAT_MESSAGES)
        localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(toStore))
      } catch (e) {
        if (e?.name === 'QuotaExceededError' || e?.code === 22) {
          const trimmed = messages.slice(-20)
          try { localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(trimmed)) } catch { /* give up */ }
        }
      }
    }, 500)
    return () => clearTimeout(saveTimerRef.current)
  }, [messages])

  useEffect(() => {
    if (isOpen) textareaRef.current?.focus()
  }, [isOpen])

  async function sendMessage(text) {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return

    const userMsg = {
      role: 'user', content: trimmed,
      whiskeys: [], genUI: [], isStreaming: false,
    }
    const assistantMsg = {
      role: 'assistant', content: '',
      whiskeys: [], genUI: [], isStreaming: true,
    }
    const nextMessages = [...messages, userMsg].slice(-MAX_CHAT_MESSAGES)

    setMessages([...nextMessages, assistantMsg])
    setInput('')
    setIsLoading(true)

    const history = nextMessages.map(m => ({ role: m.role, content: m.content }))

    // Abort the stream if it takes too long (90s total, or 30s with no data)
    const controller = new AbortController()
    const hardTimeout = setTimeout(() => controller.abort(), 90_000)
    let idleTimer = null

    function resetIdleTimer() {
      clearTimeout(idleTimer)
      idleTimer = setTimeout(() => controller.abort(), 30_000)
    }

    try {
      const response = await api.chatStream(history, null, userLocation, controller.signal)
      if (!response.ok) throw new Error('Chat request failed')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      resetIdleTimer()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        resetIdleTimer()
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop()

        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'error') {
              throw new Error(event.message || 'Server error')
            }
            handleSseEvent(event)
          } catch (e) {
            if (e.message && e.message !== 'Server error') continue
            throw e
          }
        }
      }

      // Process any remaining data in the buffer after stream ends
      if (buffer.trim()) {
        const line = buffer.trim()
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type !== 'error') handleSseEvent(event)
          } catch { /* ignore parse errors in final chunk */ }
        }
      }
    } catch (err) {
      // Don't show an error when the stream was intentionally aborted (timeout or navigation)
      if (err?.name !== 'AbortError') {
        setMessages(prev => {
          const updated = [...prev]
          const last = { ...updated[updated.length - 1] }
          last.content = last.content || 'Sorry, something went wrong. Please try again.'
          last.isStreaming = false
          updated[updated.length - 1] = last
          return updated
        })
      }
    } finally {
      clearTimeout(hardTimeout)
      clearTimeout(idleTimer)
      // Flush any remaining buffered text before finalizing
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current)
        rafIdRef.current = null
      }
      const remaining = streamBufferRef.current
      streamBufferRef.current = ''
      setMessages(prev => {
        const updated = [...prev]
        const last = { ...updated[updated.length - 1] }
        if (remaining) last.content += remaining
        last.isStreaming = false
        updated[updated.length - 1] = last
        return updated
      })
      setIsLoading(false)
      textareaRef.current?.focus()
    }
  }

  function handleSseEvent(event) {
    const updateLast = (updater) => {
      setMessages(prev => {
        const updated = [...prev]
        const last = { ...updated[updated.length - 1] }
        updater(last)
        updated[updated.length - 1] = last
        return updated
      })
    }

    switch (event.type) {
      case 'thinking':
        updateLast(last => { last.toolStatus = 'Thinking\u2026' })
        break

      case 'tool_start': {
        const labels = {
          search_whiskeys: 'Searching whiskeys\u2026',
          get_top_rated: 'Finding top-rated picks\u2026',
          compare_whiskeys: 'Comparing whiskeys\u2026',
          find_nearby_stores: 'Searching for stores\u2026',
          build_tasting_flight: 'Building a flight\u2026',
          get_similar_whiskeys: 'Finding similar bottles\u2026',
          get_recommendations: 'Getting recommendations\u2026',
          find_value_picks: 'Finding value picks\u2026',
          find_cheaper_alternatives: 'Finding alternatives\u2026',
          generate_palate_profile: 'Analyzing your palate\u2026',
          get_database_stats: 'Checking the database\u2026',
          find_gift_recommendation: 'Finding gift ideas\u2026',
          create_learning_path: 'Building your journey\u2026',
        }
        const label = labels[event.tool] || 'Working\u2026'
        updateLast(last => { last.toolStatus = label })
        break
      }

      case 'text':
        // Buffer text in a ref and flush once per animation frame
        appendStreamText(event.content)
        break

      case 'whiskeys':
        updateLast(last => {
          last.whiskeys = [...(last.whiskeys || []), ...event.whiskeys]
        })
        break

      case 'map':
        updateLast(last => {
          last.genUI = [...(last.genUI || []), {
            type: 'map',
            stores: event.stores,
            center: event.center,
          }]
        })
        break

      case 'comparison':
        updateLast(last => {
          last.genUI = [...(last.genUI || []), {
            type: 'comparison',
            whiskeys: event.whiskeys,
            rows: event.rows,
          }]
        })
        break

      case 'flight':
        updateLast(last => {
          last.genUI = [...(last.genUI || []), {
            type: 'flight',
            story: event.story,
            whiskeys: event.whiskeys,
          }]
        })
        break

      case 'palate_profile':
        updateLast(last => {
          last.genUI = [...(last.genUI || []), {
            type: 'palate_profile',
            profile: event.profile,
          }]
        })
        break

      case 'price_alternatives':
        updateLast(last => {
          last.genUI = [...(last.genUI || []), {
            type: 'price_alternatives',
            reference: event.reference,
            whiskeys: event.whiskeys,
          }]
        })
        break

      case 'done':
        updateLast(last => { last.isStreaming = false })
        break

      default:
        break
    }
  }

  function renderGenUI(item, i) {
    switch (item.type) {
      case 'map':
        return (
          <Suspense key={`map-${i}`} fallback={<div className="sb-map-loading">Loading map...</div>}>
            <SidebarMap stores={item.stores} center={item.center} />
          </Suspense>
        )
      case 'comparison':
        return <SidebarComparison key={`comp-${i}`} whiskeys={item.whiskeys} rows={item.rows} />
      case 'flight':
        return <SidebarFlight key={`flight-${i}`} story={item.story} whiskeys={item.whiskeys} />
      case 'palate_profile':
        return <SidebarPalateProfile key={`palate-${i}`} profile={item.profile} />
      case 'price_alternatives':
        return (
          <SidebarPriceAlternatives
            key={`price-${i}`}
            reference={item.reference}
            whiskeys={item.whiskeys}
          />
        )
      default:
        return null
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <>
      {/* Backdrop (mobile) */}
      {isOpen && <div className="sb-backdrop" onClick={onClose} />}

      <div className={`chat-sidebar ${isOpen ? 'chat-sidebar--open' : ''}`}>
        {/* Header */}
        <div className="sb-header">
          <div className="sb-title-row">
            <span className="sb-title">{'\u{1F943}'} Ask Sip Sense</span>
            <button
              className={`sb-gps-indicator sb-gps-indicator--${gpsStatus}`}
              onClick={gpsStatus !== 'active' ? requestLocation : undefined}
              title={
                gpsStatus === 'active' ? 'GPS active' :
                gpsStatus === 'denied' ? 'Location blocked — check browser settings' :
                gpsStatus === 'unavailable' ? 'Click to retry location' : 'Locating...'
              }
            >
              <span className="sb-gps-dot" />
              {gpsStatus === 'denied' && (
                <span className="sb-gps-label">GPS Blocked</span>
              )}
              {gpsStatus === 'unavailable' && (
                <span className="sb-gps-label">Enable GPS</span>
              )}
            </button>
          </div>
          <div className="sb-header-actions">
            {messages.length > 0 && (
              <button className="sb-clear-btn" onClick={() => {
                setMessages([])
                localStorage.removeItem(CHAT_STORAGE_KEY)
              }}>
                Clear
              </button>
            )}
            <button className="sb-close-btn" onClick={onClose} aria-label="Close">{'\u2715'}</button>
          </div>
        </div>

        {/* Messages */}
        <div className="sb-messages">
          {gpsStatus === 'denied' && (
            <div className="sb-gps-banner">
              <span>Location blocked — click the lock icon in your address bar to allow location access, then reload.</span>
            </div>
          )}
          {gpsStatus === 'unavailable' && (
            <div className="sb-gps-banner">
              <span>Could not get your location — store finder will use city names instead.</span>
              <button onClick={requestLocation}>Try Again</button>
            </div>
          )}

          {messages.length === 0 && (
            <div className="sb-starters">
              <p className="sb-starters-label">Ask me anything about whiskey</p>
              {STARTER_PROMPTS.map(p => (
                <button key={p} className="sb-starter-btn" onClick={() => sendMessage(p)}>
                  {p}
                </button>
              ))}
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={`${msg.role}-${i}`} className={`sb-bubble-wrap sb-bubble-wrap--${msg.role}`}>
              <div className={`sb-bubble sb-bubble--${msg.role}`}>
                {msg.content && (
                  <p className="sb-bubble-text">
                    {msg.content}
                    {msg.isStreaming && <span className="sb-cursor" />}
                  </p>
                )}
                {msg.isStreaming && !msg.content && (
                  <p className="sb-bubble-text sb-thinking">
                    {msg.toolStatus && <span className="sb-tool-status">{msg.toolStatus}</span>}
                    {!msg.toolStatus && <span className="sb-cursor" />}
                  </p>
                )}

                {/* Generative UI blocks */}
                {(msg.genUI || []).map((item, j) => renderGenUI(item, j))}

                {/* Whiskey cards */}
                {(msg.whiskeys || []).length > 0 && (
                  <div className="sb-cards">
                    {msg.whiskeys.slice(0, 6).map(w => (
                      <SidebarWhiskeyCard key={w.id} whiskey={w} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="sb-input-area">
          <textarea
            ref={textareaRef}
            className="sb-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="What are you sipping on?"
            rows={2}
            disabled={isLoading}
          />
          <button
            className="sb-send-btn"
            onClick={() => sendMessage(input)}
            disabled={isLoading || !input.trim()}
          >
            {isLoading ? '\u2026' : '\u2191'}
          </button>
        </div>
      </div>
    </>
  )
}
