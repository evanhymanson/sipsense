import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import './DailyDiscovery.css'

export default function DailyDiscovery() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.getDailyDiscovery()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="daily-page">
        <div className="daily-loading">
          <div className="daily-loading-icon">🌅</div>
          <p>Pouring today's discovery...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="daily-page">
        <p className="status error">{error}</p>
      </div>
    )
  }

  if (!data) return null

  const w = data.whiskey
  const flavors = data.flavors || []

  return (
    <div className="daily-page">
      <div className="daily-header">
        <span className="daily-date">{data.weekday}, {data.date}</span>
        {data.weekday_message && (
          <p className="daily-weekday-msg">{data.weekday_message}</p>
        )}
      </div>

      <div className="daily-card" onClick={() => navigate(`/whiskey/${w.id}`)}>
        <span className="daily-label">Today's Discovery</span>
        <h1 className="daily-name">{w.name}</h1>
        <p className="daily-distillery">{w.distillery}</p>

        <div className="daily-badges">
          <span className="daily-badge">{w.category}</span>
          {w.region && <span className="daily-badge">{w.region}</span>}
          {w.age && <span className="daily-badge">{w.age} yr</span>}
          <span className="daily-badge">{w.abv}% ABV</span>
          {w.price_usd && <span className="daily-badge">${w.price_usd}</span>}
        </div>

        {w.rating_avg > 0 && (
          <div className="daily-rating">
            <span className="daily-stars">{'★'.repeat(Math.round(w.rating_avg))}</span>
            <span className="daily-rating-text">{w.rating_avg.toFixed(1)}</span>
            {w.rating_count > 0 && (
              <span className="daily-rating-count">({w.rating_count} ratings)</span>
            )}
          </div>
        )}

        {w.description && (
          <p className="daily-description">{w.description}</p>
        )}

        {flavors.length > 0 && (
          <div className="daily-flavors">
            {flavors.map((f) => (
              <span key={f} className="daily-flavor-tag">{f}</span>
            ))}
          </div>
        )}

        <span className="daily-view-cta">View full details →</span>
      </div>

      <div className="daily-extras">
        <div className="daily-tip">
          <span className="extra-label">Tasting Tip</span>
          <p>{data.tasting_tip}</p>
        </div>

        {data.did_you_know && (
          <div className="daily-fact">
            <span className="extra-label">Did You Know?</span>
            <p>{data.did_you_know}</p>
          </div>
        )}

        {data.conversation_starter && (
          <div className="daily-conversation">
            <span className="extra-label">Conversation Starter</span>
            <p>{data.conversation_starter}</p>
          </div>
        )}
      </div>
    </div>
  )
}
