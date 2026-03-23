import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { getCategoryEmoji } from '../constants'
import './Discover.css'

const CATEGORIES_MAP = [
  { value: 'irish',       label: 'Irish',       x: '22%', y: '15%' },
  { value: 'japanese',    label: 'Japanese',     x: '42%', y: '20%' },
  { value: 'canadian',    label: 'Canadian',     x: '18%', y: '38%' },
  { value: 'single malt', label: 'Single Malt', x: '62%', y: '38%' },
  { value: 'wheat',       label: 'Wheat',        x: '30%', y: '50%' },
  { value: 'bourbon',     label: 'Bourbon',      x: '25%', y: '70%' },
  { value: 'rye',         label: 'Rye',          x: '58%', y: '72%' },
  { value: 'scotch',      label: 'Scotch',       x: '78%', y: '58%' },
]

export default function Discover() {
  const navigate = useNavigate()
  const [daily, setDaily] = useState(null)
  const [dailyCollapsed, setDailyCollapsed] = useState(false)
  const [dailyError, setDailyError] = useState(false)

  // Load daily discovery
  useEffect(() => {
    api.getDailyDiscovery()
      .then(setDaily)
      .catch(() => setDailyError(true))
  }, [])

  const dailyWhiskey = daily?.whiskey

  return (
    <div className="discover-page">
      {/* ── Daily Discovery Banner ─────────────────────────────── */}
      {dailyWhiskey && (
        <div className={`discover-daily ${dailyCollapsed ? 'discover-daily--collapsed' : ''}`}>
          <div className="discover-daily-main" role="button" tabIndex={0} aria-label={`View ${dailyWhiskey.name}`} onClick={() => navigate(`/whiskey/${dailyWhiskey.id}`)} onKeyDown={e => e.key === 'Enter' && navigate(`/whiskey/${dailyWhiskey.id}`)}>
            <span className="discover-daily-badge">Today's Discovery</span>
            <span className="discover-daily-name">{dailyWhiskey.name}</span>
            <span className="discover-daily-meta">
              {dailyWhiskey.distillery} · {dailyWhiskey.category}
              {dailyWhiskey.price_usd && ` · ${dailyWhiskey.price_is_estimated ? '~' : ''}$${Number(dailyWhiskey.price_usd).toFixed(2)}${dailyWhiskey.price_is_estimated ? ' Est.' : ''}`}
            </span>
          </div>
          {!dailyCollapsed && daily.tasting_tip && (
            <div className="discover-daily-tip">
              <span>Tasting Tip:</span> {daily.tasting_tip}
            </div>
          )}
          <button className="discover-daily-toggle" onClick={(e) => { e.stopPropagation(); setDailyCollapsed(!dailyCollapsed) }}>
            {dailyCollapsed ? '▼' : '▲'}
          </button>
        </div>
      )}
      {dailyError && !dailyWhiskey && (
        <p className="page-subtitle" style={{ textAlign: 'center', padding: '0.5rem' }}>Could not load today's discovery.</p>
      )}

      {/* ── Page Header ──────────────────────────────────────── */}
      <div className="discover-graph-header">
        <h1>Discover</h1>
        <p>Explore the world of whiskey by style, flavor, and more.</p>
      </div>

      {/* ── Whiskey Compass ─────────────────────────────────── */}
      <div className="category-map-section">
        <h2>Whiskey Compass</h2>
        <p>Tap a style to explore bottles in that world</p>
        <div className="category-map">
          <span className="cm-axis cm-axis--top">Light</span>
          <span className="cm-axis cm-axis--bottom">Bold</span>
          <span className="cm-axis cm-axis--left">Sweet</span>
          <span className="cm-axis cm-axis--right">Smoky</span>
          <div className="cm-crosshair-h" />
          <div className="cm-crosshair-v" />
          {CATEGORIES_MAP.map(cat => (
            <button
              key={cat.value}
              className="cm-node"
              style={{ left: cat.x, top: cat.y }}
              onClick={() => navigate(`/?category=${encodeURIComponent(cat.value)}`)}
            >
              <span className="cm-node-emoji">{getCategoryEmoji(cat.value)}</span>
              <span className="cm-node-label">{cat.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Quick Access Cards ─────────────────────────────────── */}
      <div className="discover-quick">
        <h2>Quick Access</h2>
        <div className="discover-quick-grid">
          <button className="discover-quick-card" onClick={() => navigate('/quiz')}>
            <span className="dqc-emoji">🎯</span>
            <span className="dqc-label">Taste Quiz</span>
            <span className="dqc-desc">Find your perfect match</span>
          </button>
          <button className="discover-quick-card" onClick={() => navigate('/')}>
            <span className="dqc-emoji">🔍</span>
            <span className="dqc-label">Browse All</span>
            <span className="dqc-desc">Explore the full catalog</span>
          </button>
        </div>
      </div>
    </div>
  )
}
