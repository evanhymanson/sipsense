import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import './Collection.css'

const STATUS_LABELS = {
  all: 'All Bottles',
  sealed: 'Sealed',
  opened: 'Opened',
  finished: 'Finished',
}

function BottleCard({ item, onUpdate, onRemove }) {
  const navigate = useNavigate()
  const w = item.whiskey
  if (!w) return null

  const statusColors = { sealed: '#4ade80', opened: '#facc15', finished: '#94a3b8' }

  return (
    <div className="shelf-card">
      <div className="shelf-card-header" onClick={() => navigate(`/whiskey/${w.id}`)}>
        <div className="shelf-card-name">{w.name}</div>
        <div className="shelf-card-dist">{w.distillery}</div>
      </div>
      <div className="shelf-card-meta">
        <span className="shelf-badge">{w.category}</span>
        {w.price_usd && <span className="shelf-badge">${w.price_usd}</span>}
        {item.purchase_price && (
          <span className="shelf-badge shelf-badge--paid">Paid ${item.purchase_price}</span>
        )}
      </div>
      <div className="shelf-card-status-row">
        <span className="shelf-status-dot" style={{ background: statusColors[item.status] }} />
        <select
          className="shelf-status-select"
          value={item.status}
          onChange={e => onUpdate(item.id, { status: e.target.value })}
        >
          <option value="sealed">Sealed</option>
          <option value="opened">Opened</option>
          <option value="finished">Finished</option>
        </select>
        <button className="shelf-remove-btn" onClick={() => onRemove(item.id)} title="Remove">
          ×
        </button>
      </div>
      {item.personal_notes && (
        <div className="shelf-notes">{item.personal_notes}</div>
      )}
      {item.purchase_location && (
        <div className="shelf-location">Bought at: {item.purchase_location}</div>
      )}
    </div>
  )
}

export default function Collection() {
  const [items, setItems] = useState([])
  const [stats, setStats] = useState(null)
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    const statusParam = filter !== 'all' ? filter : null
    Promise.all([
      api.getCollection(statusParam),
      api.getCollectionStats(),
    ])
      .then(([col, st]) => { setItems(col); setStats(st) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filter])

  async function handleUpdate(itemId, update) {
    await api.updateCollectionItem(itemId, update)
    load()
  }

  async function handleRemove(itemId) {
    await api.removeFromCollection(itemId)
    load()
  }

  return (
    <div className="page collection-page">
      <div className="collection-hero">
        <h1>My Shelf</h1>
        <p className="collection-subtitle">Track your whiskey collection</p>
      </div>

      {/* Stats bar */}
      {stats && stats.total > 0 && (
        <div className="shelf-stats">
          <div className="shelf-stat">
            <span className="shelf-stat-val">{stats.total}</span>
            <span className="shelf-stat-label">Total</span>
          </div>
          <div className="shelf-stat">
            <span className="shelf-stat-val" style={{ color: '#4ade80' }}>{stats.sealed}</span>
            <span className="shelf-stat-label">Sealed</span>
          </div>
          <div className="shelf-stat">
            <span className="shelf-stat-val" style={{ color: '#facc15' }}>{stats.opened}</span>
            <span className="shelf-stat-label">Opened</span>
          </div>
          <div className="shelf-stat">
            <span className="shelf-stat-val" style={{ color: '#94a3b8' }}>{stats.finished}</span>
            <span className="shelf-stat-label">Finished</span>
          </div>
          {stats.total_spent > 0 && (
            <div className="shelf-stat">
              <span className="shelf-stat-val">${stats.total_spent}</span>
              <span className="shelf-stat-label">Total Spent</span>
            </div>
          )}
        </div>
      )}

      {/* Filter tabs */}
      <div className="shelf-filters">
        {Object.entries(STATUS_LABELS).map(([key, label]) => (
          <button
            key={key}
            className={`shelf-filter ${filter === key ? 'shelf-filter--active' : ''}`}
            onClick={() => setFilter(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {loading && <p className="status">Loading...</p>}

      {!loading && items.length === 0 && (
        <div className="shelf-empty">
          <div className="shelf-empty-icon">🍾</div>
          <h2>Your shelf is empty</h2>
          <p>
            Add bottles from any whiskey detail page to start tracking
            your collection.
          </p>
        </div>
      )}

      <div className="shelf-grid">
        {items.map(item => (
          <BottleCard
            key={item.id}
            item={item}
            onUpdate={handleUpdate}
            onRemove={handleRemove}
          />
        ))}
      </div>
    </div>
  )
}
