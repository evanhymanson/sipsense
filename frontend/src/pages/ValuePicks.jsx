import { useState, useEffect } from 'react'
import { api } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'

const CATEGORIES = ['', 'bourbon', 'scotch', 'irish', 'japanese', 'rye', 'canadian', 'single malt', 'blended']
const BUDGET_PRESETS = [
  { label: 'Under $30', max: 30 },
  { label: 'Under $50', max: 50 },
  { label: 'Under $75', max: 75 },
  { label: 'Under $150', max: 150 },
]

export default function ValuePicks() {
  const [whiskeys, setWhiskeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [category, setCategory] = useState('')
  const [maxPrice, setMaxPrice] = useState(75)
  const [activePreset, setActivePreset] = useState(75)

  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = { max_price: maxPrice, limit: 12 }
    if (category) params.category = category
    api.getValuePicks(params)
      .then(setWhiskeys)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [category, maxPrice])

  function applyPreset(max) {
    setMaxPrice(max)
    setActivePreset(max)
  }

  return (
    <div className="page">
      <h1>Value Picks</h1>
      <p className="page-subtitle">
        Best bang for the buck — ranked by rating relative to price. Hidden gems that punch above their weight.
      </p>

      <div className="vp-controls">
        <div className="vp-presets">
          {BUDGET_PRESETS.map((p) => (
            <button
              key={p.max}
              className={`vp-preset-btn ${activePreset === p.max ? 'vp-preset-btn--active' : ''}`}
              onClick={() => applyPreset(p.max)}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="filter-bar">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All categories</option>
            {CATEGORIES.filter(Boolean).map((c) => (
              <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
            ))}
          </select>

          <div className="vp-price-input">
            <label>Max price</label>
            <input
              type="number"
              min={10}
              max={500}
              value={maxPrice}
              onChange={(e) => {
                setMaxPrice(Number(e.target.value))
                setActivePreset(null)
              }}
            />
          </div>
        </div>
      </div>

      <div className="vp-score-note">
        Scored by rating ÷ log(price) — a high rating at a low price wins.
      </div>

      {loading && <p className="status">Finding value picks...</p>}
      {error && <p className="status error">{error}</p>}

      {!loading && !error && whiskeys.length === 0 && (
        <p className="status">No results for those filters. Try a higher price ceiling.</p>
      )}

      {!loading && whiskeys.length > 0 && (
        <div className="card-grid">
          {whiskeys.map((w, i) => (
            <div key={w.id} className="vp-ranked-card">
              <div className="vp-rank">#{i + 1}</div>
              <WhiskeyCard whiskey={w} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
