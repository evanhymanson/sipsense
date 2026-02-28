import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'
import SkeletonCard from '../components/SkeletonCard'

const PAGE_SIZE = 24
const CATEGORIES = ['bourbon', 'scotch', 'irish', 'japanese', 'rye', 'canadian', 'single malt', 'blended']
const REGIONS = [
  'Speyside', 'Islay', 'Highlands', 'Lowlands', 'Campbeltown', 'Islands',
  'Scotland', 'USA', 'Kentucky', 'Tennessee', 'Ireland', 'Japan', 'Canada',
  'France', 'India', 'Taiwan', 'Australia', 'England', 'Sweden', 'Norway',
]
const SORT_OPTIONS = [
  { value: 'rating',     label: 'Top Rated' },
  { value: 'price_asc',  label: 'Price: Low \u2192 High' },
  { value: 'price_desc', label: 'Price: High \u2192 Low' },
  { value: 'age',        label: 'Age: Oldest First' },
  { value: 'name',       label: 'Name: A \u2192 Z' },
]

const EMPTY_FILTERS = { q: '', category: '', region: '', flavor: '', min_price: '', max_price: '', sort_by: 'rating' }

export default function Browse() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [whiskeys, setWhiskeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [error, setError] = useState(null)

  // Initialize filters from URL (supports ?flavor=smoky from detail page tags)
  const [filters, setFilters] = useState(() => ({
    ...EMPTY_FILTERS,
    flavor: searchParams.get('flavor') || '',
  }))

  // Local search input state — debounced into filters.q
  const [searchInput, setSearchInput] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: searchInput })), 400)
    return () => clearTimeout(t)
  }, [searchInput])

  // Sync URL flavor param → filters when navigating from detail page
  useEffect(() => {
    const urlFlavor = searchParams.get('flavor') || ''
    if (urlFlavor && urlFlavor !== filters.flavor) {
      setFilters((f) => ({ ...f, flavor: urlFlavor }))
    }
  }, [searchParams])

  // Fetch first page when filters change
  useEffect(() => {
    setLoading(true)
    setError(null)
    api.listWhiskeys({ ...filters, skip: 0, limit: PAGE_SIZE })
      .then(data => {
        setWhiskeys(data)
        setHasMore(data.length === PAGE_SIZE)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [filters])

  function loadMore() {
    setLoadingMore(true)
    api.listWhiskeys({ ...filters, skip: whiskeys.length, limit: PAGE_SIZE })
      .then(data => {
        setWhiskeys(prev => [...prev, ...data])
        setHasMore(data.length === PAGE_SIZE)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoadingMore(false))
  }

  function handleFilter(e) {
    setFilters((f) => ({ ...f, [e.target.name]: e.target.value }))
  }

  function clearFilter(key) {
    if (key === 'q') setSearchInput('')
    setFilters((f) => ({ ...f, [key]: key === 'sort_by' ? 'rating' : '' }))
    if (key === 'flavor') setSearchParams({})
  }

  function clearAll() {
    setSearchInput('')
    setFilters(EMPTY_FILTERS)
    setSearchParams({})
  }

  // Active filter chips (exclude defaults)
  const activeFilters = Object.entries(filters).filter(([k, v]) => {
    if (k === 'sort_by') return v !== 'rating'
    return v !== ''
  })

  const filterLabel = (key, val) => {
    if (key === 'q') return `Search: "${val}"`
    if (key === 'category') return `Category: ${val}`
    if (key === 'region') return `Region: ${val}`
    if (key === 'flavor') return `Flavor: ${val}`
    if (key === 'min_price') return `Min $${val}`
    if (key === 'max_price') return `Max $${val}`
    if (key === 'sort_by') return SORT_OPTIONS.find((o) => o.value === val)?.label || val
    return val
  }

  return (
    <div className="page">
      <h1>Browse Whiskeys</h1>

      <div className="search-bar">
        <input
          className="search-input"
          type="search"
          placeholder="Search by name or distillery\u2026"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
      </div>

      <div className="filter-bar">
        <select name="category" value={filters.category} onChange={handleFilter}>
          <option value="">All Categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
          ))}
        </select>

        <select name="region" value={filters.region} onChange={handleFilter}>
          <option value="">All Regions</option>
          {REGIONS.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>

        <input
          name="flavor"
          placeholder="Flavor (e.g. smoky)"
          value={filters.flavor}
          onChange={handleFilter}
        />

        <input
          name="min_price"
          type="number"
          placeholder="Min $"
          value={filters.min_price}
          onChange={handleFilter}
          style={{ width: '90px' }}
        />
        <input
          name="max_price"
          type="number"
          placeholder="Max $"
          value={filters.max_price}
          onChange={handleFilter}
          style={{ width: '90px' }}
        />

        <select name="sort_by" value={filters.sort_by} onChange={handleFilter}>
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Active filter chips */}
      {activeFilters.length > 0 && (
        <div className="active-filters">
          {activeFilters.map(([k, v]) => (
            <span key={k} className="filter-chip">
              {filterLabel(k, v)}
              <button className="chip-remove" onClick={() => clearFilter(k)}>\u00d7</button>
            </span>
          ))}
          <button className="chip-clear-all" onClick={clearAll}>Clear all</button>
        </div>
      )}

      {!loading && whiskeys.length > 0 && (
        <p className="result-count">{whiskeys.length} whiskeys shown</p>
      )}

      {error && <p className="status error">{error}</p>}

      {loading ? (
        <div className="card-grid">
          {Array.from({ length: 8 }, (_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : (
        <div className="card-grid">
          {whiskeys.map((w) => (
            <WhiskeyCard key={w.id} whiskey={w} />
          ))}
          {whiskeys.length === 0 && (
            <p className="status">No whiskeys found. Try adjusting filters.</p>
          )}
        </div>
      )}

      {hasMore && !loading && whiskeys.length > 0 && (
        <div style={{ textAlign: 'center', margin: '2rem 0' }}>
          <button onClick={loadMore} disabled={loadingMore}>
            {loadingMore ? 'Loading\u2026' : 'Load More'}
          </button>
        </div>
      )}
    </div>
  )
}
