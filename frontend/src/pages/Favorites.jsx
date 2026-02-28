import { useState, useEffect } from 'react'
import { api, getUsername } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'

export default function Favorites() {
  const username = getUsername()
  const [favorites, setFavorites] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getFavorites()
      .then(setFavorites)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="page">
      <div className="fav-header">
        <h1>My Favorites</h1>
        <span className="fav-user">@{username}</span>
      </div>
      <p className="page-subtitle">
        {favorites.length > 0
          ? `${favorites.length} saved whiskey${favorites.length !== 1 ? 's' : ''}`
          : 'No favorites yet — heart a whiskey on its detail page to save it here.'}
      </p>

      {loading && <p className="status">Loading...</p>}
      {error && <p className="status error">{error}</p>}

      <div className="card-grid">
        {favorites.map((w) => (
          <WhiskeyCard key={w.id} whiskey={w} />
        ))}
      </div>
    </div>
  )
}
