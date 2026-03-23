import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import './FlavorMap.css'

// ── Flavor tag → axis weight mapping ────────────────────────────────────────
// X axis: Sweet (0) → Smoky (1)   — matches Discover compass
// Y axis: Light (0) → Bold (1)    — matches Discover compass
const FLAVOR_WEIGHTS = {
  // Sweet side
  vanilla: { x: 0.15, y: 0.45 }, caramel: { x: 0.15, y: 0.60 },
  honey: { x: 0.10, y: 0.35 }, toffee: { x: 0.20, y: 0.55 },
  maple: { x: 0.10, y: 0.50 }, butterscotch: { x: 0.15, y: 0.50 },
  butter: { x: 0.20, y: 0.45 }, 'brown sugar': { x: 0.15, y: 0.50 },
  candy: { x: 0.05, y: 0.30 }, marshmallow: { x: 0.05, y: 0.25 },

  // Fruity
  fruity: { x: 0.20, y: 0.25 }, cherry: { x: 0.25, y: 0.40 },
  apple: { x: 0.15, y: 0.20 }, citrus: { x: 0.20, y: 0.15 },
  orange: { x: 0.20, y: 0.20 }, lemon: { x: 0.15, y: 0.10 },
  tropical: { x: 0.15, y: 0.20 }, berry: { x: 0.20, y: 0.30 },
  plum: { x: 0.25, y: 0.45 }, 'dried fruit': { x: 0.30, y: 0.65 },
  raisin: { x: 0.30, y: 0.60 }, fig: { x: 0.30, y: 0.55 },
  apricot: { x: 0.20, y: 0.30 }, peach: { x: 0.15, y: 0.25 },
  pear: { x: 0.15, y: 0.20 }, banana: { x: 0.15, y: 0.25 },

  // Floral / Herbal
  floral: { x: 0.30, y: 0.10 }, herbal: { x: 0.40, y: 0.20 },
  grassy: { x: 0.35, y: 0.10 }, mint: { x: 0.35, y: 0.15 },
  tea: { x: 0.35, y: 0.20 },

  // Middle
  malt: { x: 0.40, y: 0.50 }, grain: { x: 0.40, y: 0.35 },
  biscuit: { x: 0.35, y: 0.40 }, bread: { x: 0.35, y: 0.45 },
  cereal: { x: 0.35, y: 0.35 }, corn: { x: 0.30, y: 0.40 },

  // Nutty
  nutty: { x: 0.45, y: 0.55 }, almond: { x: 0.40, y: 0.50 },
  walnut: { x: 0.50, y: 0.55 }, pecan: { x: 0.40, y: 0.55 },
  hazelnut: { x: 0.45, y: 0.50 },

  // Chocolate / Coffee
  chocolate: { x: 0.30, y: 0.70 }, cocoa: { x: 0.35, y: 0.65 },
  'dark chocolate': { x: 0.40, y: 0.75 }, coffee: { x: 0.50, y: 0.70 },
  espresso: { x: 0.55, y: 0.75 }, mocha: { x: 0.40, y: 0.70 },

  // Spicy
  spicy: { x: 0.60, y: 0.65 }, cinnamon: { x: 0.50, y: 0.60 },
  pepper: { x: 0.65, y: 0.60 }, clove: { x: 0.60, y: 0.65 },
  ginger: { x: 0.55, y: 0.50 }, allspice: { x: 0.55, y: 0.60 },
  'black pepper': { x: 0.65, y: 0.65 }, anise: { x: 0.55, y: 0.55 },
  nutmeg: { x: 0.50, y: 0.55 },

  // Oak / Wood
  oak: { x: 0.55, y: 0.70 }, wood: { x: 0.55, y: 0.65 },
  cedar: { x: 0.60, y: 0.60 }, pine: { x: 0.55, y: 0.45 },
  charred: { x: 0.70, y: 0.75 }, toasted: { x: 0.50, y: 0.60 },

  // Smoky / Peaty
  smoky: { x: 0.85, y: 0.70 }, smoke: { x: 0.85, y: 0.70 },
  peaty: { x: 0.90, y: 0.75 }, peat: { x: 0.90, y: 0.75 },
  campfire: { x: 0.85, y: 0.65 }, ash: { x: 0.80, y: 0.60 },
  ashy: { x: 0.80, y: 0.60 }, bonfire: { x: 0.85, y: 0.65 },
  earthy: { x: 0.65, y: 0.55 }, maritime: { x: 0.70, y: 0.45 },
  seaweed: { x: 0.75, y: 0.50 }, brine: { x: 0.70, y: 0.45 },
  iodine: { x: 0.80, y: 0.55 }, medicinal: { x: 0.85, y: 0.60 },
  tar: { x: 0.80, y: 0.80 },

  // Leather / Tobacco
  leather: { x: 0.70, y: 0.80 }, tobacco: { x: 0.75, y: 0.80 },
  cigar: { x: 0.75, y: 0.85 },

  // Body descriptors
  rich: { x: 0.50, y: 0.85 }, full: { x: 0.50, y: 0.80 },
  bold: { x: 0.55, y: 0.80 }, robust: { x: 0.55, y: 0.85 },
  complex: { x: 0.50, y: 0.70 }, deep: { x: 0.50, y: 0.80 },
  dark: { x: 0.55, y: 0.75 }, heavy: { x: 0.55, y: 0.85 },
  oily: { x: 0.50, y: 0.75 }, creamy: { x: 0.30, y: 0.55 },
  smooth: { x: 0.35, y: 0.45 }, silky: { x: 0.30, y: 0.45 },
  velvety: { x: 0.30, y: 0.55 },

  // Light descriptors
  light: { x: 0.35, y: 0.10 }, delicate: { x: 0.30, y: 0.10 },
  gentle: { x: 0.30, y: 0.15 }, subtle: { x: 0.35, y: 0.20 },
  fresh: { x: 0.30, y: 0.10 }, clean: { x: 0.35, y: 0.15 },
  crisp: { x: 0.35, y: 0.10 }, dry: { x: 0.50, y: 0.40 },
}

