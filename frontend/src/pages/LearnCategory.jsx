import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api } from '../api/client'

export default function LearnCategory() {
  const { slug } = useParams()
  const [category, setCategory] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setCategory(null)
    setError(null)
    api.getCategory(slug)
      .then(setCategory)
      .catch(() => setError('Category not found.'))
  }, [slug])

  if (error) return (
    <div className="page learn-page">
      <p className="status error">{error}</p>
      <Link to="/learn" className="btn-secondary">Back to Learn</Link>
    </div>
  )
  if (!category) return <div className="page learn-page"><p className="status">Loading...</p></div>

  return (
    <div className="page learn-page">
      <Helmet>
        <title>{category.title} Guide | SipSense</title>
        <meta name="description" content={category.tagline} />
        <meta property="og:title" content={`${category.title} Guide | SipSense`} />
        <meta property="og:description" content={category.tagline} />
        <link rel="canonical" href={`https://sipsense.ai/learn/categories/${slug}`} />
      </Helmet>
      <Link to="/learn" className="learn-back">&larr; All Guides</Link>
      <div className="learn-hero">
        <span className="learn-hero-emoji">{category.emoji}</span>
        <div>
          <h1>{category.title}</h1>
          <p className="learn-tagline">{category.tagline}</p>
        </div>
      </div>
      {category.quick_facts?.length > 0 && (
        <div className="learn-facts">
          <h3>Quick Facts</h3>
          <ul>
            {category.quick_facts.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}
      {category.flavor_tags?.length > 0 && (
        <div className="learn-tags">
          {category.flavor_tags.map(t => (
            <Link key={t} to={`/?flavor=${encodeURIComponent(t)}`} className="tag">{t}</Link>
          ))}
        </div>
      )}
      <div className="learn-body">
        {category.body?.map((p, i) => <p key={i}>{p}</p>)}
      </div>
      {category.entry_bottles?.length > 0 && (
        <div className="learn-entry">
          <h3>Where to Start</h3>
          <div className="learn-entry-list">
            {category.entry_bottles.map((name, i) => (
              <Link key={i} to={`/?q=${encodeURIComponent(name)}`} className="learn-entry-item">{name}</Link>
            ))}
          </div>
        </div>
      )}
      {category.next_explore && (
        <div className="learn-next">
          <Link to={`/learn/categories/${category.next_explore}`} className="btn-secondary">
            Next: Explore {category.next_explore.charAt(0).toUpperCase() + category.next_explore.slice(1)} &rarr;
          </Link>
        </div>
      )}
    </div>
  )
}
