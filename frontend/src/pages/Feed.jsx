import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import CheckInCard from '../components/CheckInCard'
import UserSearch from '../components/UserSearch'
import { WHISKEY_CATEGORIES } from '../constants'
import './Feed.css'

const CATEGORIES = ['all', ...WHISKEY_CATEGORIES.map(c => c.value)]

export default function Feed() {
  const [items, setItems] = useState([])
  const [category, setCategory] = useState('all')
  const [friendsOnly, setFriendsOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState(null)
  const [suggested, setSuggested] = useState([])
  const [sugDismissed, setSugDismissed] = useState(false)

  let currentUser = null
  try { currentUser = localStorage.getItem('sipsense_user') } catch { /* private browsing */ }

  // Load suggested follows once for logged-in users
  useEffect(() => {
    if (!currentUser) return
    api.getSuggestedUsers(5)
      .then(data => setSuggested(data || []))
      .catch(() => { /* non-critical: suggested follows */ })
  }, [currentUser])

  const loadFeed = useCallback(async (skip = 0, append = false, opts = {}) => {
    try {
      const params = { skip, limit: 20 }
      if (category !== 'all') params.category = category
      if (friendsOnly && currentUser) params.following_only = true
      const data = await api.getFeed(params, opts)
      const MAX_FEED_ITEMS = 200
      setItems(prev => {
        const merged = append ? [...prev, ...data.items] : data.items
        return merged.slice(0, MAX_FEED_ITEMS)
      })
      setHasMore(data.has_more)
    } catch (e) {
      if (e.name === 'AbortError') return
      setError(e.message)
    }
  }, [category, friendsOnly, currentUser])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    loadFeed(0, false, { signal: controller.signal }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [loadFeed])

  async function handleLoadMore() {
    setLoadingMore(true)
    await loadFeed(items.length, true)
    setLoadingMore(false)
  }

  async function handleFollowSuggested(username) {
    try {
      await api.followUser(username)
      setSuggested(prev => prev.filter(u => u.username !== username))
    } catch (err) { console.error('Failed to follow user:', err) }
  }

  return (
    <div className="page feed-page">
      <div className="feed-header">
        <div>
          <h1>Activity Feed</h1>
          <p className="page-subtitle">See what the community is sipping</p>
        </div>
        {currentUser && <UserSearch />}
      </div>

      {/* Everyone / Friends toggle */}
      {currentUser && (
        <div className="feed-mode-toggle" role="tablist" aria-label="Feed filter">
          <button
            role="tab"
            aria-selected={!friendsOnly}
            className={`feed-mode-btn${!friendsOnly ? ' feed-mode-btn--active' : ''}`}
            onClick={() => setFriendsOnly(false)}
          >
            Everyone
          </button>
          <button
            role="tab"
            aria-selected={friendsOnly}
            className={`feed-mode-btn${friendsOnly ? ' feed-mode-btn--active' : ''}`}
            onClick={() => setFriendsOnly(true)}
          >
            Friends
          </button>
        </div>
      )}

      {/* AI-Suggested Follows */}
      {suggested.length > 0 && !sugDismissed && (
        <div className="feed-suggested">
          <div className="feed-suggested-header">
            <h3>People Like You</h3>
            <button className="feed-suggested-dismiss" onClick={() => setSugDismissed(true)}>&times;</button>
          </div>
          <div className="feed-suggested-scroll">
            {suggested.map(u => (
              <div key={u.username} className="feed-suggested-card">
                <Link to={`/user/${u.username}`} className="feed-suggested-name">{u.username}</Link>
                <span className="feed-suggested-match">{u.match_score}% match</span>
                <span className="feed-suggested-reason">{u.reason}</span>
                <button className="feed-suggested-follow" onClick={() => handleFollowSuggested(u.username)}>Follow</button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="feed-filters">
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            className={`feed-filter-btn ${category === cat ? 'feed-filter-btn--active' : ''}`}
            onClick={() => setCategory(cat)}
          >
            {cat === 'all' ? 'All' : cat}
          </button>
        ))}
      </div>

      {loading && <p className="status">Loading feed...</p>}
      {error && (
        <div className="status error">
          <p>{error}</p>
          <button className="retry-btn" style={{ marginTop: '0.5rem' }} onClick={() => { setError(null); setLoading(true); loadFeed(0).finally(() => setLoading(false)) }}>Retry</button>
        </div>
      )}

      {!loading && items.length === 0 && (
        friendsOnly ? (
          <div className="feed-empty-friends">
            <p>No check-ins from people you follow yet.</p>
            <p className="feed-empty-hint">Search for people above and follow them to see their sips here.</p>
          </div>
        ) : (
          <p className="status">No check-ins yet. Be the first to rate a whiskey!</p>
        )
      )}

      <div className="feed-list">
        {items.map(item => (
          <CheckInCard key={item.rating.id} item={item} />
        ))}
      </div>

      {hasMore && !loading && (
        <button
          className="feed-load-more"
          onClick={handleLoadMore}
          disabled={loadingMore}
        >
          {loadingMore ? 'Loading...' : 'Load More'}
        </button>
      )}
    </div>
  )
}
