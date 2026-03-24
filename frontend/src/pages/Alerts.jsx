import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import './Alerts.css'

export default function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [hasMore, setHasMore] = useState(false)
  const ALERT_LIMIT = 50
  const addToast = useToast()

  useEffect(() => {
    loadAlerts()
  }, [])

  async function loadAlerts(append = false) {
    setLoading(true)
    setError(null)
    try {
      const skip = append ? alerts.length : 0
      const data = await api.getAlerts({ skip, limit: ALERT_LIMIT })
      if (append) {
        setAlerts(prev => [...prev, ...data])
      } else {
        setAlerts(data)
      }
      setHasMore(data.length >= ALERT_LIMIT)
    } catch (e) {
      setError(e.message || 'Failed to load notifications')
    } finally {
      setLoading(false)
    }
  }

  async function markRead(alertId) {
    try {
      await api.markAlertRead(alertId)
      setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, is_read: true } : a))
    } catch {
      addToast('Failed to mark as read', 'error')
    }
  }

  async function markAllRead() {
    try {
      await api.markAllAlertsRead()
      setAlerts(prev => prev.map(a => ({ ...a, is_read: true })))
    } catch {
      addToast('Failed to mark all as read', 'error')
    }
  }

  const unreadCount = alerts.filter(a => !a.is_read).length

  return (
    <div className="page">
      <div className="page-header">
        <h1>Notifications</h1>
        {unreadCount > 0 && (
          <button className="btn-secondary" onClick={markAllRead}>
            Mark all read ({unreadCount})
          </button>
        )}
      </div>

      {loading && <p className="page-subtitle">Loading…</p>}

      {error && (
        <div className="empty-state">
          <p className="status error">{error}</p>
          <button className="retry-btn" style={{ marginTop: '0.75rem' }} onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      {!loading && !error && alerts.length === 0 && (
        <div className="empty-state">
          <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>🔔</div>
          <p>No notifications yet.</p>
          <p className="page-subtitle">
            Follow users and watch whiskeys to get notified about new activity.
          </p>
        </div>
      )}

      <div className="alerts-list">
        {alerts.map(alert => (
          <div
            key={alert.id}
            className={`alert-item ${alert.is_read ? 'alert-item--read' : 'alert-item--unread'}`}
          >
            <div className="alert-content">
              {alert.alert_type === 'follow' ? (
                <Link to={`/user/${alert.from_username}`} className="alert-whiskey-name">
                  {alert.from_username}
                </Link>
              ) : alert.whiskey_id ? (
                <Link to={`/whiskey/${alert.whiskey_id}`} className="alert-whiskey-name">
                  {alert.whiskey_name}
                </Link>
              ) : null}
              <p className="alert-message">{alert.message}</p>
              <span className="alert-time">
                {new Date(alert.created_at).toLocaleString(undefined, {
                  month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                })}
              </span>
            </div>
            {!alert.is_read && (
              <button
                className="alert-read-btn"
                onClick={() => markRead(alert.id)}
                title="Mark as read"
              >
                ✓
              </button>
            )}
          </div>
        ))}
        {hasMore && (
          <button
            className="btn-secondary"
            style={{ width: '100%', marginTop: '1rem' }}
            onClick={() => loadAlerts(true)}
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Load more'}
          </button>
        )}
      </div>
    </div>
  )
}
