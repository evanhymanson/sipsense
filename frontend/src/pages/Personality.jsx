import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import './Personality.css'

export default function Personality() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.getPersonality()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="personality-page">
        <div className="personality-loading">
          <div className="personality-loading-icon">🥃</div>
          <p>Analyzing your whiskey soul...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="personality-page">
        <p className="status error">{error}</p>
      </div>
    )
  }

  if (!data) return null

  const isNewcomer = data.type === 'curious_newcomer'

  return (
    <div className="personality-page">
      <div className="personality-card">
        <div className="personality-emoji">{data.emoji}</div>
        <h1 className="personality-title">{data.title}</h1>
        <p className="personality-tagline">{data.tagline}</p>
        <p className="personality-description">{data.description}</p>

        {data.spirit_bottle && (
          <div className="personality-spirit">
            <span className="spirit-label">Your spirit bottle</span>
            <span className="spirit-name">{data.spirit_bottle}</span>
          </div>
        )}

        {data.playlist_vibe && (
          <div className="personality-vibe">
            <span className="vibe-label">Your vibe</span>
            <span className="vibe-name">{data.playlist_vibe}</span>
          </div>
        )}
      </div>

      {!isNewcomer && (
        <div className="personality-details">
          <div className="personality-traits">
            {data.top_flavors?.length > 0 && (
              <div className="trait-section">
                <h3>Your Flavor DNA</h3>
                <div className="trait-tags">
                  {data.top_flavors.map((f) => (
                    <span key={f} className="trait-tag">{f}</span>
                  ))}
                </div>
              </div>
            )}

            {data.top_categories?.length > 0 && (
              <div className="trait-section">
                <h3>Your Go-To Styles</h3>
                <div className="trait-tags">
                  {data.top_categories.map((c) => (
                    <span key={c} className="trait-tag trait-tag--category">{c}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {data.stats && (
            <div className="personality-stats">
              <div className="pstat">
                <span className="pstat-value">{data.stats.total_rated}</span>
                <span className="pstat-label">Rated</span>
              </div>
              <div className="pstat">
                <span className="pstat-value">{data.stats.total_favorites}</span>
                <span className="pstat-label">Favorites</span>
              </div>
              <div className="pstat">
                <span className="pstat-value">{data.stats.categories_explored}</span>
                <span className="pstat-label">Styles Explored</span>
              </div>
              {data.stats.avg_abv && (
                <div className="pstat">
                  <span className="pstat-value">{data.stats.avg_abv}%</span>
                  <span className="pstat-label">Avg ABV</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {isNewcomer && (
        <div className="personality-cta">
          <p>Rate a few whiskeys and your personality will emerge!</p>
          <div className="cta-buttons">
            <button onClick={() => navigate('/quiz')}>Take the Quiz</button>
            <button className="cta-secondary" onClick={() => navigate('/')}>Browse Whiskeys</button>
          </div>
        </div>
      )}
    </div>
  )
}
