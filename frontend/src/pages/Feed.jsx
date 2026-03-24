import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import CheckInCard from '../components/CheckInCard'
import UserSearch from '../components/UserSearch'
import './Feed.css'

export default function Feed() {
  const [items, setItems] = useState([])
  const [category, setCategory] = useState('all')
  const [friendsOnly, setFriendsOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState(null)

  let currentUser = null
  try { currentUser = localStorage.getItem('sipsense_user') } catch { /* private browsing */ }

  const loadFeed = useCallback(async (skip = 0, append = false) => {
    try {
      const params = { skip, limit: 20 }
      if (category !== 'all') params.category = category
      if (friendsOnly && currentUser) params.following_only = true
      const data = await api.getFeed(params)
      const MAX_FEED_ITEMS = 200
      setItems(prev => {
        const merged = append ? [...prev, ...data.items] : data.items
        return merged.slice(0, MAX_FEED_ITEMS)
      })
      setHasMore(data.has_more)
    } catch (e) {
      setError(e.message)
    }
  }, [category, friendsOnly, currentUser])

  useEffect(() => {
    setLoading(true)
    setError(null)
    loadFeed(0).finally(() => setLoading(false))
  }, [loadFeed])

  async function handleLoadMore() {
    setLoadingMore(true)
    await loadFeed(items.length, true)
    setLoadingMore(false)
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

      {/* Everyone / Friends toggle — Issue #20: proper tab semantics */}
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
