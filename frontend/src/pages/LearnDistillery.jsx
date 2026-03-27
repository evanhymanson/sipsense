import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api } from '../api/client'

export default function LearnDistillery() {
  const { slug } = useParams()
  const [distillery, setDistillery] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setDistillery(null)
    setError(null)
    api.getDistillery(slug)
      .then(setDistillery)
      .catch(() => setError('Distillery not found.'))
  }, [slug])

  if (error) return (
    <div className="page learn-page">
      <p className="status error">{error}</p>
      <Link to="/learn" className="btn-secondary">Back to Learn</Link>
    </div>
  )
  if (!distillery) return <div className="page learn-page"><p className="status">Loading...</p></div>

  return (
    <div className="page learn-page">
      <Helmet>
        <title>{distillery.title} | SipSense</title>
        <meta name="description" content={`${distillery.title} — ${distillery.tagline}. ${distillery.location}.`} />
        <meta property="og:title" content={`${distillery.title} | SipSense`} />
        <meta property="og:description" content={distillery.tagline} />
        <link rel="canonical" href={`https://sipsense.ai/learn/distilleries/${slug}`} />
      </Helmet>
      <Link to="/learn" className="learn-back">&larr; All Guides</Link>
      <div className="learn-hero">
        <span className="learn-hero-emoji">{distillery.emoji}</span>
        <div>
          <h1>{distillery.title}</h1>
          <p className="learn-tagline">{distillery.location} &middot; {distillery.category}</p>
        </div>
      </div>
      {distillery.known_for?.length > 0 && (
        <div className="learn-facts">
          <h3>Known For</h3>
          <ul>
            {distillery.known_for.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}
      <div className="learn-body">
        {distillery.body?.map((p, i) => <p key={i}>{p}</p>)}
      </div>
      <div className="learn-next">
        <Link to={`/?q=${encodeURIComponent(distillery.title)}`} className="btn-secondary">
          Browse {distillery.title} Whiskeys &rarr;
        </Link>
      </div>
    </div>
  )
}
