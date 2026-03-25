import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { api, getUsername } from '../api/client'

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0, 0, 0, 0.4)',
    zIndex: 30,
    display: 'flex',
    alignItems: 'flex-end',
  },
  panel: {
    width: '100%',
    maxHeight: '60vh',
    background: 'var(--surface)',
    borderRadius: '16px 16px 0 0',
    display: 'flex',
    flexDirection: 'column',
    animation: 'slideUp 0.2s ease-out',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0.75rem 1rem',
    borderBottom: '1px solid var(--border)',
  },
  headerTitle: {
    fontSize: '0.95rem',
    fontWeight: 700,
    color: 'var(--text)',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    fontSize: '1.3rem',
    cursor: 'pointer',
    lineHeight: 1,
  },
  list: {
    flex: 1,
    overflowY: 'auto',
    padding: '0.75rem 1rem',
  },
  comment: {
    display: 'flex',
    gap: '0.6rem',
    marginBottom: '0.85rem',
  },
  avatar: {
    width: '2rem',
    height: '2rem',
    borderRadius: '50%',
    background: 'var(--border)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '0.75rem',
    color: 'var(--text-muted)',
    flexShrink: 0,
    fontWeight: 700,
  },
  commentBody: {
    flex: 1,
    minWidth: 0,
  },
  commentUser: {
    fontSize: '0.8rem',
    fontWeight: 700,
    color: 'var(--text)',
    textDecoration: 'none',
  },
  commentText: {
    fontSize: '0.85rem',
    color: 'var(--text-soft)',
    marginTop: '0.1rem',
    wordBreak: 'break-word',
  },
  commentTime: {
    fontSize: '0.7rem',
    color: 'var(--text-muted)',
    marginTop: '0.2rem',
  },
  deleteBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    fontSize: '0.7rem',
    cursor: 'pointer',
    marginLeft: '0.5rem',
  },
  inputRow: {
    display: 'flex',
    gap: '0.5rem',
    padding: '0.75rem 1rem',
    borderTop: '1px solid var(--border)',
  },
  input: {
    flex: 1,
    padding: '0.5rem 0.65rem',
    background: 'var(--bg)',
    border: '1px solid var(--border)',
    borderRadius: '999px',
    color: 'var(--text)',
    fontFamily: 'inherit',
    fontSize: '0.85rem',
  },
  sendBtn: {
    background: 'var(--amber)',
    color: '#1a1a1a',
    border: 'none',
    borderRadius: '999px',
    padding: '0.5rem 0.9rem',
    fontWeight: 700,
    fontSize: '0.85rem',
    cursor: 'pointer',
    fontFamily: 'inherit',
  },
  empty: {
    textAlign: 'center',
    color: 'var(--text-muted)',
    padding: '2rem 1rem',
    fontSize: '0.9rem',
  },
}

function timeAgo(dateStr) {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  return `${days}d`
}

export default function CheckInComments({ ratingId, onClose, onCommentCountChange }) {
  const [comments, setComments] = useState([])
  const [loading, setLoading] = useState(true)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const COMMENT_LIMIT = 50
  const MAX_COMMENTS = 500
  const inputRef = useRef(null)
  const currentUser = getUsername()

  useEffect(() => {
    loadComments()
    setTimeout(() => inputRef.current?.focus(), 200)
  // eslint-disable-next-line react-hooks/exhaustive-deps -- ratingId is the real trigger; loadComments is not memoized
  }, [ratingId])

  async function loadComments(append = false) {
    setLoading(true)
    try {
      const skip = append ? comments.length : 0
      const data = await api.getCheckInComments(ratingId, { skip, limit: COMMENT_LIMIT })
      if (append) {
        setComments(prev => [...prev, ...data].slice(0, MAX_COMMENTS))
      } else {
        setComments(data)
      }
      setHasMore(data.length >= COMMENT_LIMIT && (append ? comments.length + data.length < MAX_COMMENTS : true))
    } catch (err) {
      console.error('Failed to load comments:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleSend(e) {
    e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || sending) return

    setSending(true)
    try {
      const newComment = await api.addCheckInComment(ratingId, trimmed)
      setComments(prev => [newComment, ...prev])
      setText('')
      onCommentCountChange?.(1)
    } catch (err) {
      console.error('Failed to post comment:', err)
    } finally {
      setSending(false)
    }
  }

  async function handleDelete(commentId) {
    try {
      await api.deleteCheckInComment(commentId)
      setComments(prev => prev.filter(c => c.id !== commentId))
      onCommentCountChange?.(-1)
    } catch (err) {
      console.error('Failed to delete comment:', err)
    }
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.panel} onClick={e => e.stopPropagation()}>
        <div style={styles.header}>
          <span style={styles.headerTitle}>
            {comments.length} Comment{comments.length !== 1 ? 's' : ''}
          </span>
          <button style={styles.closeBtn} onClick={onClose}>&times;</button>
        </div>

        <div style={styles.list}>
          {loading && comments.length === 0 ? (
            <p style={styles.empty}>Loading...</p>
          ) : comments.length === 0 ? (
            <p style={styles.empty}>No comments yet. Be the first!</p>
          ) : (
            <>
              {comments.map(c => (
                <div key={c.id} style={styles.comment}>
                  <div style={styles.avatar}>
                    {c.user_id[0]?.toUpperCase()}
                  </div>
                  <div style={styles.commentBody}>
                    <Link to={`/user/${c.user_id}`} style={styles.commentUser}>
                      {c.user_id}
                    </Link>
                    <p style={styles.commentText}>{c.text}</p>
                    <span style={styles.commentTime}>
                      {timeAgo(c.created_at)}
                      {c.user_id === currentUser && (
                        <button
                          style={styles.deleteBtn}
                          onClick={() => handleDelete(c.id)}
                        >
                          Delete
                        </button>
                      )}
                    </span>
                  </div>
                </div>
              ))}
              {hasMore && (
                <button
                  onClick={() => loadComments(true)}
                  disabled={loading}
                  style={{ background: 'none', border: 'none', color: 'var(--amber)', cursor: 'pointer', width: '100%', padding: '0.5rem', fontSize: '0.85rem', fontFamily: 'inherit' }}
                >
                  {loading ? 'Loading...' : 'Load more comments'}
                </button>
              )}
            </>
          )}
        </div>

        {currentUser && (
          <form style={styles.inputRow} onSubmit={handleSend}>
            <input
              ref={inputRef}
              style={styles.input}
              placeholder="Add a comment..."
              value={text}
              onChange={e => setText(e.target.value)}
              maxLength={500}
            />
            <button
              type="submit"
              style={{
                ...styles.sendBtn,
                opacity: text.trim() && !sending ? 1 : 0.5,
              }}
              disabled={!text.trim() || sending}
            >
              Post
            </button>
          </form>
        )}
      </div>

      <style>{`
        @keyframes slideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
