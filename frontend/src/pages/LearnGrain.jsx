import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api } from '../api/client'

export default function LearnGrain() {
  const { slug } = useParams()
  const [grain, setGrain] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setGrain(null)
    setError(null)
    api.getGrain(slug)
      .then(setGrain)
      .catch(() => setError('Grain category not found.'))
  }, [slug])

  if (error) return (
    <div className="page learn-page">
      <p className="status error">{error}</p>
      <Link to="/learn" className="btn-secondary">Back to Learn</Link>
    </div>
  )
  if (!grain) return <div className="page learn-page"><p className="status">Loading...</p></div>

  return (
    <div className="page learn-page">
      <Helmet>
        <title>{grain.title} | SipSense Learn</title>
        <meta name="description" content={grain.tagline} />
        <link rel="canonical" href={`https://sipsense.ai/learn/grains/${slug}`} />
      </Helmet>
      <Link to="/learn" className="learn-back">&larr; All Guides</Link>

      <div className="learn-hero">
        <span className="learn-hero-emoji">{grain.emoji}</span>
        <div>
          <h1>{grain.title}</h1>
          <p className="learn-tagline">{grain.tagline}</p>
        </div>
      </div>

      {grain.quick_facts?.length > 0 && (
        <div className="learn-facts">
          <h3>Quick Facts</h3>
          <ul>
            {grain.quick_facts.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}

      {grain.body?.map((p, i) => (
        <p key={i} className="learn-body-paragraph">{p}</p>
      ))}

      {grain.subcategories?.length > 0 && (
        <div className="grain-subcategories">
          <h2>Sub-styles</h2>
          {grain.subcategories.map((sub, i) => (
            <div key={i} className="grain-sub-card">
              <h3>{sub.name}</h3>
              <p>{sub.description}</p>
              {sub.examples?.length > 0 && (
                <p className="grain-examples"><strong>Examples:</strong> {sub.examples.join(', ')}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
