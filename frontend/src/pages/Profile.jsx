import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import BadgeGrid from '../components/BadgeGrid'
import WhiskeyCard from '../components/WhiskeyCard'
import UserSearch from '../components/UserSearch'
import './Profile.css'
import './UserProfile.css'

const TABS = [
  { id: 'palate',     label: 'Palate',     emoji: '\u{1F445}' },
  { id: 'foryou',     label: 'For You',    emoji: '\u2728' },
  { id: 'favorites',  label: 'Favorites',  emoji: '\u2661' },
  { id: 'collection', label: 'Collection', emoji: '\u{1F37E}' },
  { id: 'journal',    label: 'Journal',    emoji: '\u{1F4DD}' },
  { id: 'badges',     label: 'Badges',     emoji: '\u{1F3C6}' },
]

const SERVING_EMOJI = { neat: '🥃', rocks: '🧊', cocktail: '🍸', highball: '🥛' }

const STATUS_LABELS = { all: 'All', sealed: 'Sealed', opened: 'Opened', finished: 'Finished' }
const STATUS_COLORS = { sealed: '#4ade80', opened: '#facc15', finished: '#94a3b8' }

// ── Shared sub-components ───────────────────────────────────────────────────

function BarRow({ label, count, max }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0
  return (
    <div className="prof-bar-row">
      <span className="prof-bar-label">{label}</span>
      <div className="prof-bar-track"><div className="prof-bar-fill" style={{ width: `${pct}%` }} /></div>
      <span className="prof-bar-count">{count}</span>
    </div>
  )
}

function FavCard({ whiskey }) {
  return (
    <Link to={`/whiskey/${whiskey.id}`} className="prof-fav-card">
      <div className="prof-fav-name">{whiskey.name}</div>
      <div className="prof-fav-dist">{whiskey.distillery}</div>
      <div className="prof-fav-meta">
        <span>{whiskey.category}</span>
        {whiskey.price_usd && <span>{whiskey.price_is_estimated ? '~' : ''}${Number(whiskey.price_usd).toFixed(2)}{whiskey.price_is_estimated ? ' Est.' : ''}</span>}
      </div>
    </Link>
  )
}

// ── Palate Tab ──────────────────────────────────────────────────────────────

