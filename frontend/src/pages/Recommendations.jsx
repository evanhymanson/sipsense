import { useState, useEffect } from 'react'
import { api } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'

export default function Recommendations() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Try explained recommendations first, fall back to plain
    api.getExplainedRecommendations(8)
      .then(setResults)
      .catch(() => {
        // Fall back to plain recommendations
        return api.getRecommendations(8).then(data =>
          setResults(data.map(r => ({ ...r, reason: null })))
        )
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="page">
      <h1>For You</h1>
      <p className="page-subtitle">
        Personalized picks based on your ratings and taste profile.
      </p>

      {loading && <p className="status">Analyzing your taste profile...</p>}
      {error && <p className="status error">{error}</p>}

      {!loading && results.length === 0 && !error && (
        <p className="status">
          No recommendations yet — try rating a few whiskeys on their detail pages first!
        </p>
      )}

      <div className="card-grid">
        {results.map(({ whiskey, score, reason }) => (
          <div key={whiskey.id} className="rec-card-wrap">
            <WhiskeyCard whiskey={whiskey} score={score} />
            {reason && (
              <div className="rec-reason">
                <span className="rec-reason-icon">*</span> {reason}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
