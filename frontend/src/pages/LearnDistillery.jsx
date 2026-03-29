import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'

export default function LearnDistillery() {
  const { slug } = useParams()
  const [distillery, setDistillery] = useState(null)
  const [bottles, setBottles] = useState([])
  const [bottleTotal, setBottleTotal] = useState(0)
  const [error, setError] = useState(null)

  useEffect(() => {
    setDistillery(null)
    setError(null)
    setBottles([])
    api.getDistillery(slug)
      .then(setDistillery)
      .catch(() => setError('Distillery not found.'))
    api.getDistilleryBottles(slug, { limit: 8 })
      .then(data => { setBottles(data.items); setBottleTotal(data.total) })
      .catch(() => {})
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
      {distillery.founded_year && (
        <p className="distillery-founded">Est. {distillery.founded_year}</p>
      )}
      {distillery.known_for?.length > 0 && (
        <div className="learn-facts">
          <h3>Known For</h3>
          <ul>
            {distillery.known_for.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}
      {distillery.fun_facts?.length > 0 && (
        <div className="distillery-fun-facts">
          <h3>Fun Facts</h3>
          <ul>
            {distillery.fun_facts.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}
      {distillery.production_details && (
        <div className="distillery-production">
          <h3>Production Details</h3>
          <dl className="production-dl">
            {distillery.production_details.mash_bill && (
              <><dt>Mash Bill</dt><dd>{distillery.production_details.mash_bill}</dd></>
            )}
            {distillery.production_details.water_source && (
              <><dt>Water Source</dt><dd>{distillery.production_details.water_source}</dd></>
            )}
            {distillery.production_details.barrel_type && (
              <><dt>Barrel Type</dt><dd>{distillery.production_details.barrel_type}</dd></>
            )}
          </dl>
        </div>
      )}
      <div className="learn-body">
        {distillery.body?.map((p, i) => <p key={i}>{p}</p>)}
      </div>
      {bottles.length > 0 && (
        <div className="distillery-bottles">
          <h2>Bottles from {distillery.title} ({bottleTotal})</h2>
          <div className="whiskey-grid">
            {bottles.map(w => <WhiskeyCard key={w.id} whiskey={w} />)}
          </div>
        </div>
      )}
      <div className="learn-next">
        <Link to={`/?q=${encodeURIComponent(distillery.title)}`} className="btn-secondary">
          Browse All {distillery.title} Whiskeys &rarr;
        </Link>
      </div>
    </div>
  )
}
