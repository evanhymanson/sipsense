import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api } from '../api/client'

export default function Regions() {
  const [regions, setRegions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getRegions()
      .then(setRegions)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="page regions-page">
      <Helmet>
        <title>Whiskey Regions | SipSense</title>
        <meta name="description" content="Explore the world's great whiskey regions — from Kentucky bourbon country to the smoky shores of Islay." />
        <link rel="canonical" href="https://sipsense.ai/regions" />
      </Helmet>
      <h1>Whiskey Regions</h1>
      <p className="page-subtitle">Explore the world's great whiskey-producing regions and their distinctive styles.</p>
      {loading ? (
        <p className="status">Loading regions...</p>
      ) : (
        <div className="regions-grid">
          {regions.map(r => (
            <Link to={`/regions/${r.slug}`} key={r.slug} className="region-card">
              <span className="region-emoji">{r.emoji}</span>
              <div className="region-card-info">
                <h3>{r.title}</h3>
                <span className="region-country">{r.country}</span>
                <p className="region-tagline">{r.tagline}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
