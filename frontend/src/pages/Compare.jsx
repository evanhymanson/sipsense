import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../api/client'
import './Compare.css'

function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}

function WhiskeySearch({ slot, onSelect, selected }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const debouncedQuery = useDebounce(query, 280)
  const ref = useRef(null)

  useEffect(() => {
    if (debouncedQuery.length < 2) {
      setResults([])
      return
    }
    api.listWhiskeys({ q: debouncedQuery, limit: 6 }).then(setResults)
  }, [debouncedQuery])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const choose = (whiskey) => {
    onSelect(whiskey)
    setQuery('')
    setResults([])
    setOpen(false)
  }

  if (selected) {
    return (
      <div className="search-selected">
        <button className="clear-btn" onClick={() => onSelect(null)}>✕</button>
        <div className="selected-name">{selected.name}</div>
        <div className="selected-dist">{selected.distillery}</div>
      </div>
    )
  }

  return (
    <div className="search-box" ref={ref}>
      <input
        className="search-input"
        placeholder={`Search ${slot === 'a' ? 'first' : 'second'} bottle…`}
        value={query}
        onChange={e => { setQuery(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
      />
      {open && results.length > 0 && (
        <ul className="search-dropdown">
          {results.map(w => (
            <li key={w.id} onMouseDown={() => choose(w)}>
              <span className="dd-name">{w.name}</span>
              <span className="dd-meta">{w.distillery} · {w.category}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function CompareRow({ label, valA, valB, mode }) {
  // mode: 'higher' = higher is better, 'lower' = lower is better, 'neutral'
  const bothPresent = valA != null && valB != null

  const winnerA = bothPresent && mode === 'higher' && valA > valB
  const winnerB = bothPresent && mode === 'higher' && valB > valA
  const cheaperA = bothPresent && mode === 'lower' && valA < valB
  const cheaperB = bothPresent && mode === 'lower' && valB < valA

  return (
    <div className="compare-row">
      <div className={`compare-cell ${winnerA || cheaperA ? 'winner' : ''}`}>
        {valA != null ? valA : <span className="compare-na">—</span>}
      </div>
      <div className="compare-label">{label}</div>
      <div className={`compare-cell ${winnerB || cheaperB ? 'winner' : ''}`}>
        {valB != null ? valB : <span className="compare-na">—</span>}
      </div>
    </div>
  )
}

function AbvBar({ value, label }) {
  const pct = value ? Math.min((value / 70) * 100, 100) : 0
  return (
    <div className="abv-bar-wrap">
      <div className="abv-bar-track">
        <div className="abv-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="abv-value">{value ? `${value}%` : '—'}</span>
    </div>
  )
}

function RatingBar({ value }) {
  const pct = value ? (value / 5) * 100 : 0
  return (
    <div className="rating-bar-wrap">
      <div className="rating-bar-track">
        <div className="rating-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="rating-value">{value ? value.toFixed(1) : '—'}</span>
    </div>
  )
}

function BottlePanel({ whiskey, side }) {
  if (!whiskey) return <div className="bottle-panel empty"><p>Select a bottle</p></div>

  const tags = whiskey.flavor_profile
    ? whiskey.flavor_profile.split(',').map(t => t.trim()).filter(Boolean)
    : []

  return (
    <div className={`bottle-panel ${side}`}>
      <div className="panel-name">{whiskey.name}</div>
      <div className="panel-dist">{whiskey.distillery}</div>
      <div className="panel-chips">
        <span className="panel-chip">{whiskey.category}</span>
        {whiskey.region && <span className="panel-chip">{whiskey.region}</span>}
      </div>
      <div className="panel-price">
        {whiskey.price_usd ? `$${whiskey.price_usd.toFixed(0)}` : 'Price N/A'}
      </div>
      <div className="panel-abv-label">ABV</div>
      <AbvBar value={whiskey.abv} />
      <div className="panel-rating-label">Rating</div>
      <RatingBar value={whiskey.rating_avg} />
      {tags.length > 0 && (
        <div className="panel-flavors">
          {tags.slice(0, 5).map(t => <span key={t} className="flavor-chip">{t}</span>)}
        </div>
      )}
    </div>
  )
}

export default function Compare() {
  const [a, setA] = useState(null)
  const [b, setB] = useState(null)
  const [comparison, setComparison] = useState(null)

  useEffect(() => {
    if (a && b) {
      api.compareBottles(a.id, b.id).then(setComparison)
    } else {
      setComparison(null)
    }
  }, [a, b])

  const wa = comparison?.a || a
  const wb = comparison?.b || b

  return (
    <div className="compare-page">
      <div className="compare-hero">
        <h1>Bottle Compare</h1>
        <p>Search for two bottles and see them side by side.</p>
      </div>

      <div className="search-row">
        <WhiskeySearch slot="a" selected={a} onSelect={setA} />
        <span className="vs-badge">vs</span>
        <WhiskeySearch slot="b" selected={b} onSelect={setB} />
      </div>

      <div className="panels-row">
        <BottlePanel whiskey={wa} side="left" />
        <div className="panels-divider" />
        <BottlePanel whiskey={wb} side="right" />
      </div>

      {wa && wb && (
        <div className="compare-table">
          <h3>Head to Head</h3>
          <CompareRow
            label="Price"
            valA={wa.price_usd ? `$${wa.price_usd.toFixed(0)}` : null}
            valB={wb.price_usd ? `$${wb.price_usd.toFixed(0)}` : null}
            mode="lower"
          />
          <CompareRow
            label="Rating"
            valA={wa.rating_avg ? wa.rating_avg.toFixed(1) : null}
            valB={wb.rating_avg ? wb.rating_avg.toFixed(1) : null}
            mode="higher"
          />
          <CompareRow
            label="Age"
            valA={wa.age ? `${wa.age}yr` : null}
            valB={wb.age ? `${wb.age}yr` : null}
            mode="higher"
          />
          <CompareRow
            label="ABV"
            valA={wa.abv ? `${wa.abv}%` : null}
            valB={wb.abv ? `${wb.abv}%` : null}
            mode="neutral"
          />
          <CompareRow
            label="Category"
            valA={wa.category}
            valB={wb.category}
            mode="neutral"
          />
          <CompareRow
            label="Region"
            valA={wa.region || null}
            valB={wb.region || null}
            mode="neutral"
          />
        </div>
      )}

      {!a && !b && (
        <div className="compare-empty">
          <p>Search for two whiskeys above to compare them.</p>
        </div>
      )}
    </div>
  )
}
