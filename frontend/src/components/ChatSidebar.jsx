import { useState, useRef, useEffect, lazy, Suspense } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import './ChatSidebar.css'

const CHAT_STORAGE_KEY = 'sipsense_chat_messages'

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

function SidebarWhiskeyCard({ whiskey }) {
  const navigate = useNavigate()
  const stars = Math.round(whiskey.rating_avg || 0)
  const emoji = {
    bourbon: '\u{1F943}', scotch: '\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}', irish: '\u2618\uFE0F',
    japanese: '\u{1F5FE}', rye: '\u{1F33E}', canadian: '\u{1F341}',
    'single malt': '\u{1F3F0}', blended: '\u{1F943}',
  }[whiskey.category] || '\u{1F943}'

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
        {whiskey.price_usd && <span className="sb-badge">${whiskey.price_usd}</span>}
        {whiskey.rating_avg > 0 && (
          <span className="sb-badge sb-badge--rating">
            {'\u2605'.repeat(stars)}{'\u2606'.repeat(5 - stars)} {whiskey.rating_avg.toFixed(1)}
          </span>
        )}
      </div>
    </div>
  )
}

// ── Comparison table (generative UI) ─────────────────────────────────────────

function SidebarComparison({ whiskeys, rows }) {
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
}

// ── Flight visualization (generative UI) ─────────────────────────────────────

function SidebarFlight({ story, whiskeys }) {
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
                {w.price_usd ? ` \u2022 $${w.price_usd}` : ''}
              </div>
            </div>
            {i < whiskeys.length - 1 && <div className="sb-flight-arrow">\u2192</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Palate profile chart (generative UI) ──────────────────────────────────────

function SidebarPalateProfile({ profile }) {
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
          <span>~${Math.round(profile.avg_price_usd)} avg</span>
        )}
      </div>
    </div>
  )
}

// ── Price alternatives (generative UI) ───────────────────────────────────────

function SidebarPriceAlternatives({ reference, whiskeys }) {
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
        <span className="sb-price-alt-price">${reference.price_usd}</span>
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
            ${w.price_usd}
            <span className="sb-price-alt-savings">
              (-${Math.round(reference.price_usd - w.price_usd)})
            </span>
          </span>
        </div>
      ))}
    </div>
  )
}

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
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  // Grab user's real GPS location once on mount
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        () => { /* permission denied or unavailable — geocoding fallback still works */ },
        { timeout: 5000 }
      )
    }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Persist completed messages to localStorage
  useEffect(() => {
    try {
      const toStore = messages.filter(m => !m.isStreaming)
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(toStore))
    } catch { /* localStorage full or unavailable */ }
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
    const nextMessages = [...messages, userMsg]

    setMessages([...nextMessages, assistantMsg])
    setInput('')
    setIsLoading(true)

    const history = nextMessages.map(m => ({ role: m.role, content: m.content }))

    try {
      const response = await api.chatStream(history, null, userLocation)
      if (!response.ok) throw new Error('Chat request failed')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop()

        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            handleSseEvent(event)
          } catch { /* malformed chunk */ }
        }
      }
    } catch {
      setMessages(prev => {
        const updated = [...prev]
        const last = { ...updated[updated.length - 1] }
        last.content = last.content || 'Sorry, something went wrong. Please try again.'
        last.isStreaming = false
        updated[updated.length - 1] = last
        return updated
      })
    } finally {
      setMessages(prev => {
        const updated = [...prev]
        const last = { ...updated[updated.length - 1] }
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
      case 'text':
        updateLast(last => { last.content += event.content })
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
          <span className="sb-title">{'\u{1F943}'} Ask SipSense</span>
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
            <div key={i} className={`sb-bubble-wrap sb-bubble-wrap--${msg.role}`}>
              <div className={`sb-bubble sb-bubble--${msg.role}`}>
                {msg.content && (
                  <p className="sb-bubble-text">
                    {msg.content}
                    {msg.isStreaming && <span className="sb-cursor" />}
                  </p>
                )}
                {msg.isStreaming && !msg.content && (
                  <p className="sb-bubble-text sb-thinking">
                    <span className="sb-cursor" />
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
            placeholder="Ask about whiskey\u2026 (Enter to send)"
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
