import { useState, useEffect, memo } from 'react'
import { Link } from 'react-router-dom'
import { api, getUsername } from '../api/client'
import { useToast } from './Toast'
import CheckInComments from './CheckInComments'
import { StarDisplay } from '../utils/stars'
import { mediaUrl } from '../utils/media'
import './CheckInCard.css'

const SERVING_EMOJI = {
  neat: '🥃',
  rocks: '🧊',
  cocktail: '🍸',
  highball: '🥂',
}

function timeAgo(dateStr) {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}

export default memo(function CheckInCard({ item, onToastToggle }) {
  const {
    rating, whiskey, username,
    toast_count, user_toasted,
    helpful_count = 0, user_marked_helpful = false,
    comment_count = 0,
  } = item
  const [toasted, setToasted] = useState(user_toasted)
  const [count, setCount] = useState(toast_count)
  const [helpfulCount, setHelpfulCount] = useState(helpful_count)
  const [markedHelpful, setMarkedHelpful] = useState(user_marked_helpful)
  const [commentCount, setCommentCount] = useState(comment_count)
  const [showComments, setShowComments] = useState(false)
  useEffect(() => { setToasted(user_toasted) }, [user_toasted])
  useEffect(() => { setCount(toast_count) }, [toast_count])
  useEffect(() => { setHelpfulCount(helpful_count) }, [helpful_count])
  useEffect(() => { setMarkedHelpful(user_marked_helpful) }, [user_marked_helpful])
  useEffect(() => { setCommentCount(comment_count) }, [comment_count])
  const [busy, setBusy] = useState(false)
  const [helpfulBusy, setHelpfulBusy] = useState(false)
  const currentUser = getUsername()
  const isOwn = currentUser === username
  const addToast = useToast()

  if (!whiskey) return null

  async function handleToast() {
    if (busy) return
    if (isOwn) {
      addToast("Can't toast your own check-in", 'info')
      return
    }
    setBusy(true)
    try {
      if (toasted) {
        await api.removeToast(rating.id)
        setToasted(false)
        setCount(c => c - 1)
      } else {
        await api.addToast(rating.id)
        setToasted(true)
        setCount(c => c + 1)
      }
      onToastToggle?.()
    } catch {
      addToast('Failed to update toast. Please try again.', 'error')
    } finally {
      setBusy(false)
    }
  }

  async function handleHelpful() {
    if (helpfulBusy || !currentUser) return
    if (isOwn) {
      addToast("Can't mark your own review as helpful", 'info')
      return
    }
    setHelpfulBusy(true)
    try {
      if (markedHelpful) {
        await api.unmarkHelpful(rating.id)
        setMarkedHelpful(false)
        setHelpfulCount(c => c - 1)
      } else {
        await api.markHelpful(rating.id)
        setMarkedHelpful(true)
        setHelpfulCount(c => c + 1)
      }
    } catch {
      addToast('Failed to update helpful vote', 'error')
    } finally {
      setHelpfulBusy(false)
    }
  }

  return (
    <div className="checkin-card">
      <div className="checkin-top">
        <Link to={`/user/${username}`} className="checkin-user">{username}</Link>
        <span className="checkin-time">{timeAgo(rating.created_at)}</span>
      </div>

      <Link to={`/whiskey/${whiskey.id}`} className="checkin-whiskey">
        <span className="checkin-whiskey-name">{whiskey.name}</span>
        <span className="checkin-whiskey-meta">
          {whiskey.distillery || ''}{whiskey.distillery && whiskey.category ? ' · ' : ''}{whiskey.category || ''}
        </span>
      </Link>

      <div className="checkin-rating">
        <StarDisplay rating={rating.score || 0} className="checkin-stars" />
        {rating.serving_style && (
          <span className="checkin-serving">
            {SERVING_EMOJI[rating.serving_style] || ''} {rating.serving_style}
          </span>
        )}
        {rating.location_note && (
          <span className="checkin-location">📍 {rating.location_note}</span>
        )}
      </div>

      {rating.image_url && (
        <img
          src={mediaUrl(rating.image_url)}
          alt={`${username}'s tasting photo`}
          className="checkin-photo"
          loading="lazy"
          decoding="async"
          onError={(e) => { e.target.style.display = 'none' }}
        />
      )}

      {rating.notes && <p className="checkin-notes">{rating.notes}</p>}

      <div className="checkin-actions">
        {!isOwn && (
          <button
            className={`toast-btn ${toasted ? 'toast-btn--active' : ''}`}
            onClick={handleToast}
            disabled={busy || !currentUser}
            aria-label={toasted ? 'Remove toast' : 'Toast this check-in'}
          >
            🍻 {count > 0 && <span className="toast-count">{count}</span>}
          </button>
        )}
        {isOwn && count > 0 && (
          <span className="toast-btn toast-btn--own" aria-label="Toasts received">
            🍻 <span className="toast-count">{count}</span>
          </span>
        )}
        {!isOwn && (
          <button
            className={`toast-btn helpful-btn ${markedHelpful ? 'helpful-btn--active' : ''}`}
            onClick={handleHelpful}
            disabled={helpfulBusy || !currentUser}
            aria-label={markedHelpful ? 'Undo helpful' : 'Mark as helpful'}
          >
            👍 {helpfulCount > 0 && <span className="toast-count">{helpfulCount}</span>}
          </button>
        )}
        {isOwn && helpfulCount > 0 && (
          <span className="toast-btn" aria-label="Helpful votes">
            👍 <span className="toast-count">{helpfulCount}</span>
          </span>
        )}
        <button
          className="toast-btn"
          onClick={() => setShowComments(true)}
          aria-label="View comments"
        >
          💬 {commentCount > 0 && <span className="toast-count">{commentCount}</span>}
        </button>
        <button
          className="toast-btn share-btn"
          onClick={() => {
            const url = `${window.location.origin}/whiskey/${rating.whiskey_id}`
            const text = `Check out this ${whiskey?.name || 'whiskey'} check-in on SipSense!`
            if (navigator.share) {
              navigator.share({ title: 'SipSense Check-in', text, url }).catch(() => {})
            } else {
              navigator.clipboard?.writeText(url).then(() => {
                addToast('Link copied!', 'success')
              }).catch(() => {})
            }
          }}
          aria-label="Share check-in"
        >
          📤
        </button>
      </div>

      {showComments && (
        <CheckInComments
          ratingId={rating.id}
          onClose={() => setShowComments(false)}
          onCommentCountChange={(delta) => setCommentCount(c => c + delta)}
        />
      )}
    </div>
  )
})
