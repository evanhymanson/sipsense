import { useState, useEffect } from 'react'
import { api } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'
import './Trending.css'

const CATEGORIES = ['all', 'bourbon', 'scotch', 'irish', 'japanese', 'rye']

export default function Trending() {
  const [trending, setTrending] = useState([])
  const [newArrivals, setNewArrivals] = useState([])
  const [activeCategory, setActiveCategory] = useState('all')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const params = activeCategory !== 'all' ? { category: activeCategory } : {}
    Promise.all([
      api.getTrending(params),
      api.getNewArrivals(8),
    ])
      .then(([t, n]) => { setTrending(t); setNewArrivals(n) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [activeCategory])

  return (
    <div className="page trending-page">
      <div className="trending-hero">
        <h1>Trending Now</h1>
        <p className="trending-subtitle">
          See what the SipSense community is rating and saving right now.
        </p>
      </div>

      <div className="trending-tabs">
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            className={`trending-tab ${activeCategory === cat ? 'trending-tab--active' : ''}`}
            onClick={() => setActiveCategory(cat)}
          >
            {cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1)}
          </button>
        ))}
      </div>

      {loading && <p className="status">Loading...</p>}

      {!loading && trending.length > 0 && (
        <section className="trending-section">
          <h2>Hot Right Now</h2>
          <div className="card-grid">
            {trending.map(w => (
              <WhiskeyCard key={w.id} whiskey={w} />
            ))}
          </div>
        </section>
      )}

      {!loading && newArrivals.length > 0 && (
        <section className="trending-section">
          <h2>Recently Added</h2>
          <div className="card-grid">
            {newArrivals.map(w => (
              <WhiskeyCard key={w.id} whiskey={w} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