/**
 * Get (x, y) in [0,1] for a whiskey.
 * Prefers AI-scored flavor_x/flavor_y from the DB (0-100 → 0-1).
 * Falls back to tag-based heuristic from flavor_profile.
 */
function getPosition(w) {
  // Prefer precise AI scores when available
  if (w.flavor_x != null && w.flavor_y != null) {
    return { x: w.flavor_x / 100, y: w.flavor_y / 100 }
  }
  // Fallback: derive from flavor profile tags
  if (!w.flavor_profile) return null
  const tags = w.flavor_profile.split(',').map(t => t.trim().toLowerCase()).filter(Boolean)
  let sumX = 0, sumY = 0, count = 0
  for (const tag of tags) {
    if (FLAVOR_WEIGHTS[tag]) {
      sumX += FLAVOR_WEIGHTS[tag].x
      sumY += FLAVOR_WEIGHTS[tag].y
      count++
      continue
    }
    for (const [key, weight] of Object.entries(FLAVOR_WEIGHTS)) {
      if (tag.includes(key) || key.includes(tag)) {
        sumX += weight.x; sumY += weight.y; count++
        break
      }
    }
  }
  if (count === 0) return null
  return { x: sumX / count, y: sumY / count }
}

/**
 * Convert 0-1 position to CSS percentage inside the plot area.
 * Keeps dots away from the very edges (10% inset, matching Discover compass crosshairs).
 */
function toPercent(pos) {
  const inset = 10
  const range = 100 - inset * 2
  return {
    left: `${inset + pos.x * range}%`,
    top: `${inset + pos.y * range}%`,
  }
}

