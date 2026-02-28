import { useState, useEffect } from 'react'
import { api } from '../api/client'
import CheckInCard from '../components/CheckInCard'
import './Feed.css'

const CATEGORIES = ['all', 'bourbon', 'scotch', 'irish', 'japanese', 'rye', 'single malt']

export default function Feed() {
  const [items, setItems] = useState([])
  const [category, setCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState(null)

  async function loadFeed(skip = 0, append = false) {
    try {
      const params = { skip, limit: 20 }
      if (category !== 'all') params.category = category
      const data = await api.getFeed(params)
      setItems(prev => append ? [...prev, ...data.items] : data.items)
      setHasMore(data.has_more)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    setLoading(true)
    setError(null)
    loadFeed(0).finally(() => setLoading(false))
  }, [category])

  async function handleLoadMore() {
    setLoadingMore(true)
    await loadFeed(items.length, true)
    setLoadingMore(false)
  }

  return (
    <div className="page feed-page">
      <h1>Activity Feed</h1>
      <p className="page-subtitle">See what the community is sipping</p>

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
      {error && <p className="status error">{error}</p>}

      {!loading && items.length === 0 && (
        <p className="status">No check-ins yet. Be the first to rate a whiskey!</p>
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
