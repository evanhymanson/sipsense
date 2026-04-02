import { useState, useEffect, useLayoutEffect, useCallback, useMemo, useRef } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api, isLoggedIn } from '../api/client'
import { useToast } from '../components/Toast'
import WhiskeyCard from '../components/WhiskeyCard'
import SkeletonCard from '../components/SkeletonCard'
import CompareDrawer from '../components/CompareDrawer'
import { WHISKEY_CATEGORIES, getCategoryEmoji } from '../constants'

function Marquee({ children, reverse }) {
  const outerRef = useRef(null)
  const dragging = useRef(false)
  const didDrag = useRef(false)
  const startX = useRef(0)
  const scrollStart = useRef(0)
  const pausedRef = useRef(false)
  const rafRef = useRef(null)
  const lastTime = useRef(null)
  const [paused, setPaused] = useState(false)
  const [progress, setProgress] = useState(0)

  // Keep ref in sync with state so rAF loop reads latest value
  useEffect(() => { pausedRef.current = paused }, [paused])

  const getHalfWidth = useCallback(() => {
    const el = outerRef.current
    return el ? el.scrollWidth / 2 : 0
  }, [])

  const updateProgress = useCallback(() => {
    const el = outerRef.current
    if (!el) return
    const half = el.scrollWidth / 2
    if (half > 0) setProgress(Math.min(1, Math.max(0, el.scrollLeft / half)))
  }, [])

  // Set initial scroll position for reverse marquee
  useLayoutEffect(() => {
    if (reverse && outerRef.current) {
      outerRef.current.scrollLeft = outerRef.current.scrollWidth / 2
    }
  }, [reverse, children])

  // requestAnimationFrame-driven auto-scroll
  useEffect(() => {
    const el = outerRef.current
    if (!el) return

    const tick = (now) => {
      rafRef.current = requestAnimationFrame(tick)
      if (lastTime.current === null) { lastTime.current = now; return }
      if (pausedRef.current) { lastTime.current = now; return }

      const dt = now - lastTime.current
      lastTime.current = now
      const half = el.scrollWidth / 2
      if (half <= 0) return

      const speed = half / 30000 // pixels per ms (30s full cycle)

      if (reverse) {
        el.scrollLeft -= speed * dt
        if (el.scrollLeft <= 0) el.scrollLeft += half
      } else {
        el.scrollLeft += speed * dt
        if (el.scrollLeft >= half) el.scrollLeft -= half
      }
      updateProgress()
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [reverse, updateProgress])

  const onPointerDown = useCallback((e) => {
    dragging.current = true
    didDrag.current = false
    startX.current = e.clientX
    scrollStart.current = outerRef.current.scrollLeft
    setPaused(true)
  }, [])

  const onPointerMove = useCallback((e) => {
    if (!dragging.current) return
    const dx = e.clientX - startX.current
    if (Math.abs(dx) > 5) {
      didDrag.current = true
      const half = getHalfWidth()
      const raw = scrollStart.current - dx
      outerRef.current.scrollLeft = Math.max(0, Math.min(raw, half))
      updateProgress()
    }
  }, [getHalfWidth, updateProgress])

  const onPointerUp = useCallback(() => {
    dragging.current = false
    setPaused(false)
  }, [])

  const onClickCapture = useCallback((e) => {
    if (didDrag.current) {
      e.preventDefault()
      e.stopPropagation()
    }
  }, [])

  return (
    <div className="browse-marquee">
      <div
        className="browse-marquee-scroll"
        ref={outerRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onClickCapture={onClickCapture}
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => { if (!dragging.current) setPaused(false) }}
      >
        <div className="browse-marquee-track">
          {children}
        </div>
      </div>
      <div className="browse-marquee-bar">
        <div className="browse-marquee-bar-fill" style={{ width: `${Math.max(5, progress * 100)}%` }} />
      </div>
    </div>
  )
}

const PAGE_SIZE = 24

const CATEGORIES = WHISKEY_CATEGORIES

const REGIONS = [
  'Speyside', 'Islay', 'Highlands', 'Lowlands', 'Campbeltown', 'Islands',
  'Scotland', 'USA', 'Kentucky', 'Tennessee', 'Ireland', 'Japan', 'Canada',
  'France', 'India', 'Taiwan', 'Australia', 'England', 'Sweden', 'Norway',
]

const SORT_OPTIONS = [
  { value: 'rating',     label: 'Top Rated' },
  { value: 'price_asc',  label: 'Price ↑' },
  { value: 'price_desc', label: 'Price ↓' },
  { value: 'age',        label: 'Oldest First' },
  { value: 'name',       label: 'Name A→Z' },
  { value: 'value',      label: 'Best Value' },
]

const COMMON_FLAVORS = [
  'vanilla', 'caramel', 'honey', 'oak', 'smoky', 'peaty', 'fruity',
  'spicy', 'chocolate', 'citrus', 'floral', 'nutty', 'toffee', 'cherry',
  'cinnamon', 'maple', 'butter', 'leather', 'tobacco', 'dried fruit',
]

const EMPTY_FILTERS = { q: '', category: '', region: '', flavor: '', min_price: '', max_price: '', sort_by: 'rating' }

export default function Browse() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [whiskeys, setWhiskeys] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [error, setError] = useState(null)

  // Hero whiskey count
  const [heroCount, setHeroCount] = useState(0)

  // Special modes
  const [specialMode, setSpecialMode] = useState(null)
  const [forYouData, setForYouData] = useState([])
  const [favoritesData, setFavoritesData] = useState([])
  const [specialLoading, setSpecialLoading] = useState(false)

  // Trending sections
  const [trending, setTrending] = useState([])
  const [newArrivals, setNewArrivals] = useState([])

  // Compare mode
  const [compareMode, setCompareMode] = useState(false)
  const [compareList, setCompareList] = useState([])

  // Match scores
  const [matchScores, setMatchScores] = useState({})

  // Next Bottle recommendation
  const [nextBottle, setNextBottle] = useState(null)
  const [nextBottleLinks, setNextBottleLinks] = useState(null)
  const [nextBottleDismissed, setNextBottleDismissed] = useState(false)
  const shownBottleIds = useRef(new Set())

  // Post-purchase follow-ups
  const [followups, setFollowups] = useState([])
  const [followupsDismissed, setFollowupsDismissed] = useState(false)

  // Buy links for "For You" recommendations
  const [forYouBuyLinks, setForYouBuyLinks] = useState({})

  const addToast = useToast()

  const [filters, setFilters] = useState(() => ({
    ...EMPTY_FILTERS,
    flavor: searchParams.get('flavor') || '',
    category: searchParams.get('category') || '',
    region: searchParams.get('region') || '',
  }))

  const [searchInput, setSearchInput] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: searchInput })), 400)
    return () => clearTimeout(t)
  }, [searchInput])

  // Sync URL params -> state in a single batch update to avoid cascading re-renders.
  useEffect(() => {
    const urlFlavor = searchParams.get('flavor') || ''
    const urlCat = searchParams.get('category') || ''
    const urlRegion = searchParams.get('region') || ''
    const urlQ = searchParams.get('q') || ''
    setFilters(f => {
      const next = { ...f }
      let changed = false
      if (urlFlavor !== f.flavor) { next.flavor = urlFlavor; changed = true }
      if (urlCat !== f.category) { next.category = urlCat; changed = true }
      if (urlRegion !== f.region) { next.region = urlRegion; changed = true }
      return changed ? next : f
    })
    if (urlQ) setSearchInput(prev => urlQ !== prev ? urlQ : prev)
  }, [searchParams])

  // Load hero count + trending on mount
  useEffect(() => {
    api.getWhiskeyCount().then(r => setHeroCount(r.count)).catch(() => {})
    Promise.all([
      api.getTrending({ limit: 8 }).catch(() => []),
      api.getNewArrivals(12).catch(() => []),
    ]).then(([t, n]) => {
      const trendingIds = new Set(t.map(w => w.id))
      setTrending(t)
      setNewArrivals(n.filter(w => !trendingIds.has(w.id)).slice(0, 8))
    }).catch(() => {})
  }, [])

  // Load personalized "Your Next Bottle" + follow-ups for logged-in users
  useEffect(() => {
    if (!isLoggedIn()) return
    api.getExplainedRecommendations(1)
      .then(data => {
        if (data.length > 0) {
          shownBottleIds.current.add(data[0].whiskey.id)
          setNextBottle(data[0])
          return api.getBuyLinks(data[0].whiskey.id)
        }
      })
      .then(links => { if (links) setNextBottleLinks(links) })
      .catch(() => {})
    api.getPendingFollowups()
      .then(r => { if (r.followups?.length > 0) setFollowups(r.followups) })
      .catch(() => {})
  }, [])

  function refreshNextBottle() {
    const currentId = nextBottle?.whiskey?.id
    if (currentId) shownBottleIds.current.add(currentId)
    setNextBottle(null)
    setNextBottleLinks(null)
    api.getExplainedRecommendations(8)
      .then(data => {
        let pick = data.find(d => !shownBottleIds.current.has(d.whiskey.id))
        if (!pick) {
          shownBottleIds.current.clear()
          pick = data.find(d => d.whiskey.id !== currentId) || data[0]
        }
        if (pick) {
          shownBottleIds.current.add(pick.whiskey.id)
          setNextBottle(pick)
          return api.getBuyLinks(pick.whiskey.id).then(links => setNextBottleLinks(links))
        }
      })
      .catch(() => setNextBottleDismissed(true))
  }

  // Load main whiskey list (abort stale requests on rapid filter changes)
  useEffect(() => {
    if (specialMode) return
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    if (filters.sort_by === 'value') {
      api.getValuePicks({ category: filters.category, limit: 50 }, { signal: controller.signal })
        .then(data => { if (!controller.signal.aborted) { setWhiskeys(data); setTotalCount(data.length); setHasMore(false) } })
        .catch(e => { if (!controller.signal.aborted) setError(e.message) })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    } else {
      api.listWhiskeys({ ...filters, skip: 0, limit: PAGE_SIZE }, { signal: controller.signal })
        .then(data => {
          if (!controller.signal.aborted) {
            setWhiskeys(data.items)
            setTotalCount(data.total)
            setHasMore(data.items.length < data.total)
          }
        })
        .catch(e => { if (!controller.signal.aborted) setError(e.message) })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }
    return () => controller.abort()
  }, [filters, specialMode])

  // Fetch match scores for visible whiskeys
  useEffect(() => {
    if (!isLoggedIn() || whiskeys.length === 0) return
    const ids = whiskeys.map(w => w.id)
    api.getMatchScores(ids)
      .then(r => { if (r.scores) setMatchScores(prev => ({ ...prev, ...r.scores })) })
      .catch(() => {})
  }, [whiskeys])

  // Handle special modes
  useEffect(() => {
    if (!specialMode) return
    const controller = new AbortController()
    setSpecialLoading(true)
    setError(null)
    if (specialMode === 'foryou') {
      api.getExplainedRecommendations(12, { signal: controller.signal })
        .then(data => { if (!controller.signal.aborted) setForYouData(data) })
        .catch(() => {
          if (controller.signal.aborted) return
          api.getRecommendations(12, { signal: controller.signal })
            .then(data => { if (!controller.signal.aborted) setForYouData(data.map(r => ({ ...r, reason: null }))) })
            .catch(e => { if (!controller.signal.aborted) { setForYouData([]); setError(e.message) } })
        })
        .finally(() => { if (!controller.signal.aborted) setSpecialLoading(false) })
    } else if (specialMode === 'favorites') {
      api.getFavorites({ signal: controller.signal })
        .then(data => { if (!controller.signal.aborted) setFavoritesData(data) })
        .catch(e => { if (!controller.signal.aborted) setError(e.message) })
        .finally(() => { if (!controller.signal.aborted) setSpecialLoading(false) })
    }
    return () => controller.abort()
  }, [specialMode])

  // Fetch buy links for "For You" recommendations
  useEffect(() => {
    if (specialMode !== 'foryou' || forYouData.length === 0) return
    forYouData.forEach(({ whiskey }) => {
      api.getBuyLinks(whiskey.id)
        .then(links => setForYouBuyLinks(prev => ({ ...prev, [whiskey.id]: links })))
        .catch(() => {})
    })
  }, [specialMode, forYouData])

  function loadMore() {
    if (loadingMore) return
    setLoadingMore(true)
    const skip = whiskeys.length
    api.listWhiskeys({ ...filters, skip, limit: PAGE_SIZE })
      .then(data => {
        setWhiskeys(current => {
          const updated = [...current, ...data.items]
          setHasMore(updated.length < data.total)
          return updated
        })
      })
      .catch(e => setError(e.message))
      .finally(() => setLoadingMore(false))
  }

  function handleFilter(e) { setFilters(f => ({ ...f, [e.target.name]: e.target.value })) }

  function toggleCategory(val) {
    setSpecialMode(null)
    setFilters(f => ({ ...f, category: f.category === val ? '' : val }))
  }

  function toggleSpecialMode(mode) { setSpecialMode(prev => prev === mode ? null : mode) }

  function clearFilter(key) {
    if (key === 'q') setSearchInput('')
    setFilters(f => ({ ...f, [key]: key === 'sort_by' ? 'rating' : '' }))
    if (key === 'flavor') setSearchParams({})
  }

  function clearFlavor(f) {
    const remaining = filters.flavor.split(',').filter(x => x !== f).join(',')
    setFilters(prev => ({ ...prev, flavor: remaining }))
    if (!remaining) setSearchParams({})
  }

  function clearAll() { setSearchInput(''); setFilters(EMPTY_FILTERS); setSearchParams({}); setSpecialMode(null) }

  // Compare (max 2)
  function toggleCompare(whiskey) {
    setCompareList(prev => {
      if (prev.find(w => w.id === whiskey.id)) return prev.filter(w => w.id !== whiskey.id)
      if (prev.length >= 2) {
        addToast('Max 2 bottles in compare', 'info')
        return prev
      }
      return [...prev, whiskey]
    })
  }

  const activeFilters = Object.entries(filters).filter(([k, v]) => {
    if (k === 'sort_by') return v !== 'rating'
    if (k === 'category') return false
    return v !== ''
  })

  const filterLabel = (key, val) => {
    if (key === 'q') return `"${val}"`
    if (key === 'region') return val
    if (key === 'flavor') return `${val} flavor`
    if (key === 'min_price') return `Min $${val}`
    if (key === 'max_price') return `Max $${val}`
    if (key === 'sort_by') return SORT_OPTIONS.find(o => o.value === val)?.label || val
    return val
  }

  const [showScrollTop, setShowScrollTop] = useState(false)

  const handleScroll = useCallback(() => {
    setShowScrollTop(window.scrollY > 600)
  }, [])

  useEffect(() => {
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [handleScroll])

  const compareIds = useMemo(() => new Set(compareList.map(w => w.id)), [compareList])
  const isSpecial = specialMode != null
  const gridLoading = isSpecial ? specialLoading : loading
  const hasActiveFilters = filters.q || filters.category || filters.region || filters.flavor || filters.min_price || filters.max_price || filters.sort_by !== 'rating'

  const heroText = heroCount > 0
    ? `Explore ${heroCount.toLocaleString()}+ whiskeys by category, flavor, and region`
    : 'Explore whiskeys by category, flavor, and region'

  return (
    <div className="page">
      <Helmet>
        <title>Browse Whiskeys | SipSense</title>
        <meta name="description" content="Explore thousands of whiskeys with AI-powered recommendations. Filter by category, flavor, price, and more." />
        <link rel="canonical" href="https://sipsense.ai/" />
      </Helmet>
      {/* ── Hero ──────────────────────────────────────────── */}
      <div className="browse-hero">
        <div className="browse-hero-text">
          <h1>Browse Whiskeys</h1>
          <p>{heroText}</p>
        </div>
        <div className="browse-hero-links">
          <Link to="/lists" className="browse-hero-link">🏆 Top Lists</Link>
          <Link to="/scan" className="browse-hero-link">📷 Scan</Link>
          <button
            className={`browse-hero-link${compareMode ? ' browse-hero-link--active' : ''}`}
            onClick={() => { setCompareMode(!compareMode); if (compareMode) setCompareList([]) }}
          >
            ⚖️ {compareMode ? 'Exit Compare' : 'Compare'}
          </button>
        </div>
      </div>

      {/* ── Your Next Bottle ────────────────────────────── */}
      {isLoggedIn() && !nextBottleDismissed && nextBottle && (
        <div className="next-bottle-hero">
          <div className="next-bottle-content">
            <div className="next-bottle-img">
              {nextBottle.whiskey.image_url ? (
                <img src={nextBottle.whiskey.image_url} alt={nextBottle.whiskey.name} loading="lazy" />
              ) : (
                <span className="next-bottle-emoji">{getCategoryEmoji(nextBottle.whiskey.category)}</span>
              )}
            </div>
            <div className="next-bottle-info">
              <span className="next-bottle-label">Your Next Bottle</span>
              <Link to={`/whiskey/${nextBottle.whiskey.id}`} className="next-bottle-name">
                {nextBottle.whiskey.name}
              </Link>
              <p className="next-bottle-reason">{nextBottle.reason}</p>
              <div className="next-bottle-meta">
                {nextBottle.whiskey.price_usd && (
                  <span className="next-bottle-price">${Number(nextBottle.whiskey.price_usd).toFixed(0)}</span>
                )}
                {nextBottle.score > 0 && (
                  <span className="next-bottle-match">{Math.round(nextBottle.score * 100)}% Match</span>
                )}
              </div>
            </div>
            <div className="next-bottle-actions">
              {nextBottleLinks?.links?.[0] && (
                <a
                  href={nextBottleLinks.links[0].url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="next-bottle-buy"
                  onClick={() => {
                    api.recordAffiliateClick({
                      whiskey_id: nextBottle.whiskey.id,
                      retailer: nextBottleLinks.links[0].retailer,
                      source: 'next_bottle',
                    }).catch(() => {})
                  }}
                >
                  Buy at {nextBottleLinks.links[0].retailer}
                </a>
              )}
              <button className="next-bottle-refresh" onClick={refreshNextBottle}>Show another</button>
            </div>
          </div>
          <button className="next-bottle-dismiss" onClick={() => setNextBottleDismissed(true)} aria-label="Dismiss">&times;</button>
        </div>
      )}

      {/* ── Post-Purchase Follow-Up ──────────────────────── */}
      {isLoggedIn() && !followupsDismissed && followups.length > 0 && (
        <div className="followup-banner">
          <div className="followup-content">
            <span className="followup-label">Did you buy it? Rate it!</span>
            <div className="followup-list">
              {followups.map(w => (
                <Link key={w.id} to={`/whiskey/${w.id}#check-in`} className="followup-item">
                  {w.image_url ? (
                    <img src={w.image_url} alt={w.name} className="followup-img" loading="lazy" />
                  ) : (
                    <span className="followup-emoji">{getCategoryEmoji(w.category)}</span>
                  )}
                  <span className="followup-name">{w.name}</span>
                </Link>
              ))}
            </div>
          </div>
          <button className="followup-dismiss" onClick={() => setFollowupsDismissed(true)} aria-label="Dismiss">&times;</button>
        </div>
      )}

      {/* ── Search ────────────────────────────────────────── */}
      <div className="search-bar">
        <input className="search-input" type="search" placeholder="🔍  Search by name or distillery…"
          value={searchInput} onChange={e => setSearchInput(e.target.value)} />
      </div>

      {/* ── Category tabs + special modes ─────────────────── */}
      <div className="category-tabs">
        <button className={`cat-tab${!specialMode && filters.category === '' ? ' cat-tab--active' : ''}`}
          onClick={() => { setSpecialMode(null); toggleCategory('') }}>All</button>
        {CATEGORIES.map(c => (
          <button key={c.value} className={`cat-tab${!specialMode && filters.category === c.value ? ' cat-tab--active' : ''}`}
            onClick={() => toggleCategory(c.value)}>{c.label}</button>
        ))}
        <span className="cat-tab-divider">|</span>
        <button className={`cat-tab cat-tab--special${specialMode === 'foryou' ? ' cat-tab--active' : ''}`}
          onClick={() => toggleSpecialMode('foryou')}>For You</button>
        <button className={`cat-tab cat-tab--special${specialMode === 'favorites' ? ' cat-tab--active' : ''}`}
          onClick={() => toggleSpecialMode('favorites')}>Favorites</button>
      </div>

      {/* ── Secondary filters ─────────────────────────────── */}
      {!isSpecial && (
        <div className="filter-bar">
          <select name="region" value={filters.region} onChange={handleFilter}>
            <option value="">All Regions</option>
            {REGIONS.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <div className="filter-flavor-wrap">
            <input name="flavor" list="flavor-suggestions" placeholder="Flavor (e.g. vanilla, caramel)" value={filters.flavor} onChange={handleFilter} />
            <datalist id="flavor-suggestions">
              {COMMON_FLAVORS.map(f => <option key={f} value={f} />)}
            </datalist>
          </div>
          <input name="min_price" type="number" placeholder="Min $" value={filters.min_price} onChange={handleFilter} style={{ width: '80px' }} />
          <input name="max_price" type="number" placeholder="Max $" value={filters.max_price} onChange={handleFilter} style={{ width: '80px' }} />
          <select name="sort_by" value={filters.sort_by} onChange={handleFilter}>
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      )}

      {/* ── Active filter chips ────────────────────────────── */}
      {!isSpecial && (activeFilters.length > 0 || filters.category) && (
        <div className="active-filters">
          {filters.category && (
            <span className="filter-chip">
              {filters.category}
              <button className="chip-remove" onClick={() => toggleCategory(filters.category)}>×</button>
            </span>
          )}
          {activeFilters.map(([k, v]) =>
            k === 'flavor' && v.includes(',')
              ? v.split(',').map(f => (
                  <span key={f} className="filter-chip">{f} flavor<button className="chip-remove" onClick={() => clearFlavor(f)}>×</button></span>
                ))
              : <span key={k} className="filter-chip">{filterLabel(k, v)}<button className="chip-remove" onClick={() => clearFilter(k)}>×</button></span>
          )}
          <button className="chip-clear-all" onClick={clearAll}>Clear all</button>
        </div>
      )}

      {/* ── Trending Sections (auto-hidden when filtering) ── */}
      {!isSpecial && !hasActiveFilters && (
        <div className="browse-trending">
          <div className="browse-trending-section">
            <h3>Hot Right Now</h3>
            {trending.length > 0 ? (
              <Marquee>
                {trending.map(w => <WhiskeyCard key={w.id} whiskey={w} compareMode={compareMode} isCompared={compareIds.has(w.id)} onCompareToggle={toggleCompare} />)}
                {trending.map(w => <WhiskeyCard key={`dup-${w.id}`} whiskey={w} compareMode={compareMode} isCompared={compareIds.has(w.id)} onCompareToggle={toggleCompare} />)}
              </Marquee>
            ) : (
              <p className="status">No trending whiskeys right now — check back soon!</p>
            )}
          </div>
          <div className="browse-trending-section">
            <h3>Recently Added</h3>
            {newArrivals.length > 0 ? (
              <Marquee reverse>
                {newArrivals.map(w => <WhiskeyCard key={w.id} whiskey={w} compareMode={compareMode} isCompared={compareIds.has(w.id)} onCompareToggle={toggleCompare} />)}
                {newArrivals.map(w => <WhiskeyCard key={`dup-${w.id}`} whiskey={w} compareMode={compareMode} isCompared={compareIds.has(w.id)} onCompareToggle={toggleCompare} />)}
              </Marquee>
            ) : (
              <p className="status">No new arrivals yet.</p>
            )}
          </div>
        </div>
      )}

      {!gridLoading && !isSpecial && totalCount > 0 && (
        <p className="result-count">{totalCount.toLocaleString()} whiskeys</p>
      )}

      {error && (
        <div className="status error">
          <p>{error}</p>
          <button className="retry-btn" style={{ marginTop: '0.5rem' }} onClick={() => { setError(null); setLoading(true); window.location.reload() }}>Retry</button>
        </div>
      )}

      {/* ── Grid ──────────────────────────────────────────── */}
      {gridLoading ? (
        <div className="card-grid">{Array.from({ length: 8 }, (_, i) => <SkeletonCard key={i} />)}</div>
      ) : isSpecial ? (
        <div className="card-grid">
          {specialMode === 'foryou' && forYouData.map(({ whiskey, score, reason }) => {
            const topLink = forYouBuyLinks[whiskey.id]?.links?.[0]
            return (
              <div key={whiskey.id} className="rec-card-wrap">
                <WhiskeyCard whiskey={whiskey} score={score} compareMode={compareMode} isCompared={compareIds.has(whiskey.id)} onCompareToggle={toggleCompare} />
                {reason && <div className="rec-reason"><span className="rec-reason-icon">*</span> {reason}</div>}
                {topLink && (
                  <a
                    href={topLink.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rec-buy"
                    onClick={(e) => {
                      e.stopPropagation()
                      api.recordAffiliateClick({
                        whiskey_id: whiskey.id,
                        retailer: topLink.retailer,
                        source: 'for_you',
                      }).catch(() => {})
                    }}
                  >
                    Buy at {topLink.retailer} &rarr;
                  </a>
                )}
              </div>
            )
          })}
          {specialMode === 'favorites' && favoritesData.map(w => (
            <WhiskeyCard key={w.id} whiskey={w} compareMode={compareMode} isCompared={compareIds.has(w.id)} onCompareToggle={toggleCompare} />
          ))}
          {((specialMode === 'foryou' && forYouData.length === 0) || (specialMode === 'favorites' && favoritesData.length === 0)) && (
            <p className="status">{specialMode === 'foryou' ? 'No recommendations yet — try rating a few whiskeys first!' : 'No favorites yet — heart a whiskey on its detail page.'}</p>
          )}
        </div>
      ) : (
        <div className="card-grid">
          {whiskeys.map(w => (
            <WhiskeyCard key={w.id} whiskey={w} matchScore={matchScores[w.id]} compareMode={compareMode} isCompared={compareIds.has(w.id)} onCompareToggle={toggleCompare} />
          ))}
          {whiskeys.length === 0 && <p className="status">No whiskeys found. Try adjusting filters.</p>}
        </div>
      )}

      {!isSpecial && hasMore && !loading && whiskeys.length > 0 && (
        <div style={{ textAlign: 'center', margin: '2rem 0' }}>
          <button onClick={loadMore} disabled={loadingMore} className="btn-secondary">{loadingMore ? 'Loading…' : 'Load More'}</button>
        </div>
      )}

      {/* ── Compare Drawer ────────────────────────────────── */}
      {compareMode && compareList.length > 0 && (
        <CompareDrawer whiskeys={compareList} onRemove={id => setCompareList(prev => prev.filter(w => w.id !== id))} onClose={() => { setCompareMode(false); setCompareList([]) }} />
      )}

      {showScrollTop && (
        <button
          className="scroll-to-top"
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          aria-label="Back to top"
        >
          ↑
        </button>
      )}
    </div>
  )
}