function PalateTab({ palateData }) {
  const [aiSummary, setAiSummary] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)

  if (!palateData) return <p className="prof-empty">Rate some whiskeys to start building your taste portrait.</p>

  const { narrative, stats, top_categories = [], top_flavors = [], recent_ratings = [], favorites = [] } = palateData
  const maxCat = top_categories[0]?.count || 1
  const maxFlavor = top_flavors[0]?.count || 1

  async function loadAiSummary() {
    setAiLoading(true)
    try { setAiSummary((await api.getAiPalateSummary()).narrative) }
    catch { setAiSummary(null) }
    finally { setAiLoading(false) }
  }

  if (stats.total_rated === 0 && stats.total_favorites === 0) {
    return (
      <div className="prof-empty-state">
        <div className="prof-empty-icon">🥃</div>
        <h2>Your palate profile is empty</h2>
        <p>Rate some whiskeys in Browse to start building your taste portrait.</p>
      </div>
    )
  }

  return (
    <div className="prof-palate">
      <div className="prof-narrative">
        <p>{aiSummary || narrative}</p>
        {!aiSummary && !aiLoading && (
          <button className="prof-ai-btn" onClick={loadAiSummary}>Generate AI Portrait</button>
        )}
        {aiLoading && <p className="prof-ai-loading">Writing your taste portrait...</p>}
      </div>

      {top_categories.length > 0 && (
        <div className="prof-section">
          <h3>Styles You Reach For</h3>
          <div className="prof-bars">{top_categories.map(c => <BarRow key={c.name} label={c.name} count={c.count} max={maxCat} />)}</div>
        </div>
      )}

      {top_flavors.length > 0 && (
        <div className="prof-section">
          <h3>Flavor Fingerprint</h3>
          <div className="prof-flavor-cloud">
            {top_flavors.map((f, i) => (
              <span key={f.name} className="prof-cloud-tag" style={{ fontSize: `${1.1 - i * 0.07}rem`, opacity: 1 - i * 0.06 }}>
                {f.name}
              </span>
            ))}
          </div>
          <div className="prof-bars">{top_flavors.slice(0, 6).map(f => <BarRow key={f.name} label={f.name} count={f.count} max={maxFlavor} />)}</div>
        </div>
      )}

      {recent_ratings.length > 0 && (
        <div className="prof-section">
          <h3>Recent Ratings</h3>
          <div className="prof-ratings">
            {recent_ratings.map((r) => (
              <div key={r.whiskey.id} className="prof-rating-row">
                <div className="prof-rating-info">
                  <span className="prof-rating-name">{r.whiskey.name}</span>
                  <span className="prof-rating-dist">{r.whiskey.distillery} · {r.whiskey.category}</span>
                </div>
                <div className="prof-rating-right">
                  <span className="prof-rating-score">{r.score.toFixed(1)}</span>
                  <span className="prof-rating-stars">{'★'.repeat(Math.min(5, Math.max(0, Math.round(r.score || 0))))}{'☆'.repeat(Math.max(0, 5 - Math.min(5, Math.round(r.score || 0))))}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {favorites.length > 0 && (
        <div className="prof-section">
          <h3>Saved Favorites</h3>
          <div className="prof-fav-grid">{favorites.map(w => <FavCard key={w.id} whiskey={w} />)}</div>
        </div>
      )}
    </div>
  )
}

// ── For You Tab ─────────────────────────────────────────────────────────────

function ForYouTab() {
  const [recs, setRecs] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.getExplainedRecommendations(12)
      .then(setRecs)
      .catch(() =>
        api.getRecommendations(12)
          .then(data => setRecs(data.map(r => ({ ...r, reason: null }))))
          .catch(() => setRecs([]))
      )
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="prof-loading">Finding your next bottles...</p>

  if (recs.length === 0) {
    return (
      <div className="prof-empty-state">
        <div className="prof-empty-icon">✦</div>
        <h2>No recommendations yet</h2>
        <p>Rate a few whiskeys and we'll suggest bottles tailored to your taste.</p>
        <button className="prof-cta-btn" onClick={() => navigate('/')}>Browse Whiskeys</button>
      </div>
    )
  }

  return (
    <div className="prof-foryou">
      <p className="prof-foryou-subtitle">Picked for your palate</p>
      <div className="prof-foryou-grid">
        {recs.map(({ whiskey, score, reason }) => (
          <div key={whiskey.id} className="prof-foryou-item">
            <WhiskeyCard whiskey={whiskey} score={score} />
            {reason && <div className="prof-foryou-reason">{reason}</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Favorites Tab ───────────────────────────────────────────────────────────

function FavoritesTab() {
  const [favs, setFavs] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.getFavorites()
      .then(setFavs)
      .catch(() => setFavs([]))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="prof-loading">Loading favorites...</p>

  if (favs.length === 0) {
    return (
      <div className="prof-empty-state">
        <div className="prof-empty-icon">♡</div>
        <h2>No favorites yet</h2>
        <p>Bottles you're interested in — heart any whiskey to save it here.</p>
        <button className="prof-cta-btn" onClick={() => navigate('/')}>Browse Whiskeys</button>
      </div>
    )
  }

  return (
    <div className="prof-favorites">
      <p className="prof-foryou-subtitle">{favs.length} bottle{favs.length !== 1 ? 's' : ''} on your wishlist</p>
      <div className="prof-foryou-grid">
        {favs.map(w => (
          <WhiskeyCard key={w.id} whiskey={w} />
        ))}
      </div>
    </div>
  )
}

// ── Collection Tab ──────────────────────────────────────────────────────────

function CollectionTab() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [stats, setStats] = useState(null)
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [searchText, setSearchText] = useState('')

  const addToast = useToast()
  const [confirmRemoveId, setConfirmRemoveId] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editNotes, setEditNotes] = useState('')
  const [editPrice, setEditPrice] = useState('')

  // ── Add bottle state ──
  const [showAdd, setShowAdd] = useState(false)
  const [addSearch, setAddSearch] = useState('')
  const [addResults, setAddResults] = useState([])
  const [addSearchLoading, setAddSearchLoading] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    const statusParam = filter !== 'all' ? filter : null
    Promise.all([api.getCollection(statusParam), api.getCollectionStats()])
      .then(([col, st]) => { setItems(col); setStats(st) })
      .catch(() => addToast('Failed to load collection', 'error'))
      .finally(() => setLoading(false))
  }, [filter, addToast])

  useEffect(() => { load() }, [load])

  // ── Debounced search for adding bottles ──
  useEffect(() => {
    if (!addSearch.trim()) { setAddResults([]); return }
    const timeout = setTimeout(() => {
      setAddSearchLoading(true)
      api.listWhiskeys({ q: addSearch.trim(), limit: 6 })
        .then(data => setAddResults(Array.isArray(data) ? data : data.items || []))
        .catch(() => { setAddResults([]); addToast('Search failed', 'error') })
        .finally(() => setAddSearchLoading(false))
    }, 400)
    return () => clearTimeout(timeout)
  }, [addSearch])

  async function handleAddToCollection(whiskey) {
    try {
      await api.addToCollection({ whiskey_id: whiskey.id, status: 'sealed' })
      addToast(`Added ${whiskey.name} to collection`, 'success')
      setShowAdd(false)
      setAddSearch('')
      setAddResults([])
      load()
    } catch (err) {
      addToast(err.message || 'Failed to add bottle', 'error')
    }
  }

  async function handleUpdate(itemId, update) {
    try { await api.updateCollectionItem(itemId, update); load() }
    catch { addToast('Failed to update item', 'error') }
  }

  async function handleRemove(itemId) {
    if (confirmRemoveId !== itemId) {
      setConfirmRemoveId(itemId)
      setTimeout(() => setConfirmRemoveId(null), 3000)
      return
    }
    try { await api.removeFromCollection(itemId); load(); setConfirmRemoveId(null) }
    catch { addToast('Failed to remove item', 'error') }
  }

  function startEditing(item) {
    setEditingId(item.id)
    setEditNotes(item.personal_notes || '')
    setEditPrice(item.purchase_price ? String(item.purchase_price) : '')
  }

  async function saveEdit(itemId) {
    const update = { personal_notes: editNotes.trim() || null }
    const price = parseFloat(editPrice)
    if (!isNaN(price) && price > 0) update.purchase_price = price
    else if (!editPrice.trim()) update.purchase_price = null
    try {
      await api.updateCollectionItem(itemId, update)
      setEditingId(null)
      load()
    } catch { addToast('Failed to save changes', 'error') }
  }

  // ── Client-side search filter ──
  const filtered = items.filter(item => {
    if (!searchText.trim()) return true
    const q = searchText.toLowerCase()
    const w = item.whiskey
    if (!w) return false
    return (w.name || '').toLowerCase().includes(q) ||
           (w.distillery || '').toLowerCase().includes(q) ||
           (w.category || '').toLowerCase().includes(q)
  })

  return (
    <div className="prof-collection">
      {/* ── Top bar: add + search ── */}
      <div className="prof-shelf-top">
        <button className="prof-shelf-add-btn" onClick={() => setShowAdd(!showAdd)}>
          {showAdd ? 'Cancel' : '+ Add Bottle'}
        </button>
        {stats && stats.total_spent > 0 && (
          <span className="prof-shelf-spent">${stats.total_spent} invested</span>
        )}
      </div>

      {/* ── Add bottle panel ── */}
      {showAdd && (
        <div className="prof-shelf-add-panel">
          <input
            type="search"
            className="prof-shelf-add-search"
            placeholder="Search for a whiskey to add..."
            value={addSearch}
            onChange={e => setAddSearch(e.target.value)}
            autoFocus
          />
          {addSearchLoading && <p className="prof-shelf-add-hint">Searching...</p>}
          {!addSearchLoading && addSearch.trim() && addResults.length === 0 && (
            <p className="prof-shelf-add-hint">No whiskeys found.</p>
          )}
          {addResults.length > 0 && (
            <div className="prof-shelf-add-results">
              {addResults.map(w => (
                <button key={w.id} className="prof-shelf-add-result" onClick={() => handleAddToCollection(w)}>
                  <span className="prof-shelf-add-result-name">{w.name}</span>
                  <span className="prof-shelf-add-result-meta">{w.distillery}{w.category ? ` · ${w.category}` : ''}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Stats as clickable filters ── */}
      {stats && stats.total > 0 && (
        <div className="prof-shelf-stat-filters">
          <button
            className={`prof-shelf-sf${filter === 'all' ? ' prof-shelf-sf--active' : ''}`}
            onClick={() => setFilter('all')}
          >
            <span className="prof-shelf-sf-val">{stats.total}</span>
            <span className="prof-shelf-sf-label">All</span>
          </button>
          {['sealed', 'opened', 'finished'].map(status => (
            <button
              key={status}
              className={`prof-shelf-sf${filter === status ? ' prof-shelf-sf--active' : ''}`}
              onClick={() => setFilter(filter === status ? 'all' : status)}
            >
              <span className="prof-shelf-sf-val" style={{ color: filter === status ? STATUS_COLORS[status] : undefined }}>
                {stats[status]}
              </span>
              <span className="prof-shelf-sf-label">{STATUS_LABELS[status]}</span>
            </button>
          ))}
        </div>
      )}

      {/* ── Search within collection ── */}
      {items.length > 3 && (
        <input
          type="search"
          className="prof-shelf-search"
          placeholder="Search your collection..."
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
        />
      )}

      {loading && <p className="prof-loading">Loading...</p>}

      {!loading && items.length === 0 && !showAdd && (
        <div className="prof-empty-state">
          <div className="prof-empty-icon">🍾</div>
          <h2>Your shelf is empty</h2>
          <p>Track bottles you own — sealed, opened, or finished.</p>
          <button className="prof-cta-btn" onClick={() => setShowAdd(true)}>Add Your First Bottle</button>
        </div>
      )}

      {!loading && items.length > 0 && searchText.trim() && filtered.length === 0 && (
        <p className="prof-empty" style={{ textAlign: 'center', padding: '1.5rem 0' }}>No matching bottles.</p>
      )}

      <div className="prof-shelf-grid">
        {filtered.map(item => {
          const w = item.whiskey
          if (!w) return null
          const isEditing = editingId === item.id
          return (
            <div key={item.id} className="prof-shelf-card">
              <div className="prof-shelf-card-header" onClick={() => navigate(`/whiskey/${w.id}`)}>
                <div className="prof-shelf-card-name">{w.name}</div>
                <div className="prof-shelf-card-dist">{w.distillery}</div>
              </div>
              <div className="prof-shelf-card-meta">
                <span className="prof-shelf-badge">{w.category}</span>
                {w.price_usd && (
                  <span className={`prof-shelf-badge${w.price_is_estimated ? ' prof-shelf-badge--estimated' : ''}`}>
                    {w.price_is_estimated ? '~' : ''}${Number(w.price_usd).toFixed(2)}{w.price_is_estimated ? ' Est.' : ''}
                  </span>
                )}
                {!isEditing && item.purchase_price && (
                  <span className="prof-shelf-badge prof-shelf-badge--paid">Paid ${item.purchase_price}</span>
                )}
              </div>

              {/* ── Status segment buttons ── */}
              <div className="prof-shelf-status-row">
                <div className="prof-shelf-segments">
                  {['sealed', 'opened', 'finished'].map(s => (
                    <button
                      key={s}
                      className={`prof-shelf-seg${item.status === s ? ' prof-shelf-seg--active' : ''}`}
                      style={item.status === s ? { borderColor: STATUS_COLORS[s], color: STATUS_COLORS[s] } : undefined}
                      onClick={() => handleUpdate(item.id, { status: s })}
                    >
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </button>
                  ))}
                </div>
                <div className="prof-shelf-actions">
                  <button
                    className="prof-shelf-edit"
                    onClick={() => isEditing ? setEditingId(null) : startEditing(item)}
                    title={isEditing ? 'Cancel edit' : 'Edit notes & price'}
                  >
                    {isEditing ? '✕' : '✎'}
                  </button>
                  <button
                    className="prof-shelf-remove"
                    onClick={() => handleRemove(item.id)}
                    title={confirmRemoveId === item.id ? 'Tap again to confirm' : 'Remove'}
                  >
                    {confirmRemoveId === item.id ? 'Remove?' : '🗑'}
                  </button>
                </div>
              </div>

              {/* ── Inline edit panel ── */}
              {isEditing && (
                <div className="prof-shelf-edit-panel">
                  <div className="prof-shelf-edit-row">
                    <label>Paid</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="$0.00"
                      value={editPrice}
                      onChange={e => setEditPrice(e.target.value)}
                      className="prof-shelf-edit-input prof-shelf-edit-price"
                    />
                  </div>
                  <textarea
                    className="prof-shelf-edit-notes"
                    placeholder="Personal notes..."
                    value={editNotes}
                    onChange={e => setEditNotes(e.target.value)}
                    rows={2}
                  />
                  <button className="prof-shelf-edit-save" onClick={() => saveEdit(item.id)}>Save</button>
                </div>
              )}

              {/* ── Read-only notes (when not editing) ── */}
              {!isEditing && item.personal_notes && (
                <div className="prof-shelf-notes">{item.personal_notes}</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Journal Tab ─────────────────────────────────────────────────────────────

function groupByMonth(entries) {
  const groups = {}
  for (const entry of entries) {
    const d = new Date(entry.created_at)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const label = d.toLocaleDateString('en-US', { year: 'numeric', month: 'long' })
    if (!groups[key]) groups[key] = { label, entries: [] }
    groups[key].entries.push(entry)
  }
  return Object.values(groups)
}

function relativeDate(dateStr) {
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now - d
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const SCORE_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'top', label: '4-5\u2605' },
  { key: 'mid', label: '3\u2605' },
  { key: 'low', label: '1-2\u2605' },
]

function JournalTab() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const addToast = useToast()

  // ── Log a Tasting state ────────────────────────────
  const [showLog, setShowLog] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [selectedWhiskey, setSelectedWhiskey] = useState(null)
  const [logScore, setLogScore] = useState(0)
  const [logServing, setLogServing] = useState(null)
  const [logNotes, setLogNotes] = useState('')
  const [logSubmitting, setLogSubmitting] = useState(false)

  // ── Filter state ───────────────────────────────────
  const [filterText, setFilterText] = useState('')
  const [scoreFilter, setScoreFilter] = useState('all')

  function loadJournal() {
    setLoading(true)
    api.getJournal().then(data => setEntries(data.entries || []))
      .catch(e => { setError(e.message || 'Failed to load journal'); addToast('Failed to load journal', 'error') })
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadJournal() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Debounced whiskey search ───────────────────────
  useEffect(() => {
    if (!searchText.trim()) { setSearchResults([]); return }
    const timeout = setTimeout(() => {
      setSearchLoading(true)
      api.listWhiskeys({ q: searchText.trim(), limit: 6 })
        .then(data => setSearchResults(Array.isArray(data) ? data : data.items || []))
        .catch(() => setSearchResults([]))
        .finally(() => setSearchLoading(false))
    }, 400)
    return () => clearTimeout(timeout)
  }, [searchText])

  // ── Submit check-in ────────────────────────────────
  async function handleLogSubmit() {
    if (!selectedWhiskey || logScore === 0) return
    setLogSubmitting(true)
    try {
      const body = { score: logScore }
      if (logNotes.trim()) body.notes = logNotes.trim()
      if (logServing) body.serving_style = logServing
      await api.rateWhiskey(selectedWhiskey.id, body)
      addToast('Check-in saved!', 'success')
      // Reset log state
      setShowLog(false)
      setSearchText('')
      setSearchResults([])
      setSelectedWhiskey(null)
      setLogScore(0)
      setLogServing(null)
      setLogNotes('')
      // Refresh journal
      loadJournal()
    } catch (err) {
      addToast(err.message || 'Failed to save check-in', 'error')
    } finally {
      setLogSubmitting(false)
    }
  }

  // ── Filter entries client-side ─────────────────────
  const filteredEntries = entries.filter(entry => {
    // Score filter
    if (scoreFilter === 'top' && entry.score < 4) return false
    if (scoreFilter === 'mid' && (entry.score < 3 || entry.score >= 4)) return false
    if (scoreFilter === 'low' && entry.score >= 3) return false
    // Text filter
    if (filterText.trim()) {
      const q = filterText.toLowerCase()
      const name = (entry.whiskey?.name || '').toLowerCase()
      const dist = (entry.whiskey?.distillery || '').toLowerCase()
      const notes = (entry.notes || '').toLowerCase()
      if (!name.includes(q) && !dist.includes(q) && !notes.includes(q)) return false
    }
    return true
  })
  const hasFilters = scoreFilter !== 'all' || filterText.trim()
  const months = useMemo(() => groupByMonth(filteredEntries), [filteredEntries])

  if (loading) return <p className="prof-loading">Loading journal...</p>

  if (error) return (
    <div className="prof-empty-state">
      <p className="status error">{error}</p>
      <button className="retry-btn" style={{ marginTop: '0.5rem' }} onClick={() => window.location.reload()}>Retry</button>
    </div>
  )

  return (
    <div className="prof-journal">
      {/* ── Top bar ─────────────────────────────────── */}
      <div className="prof-journal-top">
        <p className="prof-journal-count">{entries.length} tasting{entries.length !== 1 ? 's' : ''} recorded</p>
        <button className="prof-journal-log-btn" onClick={() => setShowLog(!showLog)}>
          {showLog ? 'Cancel' : '+ Log a Tasting'}
        </button>
      </div>

      {/* ── Inline log panel ────────────────────────── */}
      {showLog && (
        <div className="jlog-panel">
          {!selectedWhiskey ? (
            <>
              <input
                type="search"
                className="jlog-search"
                placeholder="Search for a whiskey..."
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                autoFocus
              />
              {searchLoading && <p className="jlog-hint">Searching...</p>}
              {!searchLoading && searchText.trim() && searchResults.length === 0 && (
                <p className="jlog-hint">No whiskeys found. Try a different name.</p>
              )}
              {searchResults.length > 0 && (
                <div className="jlog-results">
                  {searchResults.map(w => (
                    <button key={w.id} className="jlog-result" onClick={() => setSelectedWhiskey(w)}>
                      <span className="jlog-result-name">{w.name}</span>
                      <span className="jlog-result-meta">{w.distillery}{w.category ? ` \u00b7 ${w.category}` : ''}</span>
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="jlog-form">
              <div className="jlog-selected">
                <div>
                  <span className="jlog-selected-name">{selectedWhiskey.name}</span>
                  <span className="jlog-selected-meta">{selectedWhiskey.distillery}</span>
                </div>
                <button className="jlog-change" onClick={() => { setSelectedWhiskey(null); setLogScore(0); setLogServing(null); setLogNotes('') }}>Change</button>
              </div>
              <div className="jlog-stars" role="radiogroup" aria-label="Rating">
                {[1, 2, 3, 4, 5].map(n => (
                  <button key={n} type="button" className={`jlog-star ${n <= logScore ? 'jlog-star--filled' : ''}`} onClick={() => setLogScore(n)}>★</button>
                ))}
              </div>
              <div className="jlog-servings">
                {Object.entries(SERVING_EMOJI).map(([style, emoji]) => (
                  <button key={style} type="button" className={`jlog-serving ${logServing === style ? 'jlog-serving--active' : ''}`} onClick={() => setLogServing(logServing === style ? null : style)}>
                    {emoji} {style}
                  </button>
                ))}
              </div>
              <textarea className="jlog-notes" placeholder="Tasting notes (optional)" value={logNotes} onChange={e => setLogNotes(e.target.value)} rows={2} />
              <button className="jlog-submit" onClick={handleLogSubmit} disabled={logScore === 0 || logSubmitting}>
                {logSubmitting ? 'Saving...' : 'Check In'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Filters (only when there are entries) ──── */}
      {entries.length > 0 && (
        <div className="jfilter-bar">
          <input
            type="search"
            className="jfilter-search"
            placeholder="Search your tastings..."
            value={filterText}
            onChange={e => setFilterText(e.target.value)}
          />
          <div className="jfilter-scores">
            {SCORE_FILTERS.map(f => (
              <button key={f.key} className={`jfilter-pill${scoreFilter === f.key ? ' jfilter-pill--active' : ''}`} onClick={() => setScoreFilter(f.key)}>
                {f.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Empty state ─────────────────────────────── */}
      {entries.length === 0 && !showLog && (
        <div className="prof-empty-state">
          <div className="prof-empty-icon">📝</div>
          <h2>No tastings yet</h2>
          <p>Tap "+ Log a Tasting" above to record your first check-in.</p>
          <button className="prof-cta-btn" onClick={() => setShowLog(true)}>Log a Tasting</button>
        </div>
      )}

      {/* ── No filter results ───────────────────────── */}
      {entries.length > 0 && hasFilters && filteredEntries.length === 0 && (
        <p className="prof-empty" style={{ textAlign: 'center', padding: '1.5rem 0' }}>No matching entries.</p>
      )}

      {/* ── Timeline ────────────────────────────────── */}
      {months.map(group => (
        <div key={group.label} className="prof-journal-month">
          <h3>{group.label}</h3>
          <div className="prof-journal-entries">
            {group.entries.map(entry => (
              <div key={entry.id} className="prof-journal-card">
                {entry.image_url && (
                  <img src={entry.image_url} alt={`Tasting photo of ${entry.whiskey?.name || 'whiskey'}`} className="prof-journal-card-photo" />
                )}
                <div className="prof-journal-card-body">
                  <div className="prof-journal-card-top">
                    <div className="prof-journal-card-info">
                      <Link to={`/whiskey/${entry.whiskey?.id}`} className="prof-journal-card-name">{entry.whiskey?.name}</Link>
                      <span className="prof-journal-card-dist">{entry.whiskey?.distillery}{entry.whiskey?.category ? ` \u00b7 ${entry.whiskey.category}` : ''}</span>
                    </div>
                    <div className="prof-journal-card-score">
                      <span className="prof-journal-card-num">{entry.score}</span>
                      <span className="prof-journal-card-stars">{'★'.repeat(Math.min(5, Math.max(0, Math.round(entry.score || 0))))}{'☆'.repeat(Math.max(0, 5 - Math.min(5, Math.round(entry.score || 0))))}</span>
                    </div>
                  </div>
                  {entry.notes && <p className="prof-journal-card-notes">{entry.notes}</p>}
                  <div className="prof-journal-card-tags">
                    {entry.serving_style && <span className="prof-journal-tag">{SERVING_EMOJI[entry.serving_style] || ''} {entry.serving_style}</span>}
                    {entry.location_note && <span className="prof-journal-tag">{entry.location_note}</span>}
                    <span className="prof-journal-card-date">{relativeDate(entry.created_at)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main Profile Page ───────────────────────────────────────────────────────

export default function Profile() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tabFromUrl = searchParams.get('tab')
  const [activeTab, setActiveTabRaw] = useState(
    TABS.some(t => t.id === tabFromUrl) ? tabFromUrl : 'palate'
  )
  const setActiveTab = useCallback((id) => {
    setActiveTabRaw(id)
    setSearchParams({ tab: id }, { replace: true })
  }, [setSearchParams])
  const [personality, setPersonality] = useState(null)
  const [palateData, setPalateData] = useState(null)
  const [tabCounts, setTabCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const [followerCount, setFollowerCount] = useState(0)
  const [followingCount, setFollowingCount] = useState(0)
  const [listModal, setListModal] = useState(null)
  const [listUsers, setListUsers] = useState([])
  const [listLoading, setListLoading] = useState(false)

  useEffect(() => {
    Promise.all([
      api.getPersonality().catch(() => null),
      api.getPalate().catch(() => null),
      api.getCollectionStats().catch(() => null),
      api.getJournal().catch(() => null),
      api.getMe().catch(() => null),
    ]).then(([pers, pal, colStats, journal, me]) => {
      setPersonality(pers)
      setPalateData(pal)
      setTabCounts({
        favorites: pal?.stats?.total_favorites ?? 0,
        collection: colStats?.total ?? 0,
        journal: Array.isArray(journal?.entries) ? journal.entries.length : (journal?.total ?? 0),
        badges: pal?.badges?.length ?? 0,
      })
      if (me?.username) {
        api.getUserProfile(me.username)
          .then(p => { setFollowerCount(p.follower_count || 0); setFollowingCount(p.following_count || 0) })
          .catch(() => {})
      }
    }).finally(() => setLoading(false))
  }, [])

  async function openList(type) {
    setListModal(type)
    setListLoading(true)
    try {
      const me = await api.getMe()
      const users = type === 'followers'
        ? await api.getFollowers(me.username)
        : await api.getFollowing(me.username)
      setListUsers(users)
    } catch { setListUsers([]) }
    finally { setListLoading(false) }
  }

  if (loading) {
    return (
      <div className="profile-page">
        <div className="prof-loading-state">
          <span className="prof-loading-icon">🥃</span>
          <p>Loading your profile...</p>
        </div>
      </div>
    )
  }

  const stats = palateData?.stats
  const isNewcomer = personality?.type === 'curious_newcomer'

  return (
    <div className="profile-page">
      {/* ── Hero: Personality Card ───────────────────────────── */}
      <div className="prof-hero">
        {personality && (
          <div className="prof-personality">
            <span className="prof-personality-emoji">{personality.emoji}</span>
            <div className="prof-personality-info">
              <h1>{personality.title}</h1>
              <p className="prof-personality-tagline">{personality.tagline}</p>
              {personality.spirit_bottle && (
                <span className="prof-spirit">Spirit bottle: {personality.spirit_bottle}</span>
              )}
            </div>
          </div>
        )}

        {!isNewcomer && personality?.top_flavors?.length > 0 && (
          <div className="prof-dna">
            <div className="prof-dna-section">
              <span className="prof-dna-label">Flavor DNA</span>
              <div className="prof-dna-tags">
                {personality.top_flavors.map(f => <span key={f} className="prof-dna-tag">{f}</span>)}
              </div>
            </div>
            {personality.top_categories?.length > 0 && (
              <div className="prof-dna-section">
                <span className="prof-dna-label">Go-To Styles</span>
                <div className="prof-dna-tags">
                  {personality.top_categories.map(c => <span key={c} className="prof-dna-tag prof-dna-tag--cat">{c}</span>)}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Stats row */}
        {stats && (
          <div className="prof-stats">
            <div className="prof-stat"><span className="prof-stat-val">{stats.total_rated}</span><span>Rated</span></div>
            <div className="prof-stat"><span className="prof-stat-val">{stats.total_favorites}</span><span>Favorites</span></div>
            <div className="prof-stat prof-stat--clickable" onClick={() => openList('followers')}>
              <span className="prof-stat-val">{followerCount}</span><span>Followers</span>
            </div>
            <div className="prof-stat prof-stat--clickable" onClick={() => openList('following')}>
              <span className="prof-stat-val">{followingCount}</span><span>Following</span>
            </div>
          </div>
        )}

        <div className="prof-find-people">
          <UserSearch />
        </div>

        {isNewcomer && (
          <div className="prof-cta">
            <p>Rate a few whiskeys and your personality will emerge!</p>
            <button onClick={() => navigate('/discover')}>Start Exploring</button>
          </div>
        )}
      </div>

      {/* ── Tabs ─────────────────────────────────────────────── */}
      <div className="prof-tabs-wrapper">
        <div className="prof-tabs" role="tablist" aria-label="Profile sections">
          {TABS.map(tab => {
            const count = tabCounts[tab.id]
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={activeTab === tab.id}
                className={`prof-tab${activeTab === tab.id ? ' prof-tab--active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <span className="prof-tab-emoji">{tab.emoji}</span>
                {tab.label}
                {count > 0 && <span className="prof-tab-count">{count}</span>}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Tab Content ──────────────────────────────────────── */}
      <div className="prof-tab-content" role="tabpanel">
        {activeTab === 'palate' && <PalateTab palateData={palateData} />}
        {activeTab === 'foryou' && <ForYouTab />}
        {activeTab === 'favorites' && <FavoritesTab />}
        {activeTab === 'collection' && <CollectionTab />}
        {activeTab === 'journal' && <JournalTab />}
        {activeTab === 'badges' && (
          palateData?.badges?.length > 0
            ? <BadgeGrid badges={palateData.badges} showDate />
            : <div className="prof-empty-state">
                <div className="prof-empty-icon">🏆</div>
                <h2>No badges yet</h2>
                <p>Rate whiskeys and explore to earn achievements!</p>
                <button className="prof-cta-btn" onClick={() => navigate('/')}>Browse Whiskeys</button>
              </div>
        )}
      </div>

      {/* ── Followers / Following Modal ──────────────────────── */}
      {listModal && (
        <div className="follow-modal-overlay" onClick={() => setListModal(null)}>
          <div className="follow-modal" onClick={e => e.stopPropagation()}>
            <div className="follow-modal-header">
              <h3>{listModal === 'followers' ? 'Followers' : 'Following'}</h3>
              <button className="follow-modal-close" onClick={() => setListModal(null)}>✕</button>
            </div>
            <div className="follow-modal-body">
              {listLoading ? (
                <p className="status">Loading...</p>
              ) : listUsers.length === 0 ? (
                <p className="status">{listModal === 'followers' ? 'No followers yet' : 'Not following anyone yet'}</p>
              ) : (
                listUsers.map(u => (
                  <div key={u.username} className="follow-modal-user">
                    <Link to={`/user/${u.username}`} className="follow-modal-name" onClick={() => setListModal(null)}>
                      {u.username}
                    </Link>
                    <span className="follow-modal-meta">{u.total_checkins} check-ins</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