export default function FlavorMap({ whiskey, similar = [] }) {
  const [hoveredId, setHoveredId] = useState(null)
  const [categoryWhiskeys, setCategoryWhiskeys] = useState(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [compareCount, setCompareCount] = useState(10)

  // Search-to-add state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [addedWhiskeys, setAddedWhiskeys] = useState([])
  const [showSearch, setShowSearch] = useState(false)
  const searchRef = useRef(null)
  const debounceRef = useRef(null)

  // Clean up debounce timer on unmount
  useEffect(() => () => { if (debounceRef.current) clearTimeout(debounceRef.current) }, [])

  // Close search dropdown on outside click
  useEffect(() => {
    function handleClick(e) {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setSearchResults([])
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Debounced search
  const handleSearchInput = useCallback((value) => {
    setSearchQuery(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (value.trim().length < 2) {
      setSearchResults([])
      return
    }
    debounceRef.current = setTimeout(async () => {
      setSearchLoading(true)
      try {
        const res = await api.listWhiskeys({ q: value.trim(), limit: 8 })
        setSearchResults(res.items || [])
      } catch {
        setSearchResults([])
      } finally {
        setSearchLoading(false)
      }
    }, 300)
  }, [])

  function addWhiskey(w) {
    if (w.id === whiskey.id) return
    if (addedWhiskeys.some(a => a.id === w.id)) return
    setAddedWhiskeys(prev => [...prev, w])
    setSearchQuery('')
    setSearchResults([])
  }

  function removeAdded(id) {
    setAddedWhiskeys(prev => prev.filter(w => w.id !== id))
  }

  const loadCategory = useCallback(async () => {
    setLoadingMore(true)
    try {
      const res = await api.listWhiskeys({
        category: whiskey.category,
        limit: 50,
        sort_by: 'rating',
      })
      setCategoryWhiskeys(res.items || [])
    } catch {
      setCategoryWhiskeys([])
    } finally {
      setLoadingMore(false)
    }
  }, [whiskey.category])

  const points = useMemo(() => {
    const result = []
    const seen = new Set()

    // Current whiskey (always first)
    const mainPos = getPosition(whiskey)
    if (mainPos) {
      result.push({ ...mainPos, id: whiskey.id, name: whiskey.name, isCurrent: true, source: 'main' })
      seen.add(whiskey.id)
    }

    // Manually added whiskeys (green dots)
    for (const w of addedWhiskeys) {
      if (seen.has(w.id)) continue
      const pos = getPosition(w)
      if (!pos) continue
      result.push({ ...pos, id: w.id, name: w.name, category: w.category, isCurrent: false, source: 'added' })
      seen.add(w.id)
    }

    // Category / similar whiskeys (blue dots)
    const compareList = categoryWhiskeys || similar
    let added = 0
    for (const w of compareList) {
      if (seen.has(w.id)) continue
      const pos = getPosition(w)
      if (!pos) continue
      result.push({ ...pos, id: w.id, name: w.name, category: w.category, isCurrent: false, source: 'category' })
      seen.add(w.id)
      added++
      if (added >= compareCount) break
    }

    return result
  }, [whiskey, similar, categoryWhiskeys, compareCount, addedWhiskeys])

  const mainPoint = points.find(p => p.isCurrent)
  if (!mainPoint) return null

  const categoryPoints = points.filter(p => p.source === 'category')
  const addedPoints = points.filter(p => p.source === 'added')
  const allComparePoints = points.filter(p => !p.isCurrent)
  const maxCompare = categoryWhiskeys
    ? Math.min(categoryWhiskeys.filter(w => w.id !== whiskey.id && getPosition(w)).length, 50)
    : 10

  return (
    <div className="flavor-map-section">
      <h3>Flavor Map</h3>
      <p className="flavor-map-desc">
        Where this {whiskey.category || 'whiskey'} sits — add any bottle to compare
      </p>

      {/* ── Compass grid ── */}
      <div className="flavor-map-plot">
        {/* Quadrant color washes */}
        <div className="fm-quadrant fm-quadrant--tl">
          <span className="fm-quadrant-label">Sweet &amp; Light</span>
        </div>
        <div className="fm-quadrant fm-quadrant--tr">
          <span className="fm-quadrant-label">Smoky &amp; Light</span>
        </div>
        <div className="fm-quadrant fm-quadrant--bl">
          <span className="fm-quadrant-label">Sweet &amp; Bold</span>
        </div>
        <div className="fm-quadrant fm-quadrant--br">
          <span className="fm-quadrant-label">Smoky &amp; Bold</span>
        </div>

        {/* Quarter gridlines */}
        <div className="fm-grid-line fm-grid-h fm-grid-h--25" />
        <div className="fm-grid-line fm-grid-h fm-grid-h--75" />
        <div className="fm-grid-line fm-grid-v fm-grid-v--25" />
        <div className="fm-grid-line fm-grid-v fm-grid-v--75" />

        {/* Center crosshairs */}
        <span className="cm-axis cm-axis--top">Light</span>
        <span className="cm-axis cm-axis--bottom">Bold</span>
        <span className="cm-axis cm-axis--left">Sweet</span>
        <span className="cm-axis cm-axis--right">Smoky</span>
        <div className="cm-crosshair-h" />
        <div className="cm-crosshair-v" />

        {/* Connection lines from main dot to each added (green) whiskey */}
        {addedPoints.length > 0 && (
          <svg className="fm-connection" viewBox="0 0 100 100" preserveAspectRatio="none">
            {addedPoints.map(pt => {
              const m = { x: 10 + mainPoint.x * 80, y: 10 + mainPoint.y * 80 }
              const a = { x: 10 + pt.x * 80, y: 10 + pt.y * 80 }
              return <line key={pt.id} x1={m.x} y1={m.y} x2={a.x} y2={a.y} />
            })}
          </svg>
        )}

        {/* Category/similar dots (blue) */}
        {categoryPoints.map(pt => {
          const pos = toPercent(pt)
          const isHovered = hoveredId === pt.id
          return (
            <Link
              key={pt.id}
              to={`/whiskey/${pt.id}`}
              className={`fm-dot fm-dot--compare ${isHovered ? 'fm-dot--hovered' : ''}`}
              style={pos}
              onMouseEnter={() => setHoveredId(pt.id)}
              onMouseLeave={() => setHoveredId(null)}
              onTouchStart={() => setHoveredId(pt.id)}
            >
              {isHovered && (
                <span className="fm-tooltip">
                  {pt.name.length > 28 ? pt.name.slice(0, 26) + '…' : pt.name}
                  <span className="fm-tooltip-meta">{pt.category || ''}</span>
                </span>
              )}
            </Link>
          )
        })}

        {/* Manually added dots (green) */}
        {addedPoints.map(pt => {
          const pos = toPercent(pt)
          const isHovered = hoveredId === pt.id
          return (
            <Link
              key={pt.id}
              to={`/whiskey/${pt.id}`}
              className={`fm-dot fm-dot--added ${isHovered ? 'fm-dot--hovered' : ''}`}
              style={pos}
              onMouseEnter={() => setHoveredId(pt.id)}
              onMouseLeave={() => setHoveredId(null)}
              onTouchStart={() => setHoveredId(pt.id)}
            >
              {isHovered && (
                <span className="fm-tooltip">
                  {pt.name.length > 28 ? pt.name.slice(0, 26) + '…' : pt.name}
                  <span className="fm-tooltip-meta">{pt.category || ''}</span>
                </span>
              )}
            </Link>
          )
        })}

        {/* Main whiskey dot (rendered last = on top) */}
        {(() => {
          const pos = toPercent(mainPoint)
          return (
            <div className="fm-dot fm-dot--main" style={pos}>
              <span className="fm-dot-pulse" />
              <span className="fm-dot-label">
                {whiskey.name.length > 26 ? whiskey.name.slice(0, 24) + '…' : whiskey.name}
              </span>
            </div>
          )
        })()}
      </div>

      {/* ── Legend ── */}
      <div className="fm-legend">
        <span className="fm-legend-item">
          <span className="fm-legend-swatch fm-legend-swatch--main" /> This bottle
        </span>
        {categoryPoints.length > 0 && (
          <span className="fm-legend-item">
            <span className="fm-legend-swatch fm-legend-swatch--compare" /> {whiskey.category || 'Similar'}
          </span>
        )}
        {addedPoints.length > 0 && (
          <span className="fm-legend-item">
            <span className="fm-legend-swatch fm-legend-swatch--added" /> Added
          </span>
        )}
        <span className="fm-legend-count">
          {allComparePoints.length} comparison{allComparePoints.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* ── Added whiskeys chips (removable) ── */}
      {addedWhiskeys.length > 0 && (
        <div className="fm-added-list">
          {addedWhiskeys.map(w => (
            <span key={w.id} className="fm-added-chip">
              {w.name.length > 28 ? w.name.slice(0, 26) + '…' : w.name}
              <button className="fm-added-remove" onClick={() => removeAdded(w.id)}>×</button>
            </span>
          ))}
        </div>
      )}

      {/* ── Controls ── */}
      <div className="fm-controls">
        {/* Search to add any whiskey */}
        <div className="fm-search-wrapper" ref={searchRef}>
          {!showSearch ? (
            <button className="fm-load-btn" onClick={() => setShowSearch(true)}>
              + Add a whiskey to compare
            </button>
          ) : (
            <div className="fm-search">
              <input
                type="text"
                className="fm-search-input"
                placeholder="Search any whiskey…"
                value={searchQuery}
                onChange={e => handleSearchInput(e.target.value)}
                autoFocus
              />
              {searchLoading && <span className="fm-search-spinner" />}
              {searchResults.length > 0 && (
                <div className="fm-search-dropdown">
                  {searchResults
                    .filter(w => w.id !== whiskey.id && !addedWhiskeys.some(a => a.id === w.id))
                    .map(w => (
                      <button key={w.id} className="fm-search-result" onClick={() => addWhiskey(w)}>
                        <span className="fm-search-result-name">{w.name}</span>
                        <span className="fm-search-result-meta">
                          {w.category}{w.rating_avg ? ` · ★ ${w.rating_avg.toFixed(1)}` : ''}
                        </span>
                      </button>
                    ))
                  }
                  {searchResults.every(w => w.id === whiskey.id || addedWhiskeys.some(a => a.id === w.id)) && (
                    <div className="fm-search-empty">All results already on plot</div>
                  )}
                </div>
              )}
              {searchQuery.length >= 2 && !searchLoading && searchResults.length === 0 && (
                <div className="fm-search-dropdown">
                  <div className="fm-search-empty">No results</div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Load same category */}
        {!categoryWhiskeys && (
          <button
            className="fm-load-btn"
            onClick={loadCategory}
            disabled={loadingMore}
          >
            {loadingMore ? 'Loading…' : `+ All ${whiskey.category || 'similar'}`}
          </button>
        )}
        {categoryWhiskeys && maxCompare > 5 && (
          <div className="fm-slider">
            <label>
              Show: <strong>{Math.min(compareCount, maxCompare)}</strong> of {maxCompare}
            </label>
            <input
              type="range"
              min={1}
              max={maxCompare}
              value={Math.min(compareCount, maxCompare)}
              onChange={e => setCompareCount(Number(e.target.value))}
            />
          </div>
        )}
      </div>
    </div>
  )
}
