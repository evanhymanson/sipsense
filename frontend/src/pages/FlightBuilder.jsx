import { useState, useEffect } from 'react'
import { api } from '../api/client'
import './FlightBuilder.css'

function StarRating({ value }) {
  return (
    <span className="star-rating">
      {[1, 2, 3, 4, 5].map(n => (
        <span key={n} className={n <= Math.round(value) ? 'star filled' : 'star'}>★</span>
      ))}
      <span className="rating-num">{value ? value.toFixed(1) : '—'}</span>
    </span>
  )
}

function ThemeCard({ theme, selected, onSelect }) {
  return (
    <button
      className={`theme-card ${selected ? 'selected' : ''}`}
      onClick={() => onSelect(theme.slug)}
    >
      <span className="theme-emoji">{theme.emoji}</span>
      <span className="theme-label">{theme.label}</span>
      <span className="theme-tagline">{theme.tagline}</span>
    </button>
  )
}

function FlightBottle({ bottle, index, total }) {
  return (
    <div className="flight-bottle">
      <div className="step-badge">{bottle.step_label}</div>
      <div className="bottle-card">
        <div className="bottle-name">{bottle.whiskey.name}</div>
        <div className="bottle-distillery">{bottle.whiskey.distillery}</div>
        <div className="bottle-meta">
          {bottle.whiskey.age && <span>{bottle.whiskey.age}yr</span>}
          {bottle.whiskey.abv && <span>{bottle.whiskey.abv}% ABV</span>}
          {bottle.whiskey.price_usd && <span>${bottle.whiskey.price_usd}</span>}
        </div>
        <StarRating value={bottle.whiskey.rating_avg} />
        {bottle.whiskey.flavor_profile && (
          <div className="bottle-flavors">
            {bottle.whiskey.flavor_profile.split(',').slice(0, 4).map(f => (
              <span key={f} className="flavor-chip">{f.trim()}</span>
            ))}
          </div>
        )}
      </div>
      <div className="bottle-lesson">
        <span className="lesson-label">What to look for</span>
        <p>{bottle.lesson}</p>
      </div>
      {index < total - 1 && <div className="flight-arrow">→</div>}
    </div>
  )
}

export default function FlightBuilder() {
  const [themes, setThemes] = useState([])
  const [selectedTheme, setSelectedTheme] = useState(null)
  const [flight, setFlight] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [maxPrice, setMaxPrice] = useState('')

  useEffect(() => {
    api.listFlightThemes().then(setThemes)
  }, [])

  const buildFlight = (slug) => {
    setSelectedTheme(slug)
    setFlight(null)
    setError(null)
    setLoading(true)
    api.getFlight(slug, maxPrice ? parseFloat(maxPrice) : 0, 4)
      .then(setFlight)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  return (
    <div className="flight-page">
      <div className="flight-hero">
        <h1>Flight Builder</h1>
        <p>
          Pick a theme and get a curated progression of bottles — each one
          chosen to teach your palate something new.
        </p>
      </div>

      <div className="flight-controls">
        <div className="theme-grid">
          {themes.map(t => (
            <ThemeCard
              key={t.slug}
              theme={t}
              selected={selectedTheme === t.slug}
              onSelect={buildFlight}
            />
          ))}
        </div>

        <div className="price-filter">
          <label htmlFor="max-price">Max price per bottle</label>
          <div className="price-input-row">
            <span className="price-symbol">$</span>
            <input
              id="max-price"
              type="number"
              placeholder="No limit"
              value={maxPrice}
              onChange={e => setMaxPrice(e.target.value)}
            />
            {selectedTheme && (
              <button className="rebuild-btn" onClick={() => buildFlight(selectedTheme)}>
                Rebuild
              </button>
            )}
          </div>
        </div>
      </div>

      {loading && (
        <div className="flight-loading">
          <div className="loading-glass">🥃</div>
          <p>Building your flight…</p>
        </div>
      )}

      {error && (
        <div className="flight-error">
          {error}
        </div>
      )}

      {flight && !loading && (
        <div className="flight-result">
          <div className="flight-header">
            <span className="flight-emoji">{flight.emoji}</span>
            <div>
              <h2>{flight.label}</h2>
              <p>{flight.tagline}</p>
            </div>
          </div>
          <div className="flight-bottles">
            {flight.bottles.map((bottle, i) => (
              <FlightBottle
                key={bottle.step}
                bottle={bottle}
                index={i}
                total={flight.bottles.length}
              />
            ))}
          </div>
        </div>
      )}

      {!flight && !loading && !error && (
        <div className="flight-prompt">
          <p>← Select a theme above to build your flight</p>
        </div>
      )}
    </div>
  )
}
