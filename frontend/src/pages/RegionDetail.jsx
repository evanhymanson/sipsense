import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'

export default function RegionDetail() {
  const { slug } = useParams()
  const [region, setRegion] = useState(null)
  const [whiskeys, setWhiskeys] = useState([])
  const [total, setTotal] = useState(0)
  const [sort, setSort] = useState('rating')
  const [error, setError] = useState(null)

  useEffect(() => {
    setRegion(null)
    setError(null)
    api.getRegion(slug)
      .then(setRegion)
      .catch(() => setError('Region not found.'))
  }, [slug])

  useEffect(() => {
    api.getRegionWhiskeys(slug, { sort, limit: 20 })
      .then(data => { setWhiskeys(data.items); setTotal(data.total) })
      .catch(() => {})
  }, [slug, sort])

  if (error) return (
    <div className="page regions-page">
      <p className="status error">{error}</p>
      <Link to="/regions" className="btn-secondary">All Regions</Link>
    </div>
  )
  if (!region) return <div className="page regions-page"><p className="status">Loading...</p></div>

  return (
    <div className="page regions-page">
      <Helmet>
        <title>{region.title} Whiskey Region | SipSense</title>
        <meta name="description" content={region.tagline} />
        <link rel="canonical" href={`https://sipsense.ai/regions/${slug}`} />
      </Helmet>
      <Link to="/regions" className="learn-back">&larr; All Regions</Link>

      <div className="region-hero">
        <span className="region-hero-emoji">{region.emoji}</span>
        <div>
          <h1>{region.title}</h1>
          <span className="region-country">{region.country}</span>
          <p className="region-tagline">{region.tagline}</p>
        </div>
      </div>

      {region.style_description?.map((p, i) => (
        <p key={i} className="region-body-paragraph">{p}</p>
      ))}

      {region.key_characteristics?.length > 0 && (
        <div className="region-chars">
          <h3>Key Characteristics</h3>
          <div className="flavor-tags-row">
            {region.key_characteristics.map(c => (
              <span key={c} className="flavor-tag">{c}</span>
            ))}
          </div>
        </div>
      )}

      {region.notable_distilleries?.length > 0 && (
        <div className="region-distilleries">
          <h3>Notable Distilleries</h3>
          <p>{region.notable_distilleries.join(' · ')}</p>
        </div>
      )}

      {region.climate_note && (
        <div className="region-climate">
          <h3>Climate & Aging</h3>
          <p>{region.climate_note}</p>
        </div>
      )}

      <div className="region-whiskeys-section">
        <div className="region-whiskeys-header">
          <h2>Whiskeys from {region.title} ({total})</h2>
          <select value={sort} onChange={e => setSort(e.target.value)} className="sort-select">
            <option value="rating">Top Rated</option>
            <option value="price_asc">Price: Low to High</option>
            <option value="price_desc">Price: High to Low</option>
            <option value="name">Name</option>
          </select>
        </div>
        <div className="whiskey-grid">
          {whiskeys.map(w => <WhiskeyCard key={w.id} whiskey={w} />)}
        </div>
        {whiskeys.length === 0 && <p className="status">No whiskeys found for this region.</p>}
      </div>
    </div>
  )
}
