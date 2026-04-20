import { useState, useEffect, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useToast } from './Toast'
import './JournalTab.css'

const SERVING_EMOJI = { neat: '🥃', rocks: '🧊', cocktail: '🍸', highball: '🥛' }

const SCORE_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'top', label: '4-5\u2605' },
  { key: 'mid', label: '3\u2605' },
  { key: 'low', label: '1-2\u2605' },
]

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

export default function JournalTab({ initialEntries = null }) {
  const [entries, setEntries] = useState(initialEntries || [])
  const [loading, setLoading] = useState(!initialEntries)
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

  const loadJournal = useCallback(() => {
    setLoading(true)
    api.getJournal().then(data => setEntries(data.entries || []))
      .catch(e => { setError(e.message || 'Failed to load journal'); addToast('Failed to load journal', 'error') })
      .finally(() => setLoading(false))
  }, [addToast])

  useEffect(() => { if (!initialEntries) loadJournal() }, []) // eslint-disable-line react-hooks/exhaustive-deps

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
                  <img src={entry.image_url} alt={`Tasting photo of ${entry.whiskey?.name || 'whiskey'}`} className="prof-journal-card-photo" loading="lazy" />
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
