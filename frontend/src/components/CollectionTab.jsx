import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useToast } from './Toast'
import './CollectionTab.css'

const STATUS_LABELS = { all: 'All', sealed: 'Sealed', opened: 'Opened', finished: 'Finished' }
const STATUS_COLORS = { sealed: '#4ade80', opened: '#facc15', finished: '#94a3b8' }

export default function CollectionTab({ initialStats = null }) {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [stats, setStats] = useState(initialStats)
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

  const loadItems = useCallback(() => {
    setLoading(true)
    const statusParam = filter !== 'all' ? filter : null
    api.getCollection(statusParam)
      .then(setItems)
      .catch(() => addToast('Failed to load collection', 'error'))
      .finally(() => setLoading(false))
  }, [filter, addToast])

  const refreshStats = useCallback(() => {
    api.getCollectionStats()
      .then(setStats)
      .catch(() => {})
  }, [])

  useEffect(() => { loadItems() }, [loadItems])

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
  }, [addSearch, addToast])

  async function handleAddToCollection(whiskey) {
    try {
      await api.addToCollection({ whiskey_id: whiskey.id, status: 'sealed' })
      addToast(`Added ${whiskey.name} to collection`, 'success')
      setShowAdd(false)
      setAddSearch('')
      setAddResults([])
      loadItems(); refreshStats()
    } catch (err) {
      addToast(err.message || 'Failed to add bottle', 'error')
    }
  }

  async function handleUpdate(itemId, update) {
    try { await api.updateCollectionItem(itemId, update); loadItems(); refreshStats() }
    catch { addToast('Failed to update item', 'error') }
  }

  async function handleRemove(itemId) {
    if (confirmRemoveId !== itemId) {
      setConfirmRemoveId(itemId)
      setTimeout(() => setConfirmRemoveId(null), 3000)
      return
    }
    try { await api.removeFromCollection(itemId); loadItems(); refreshStats(); setConfirmRemoveId(null) }
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
      loadItems()
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
