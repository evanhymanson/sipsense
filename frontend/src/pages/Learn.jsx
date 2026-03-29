import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api } from '../api/client'

export default function Learn() {
  const [categories, setCategories] = useState([])
  const [distilleries, setDistilleries] = useState([])

  useEffect(() => {
    api.getCategories().then(setCategories).catch(() => {})
    api.getDistilleries().then(setDistilleries).catch(() => {})
  }, [])

  return (
    <div className="page learn-page">
      <Helmet>
        <title>Learn About Whiskey | SipSense</title>
        <meta name="description" content="Whiskey guides, distillery stories, and a complete glossary. Learn about bourbon, scotch, rye, Irish, Japanese, and Canadian whisky." />
        <meta property="og:title" content="Learn About Whiskey | SipSense" />
        <meta property="og:description" content="Whiskey guides, distillery stories, and a complete glossary." />
        <link rel="canonical" href="https://sipsense.ai/learn" />
      </Helmet>
      <h1>Learn About Whiskey</h1>
      <p className="page-subtitle">Guides, distillery stories, and everything you need to explore the world of whiskey.</p>
      <section className="learn-section">
        <h2>Category Guides</h2>
        <div className="learn-grid">
          {categories.map(cat => (
            <Link key={cat.slug} to={`/learn/categories/${cat.slug}`} className="learn-card">
              <span className="learn-card-emoji">{cat.emoji}</span>
              <div className="learn-card-text">
                <h3>{cat.title}</h3>
                <p>{cat.tagline}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>
      <section className="learn-section">
        <h2>Distillery Stories</h2>
        <div className="learn-grid">
          {distilleries.map(d => (
            <Link key={d.slug} to={`/learn/distilleries/${d.slug}`} className="learn-card">
              <span className="learn-card-emoji">{d.emoji}</span>
              <div className="learn-card-text">
                <h3>{d.title}</h3>
                <p>{d.location} &middot; {d.category}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>
      <section className="learn-section">
        <h2>Rankings & Guides</h2>
        <div className="learn-grid">
          <Link to="/blog" className="learn-card">
            <span className="learn-card-emoji">🏆</span>
            <div className="learn-card-text">
              <h3>Best Whiskeys</h3>
              <p>Data-driven rankings built from real community ratings</p>
            </div>
          </Link>
        </div>
      </section>
      <section className="learn-section">
        <h2>Reference</h2>
        <div className="learn-grid">
          <Link to="/learn/glossary" className="learn-card">
            <span className="learn-card-emoji">📖</span>
            <div className="learn-card-text">
              <h3>Whiskey Glossary</h3>
              <p>30+ terms every whiskey enthusiast should know</p>
            </div>
          </Link>
        </div>
      </section>
    </div>
  )
}
