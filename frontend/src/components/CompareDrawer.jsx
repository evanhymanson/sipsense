import { useState, useEffect, useMemo } from 'react'
import { api } from '../api/client'
import './CompareDrawer.css'

function CompareRow({ label, values, mode }) {
  // mode: 'higher' = higher is better, 'lower' = lower is better, 'neutral'
  const numericVals = values.map(v => typeof v === 'number' ? v : parseFloat(String(v).replace(/[^0-9.]/g, '')) || null)

  function isWinner(idx) {
    if (mode === 'neutral') return false
    const val = numericVals[idx]
    if (val == null) return false
    const others = numericVals.filter((v, i) => i !== idx && v != null)
    if (others.length === 0) return false
    if (mode === 'higher') return others.every(o => val > o)
    if (mode === 'lower') return others.every(o => val < o)
    return false
  }

  return (
    <div className="cd-row">
      <div className="cd-row-label">{label}</div>
      {values.map((v, i) => (
        <div key={i} className={`cd-row-val${isWinner(i) ? ' cd-row-val--winner' : ''}`}>
          {v ?? '—'}
        </div>
      ))}
    </div>
  )
}

export default function CompareDrawer({ whiskeys, onRemove, onClose }) {
  const [comparison, setComparison] = useState(null)

  // Stabilize dependency — only re-fetch when the actual IDs change
  const whiskeyIdKey = useMemo(() => whiskeys.map(w => w.id).join(','), [whiskeys])

  useEffect(() => {
    if (whiskeys.length === 2) {
      api.compareBottles(whiskeys[0].id, whiskeys[1].id)
        .then(setComparison)
        .catch(() => setComparison(null))
    } else {
      setComparison(null)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [whiskeyIdKey])

  if (whiskeys.length === 0) return null

  // Use comparison data if available, otherwise use raw whiskey data
  const bottles = whiskeys.length === 2 && comparison
    ? [comparison.a, comparison.b]
    : whiskeys

  return (
    <div className="compare-drawer" role="dialog" aria-label="Compare whiskeys">
      <div className="cd-header">
        <h3>Compare ({whiskeys.length}/2)</h3>
        <div className="cd-header-actions">
          {whiskeys.length < 2 && <span className="cd-hint">Select {2 - whiskeys.length} more to compare</span>}
          {whiskeys.length > 0 && (
            <button className="cd-clear-all" onClick={() => { whiskeys.forEach(w => onRemove(w.id)) }}>Clear All</button>
          )}
          <button className="cd-close" onClick={onClose} aria-label="Close compare drawer">×</button>
        </div>
      </div>

      {/* Selected bottles */}
      <div className="cd-bottles">
        {whiskeys.map(w => (
          <div key={w.id} className="cd-bottle">
            <button className="cd-bottle-remove" onClick={() => onRemove(w.id)}>×</button>
            <div className="cd-bottle-name">{w.name}</div>
            <div className="cd-bottle-dist">{w.distillery}</div>
          </div>
        ))}
      </div>

      {/* Comparison table — only when 2+ bottles selected */}
      {bottles.length >= 2 && (
        <div className="cd-table">
          <CompareRow label="Price" values={bottles.map(w => w.price_usd ? `${w.price_is_estimated ? '~' : ''}$${Number(w.price_usd).toFixed(2)}${w.price_is_estimated ? ' Est.' : ''}` : null)} mode="lower" />
          <CompareRow label="Rating" values={bottles.map(w => w.rating_avg ? Number(w.rating_avg).toFixed(1) : null)} mode="higher" />
          <CompareRow label="Age" values={bottles.map(w => w.age ? `${w.age}yr` : null)} mode="higher" />
          <CompareRow label="ABV" values={bottles.map(w => w.abv ? `${w.abv}%` : null)} mode="neutral" />
          <CompareRow label="Category" values={bottles.map(w => w.category)} mode="neutral" />
          <CompareRow label="Region" values={bottles.map(w => w.region || null)} mode="neutral" />
        </div>
      )}
    </div>
  )
}
