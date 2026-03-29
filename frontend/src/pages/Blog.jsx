import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api } from '../api/client'

export default function Blog() {
  const [articles, setArticles] = useState([])

  useEffect(() => {
    api.getBlogArticles().then(setArticles).catch(() => {})
  }, [])

  return (
    <div className="page blog-page">
      <Helmet>
        <title>Whiskey Guides & Rankings | SipSense Blog</title>
        <meta name="description" content="Data-driven whiskey guides and rankings. Best bourbons, top scotch, value picks — all ranked by real community ratings." />
        <meta property="og:title" content="Whiskey Guides & Rankings | SipSense Blog" />
        <meta property="og:description" content="Data-driven whiskey guides ranked by real community ratings." />
        <link rel="canonical" href="https://sipsense.ai/blog" />
      </Helmet>
      <h1>Whiskey Guides & Rankings</h1>
      <p className="page-subtitle">
        Data-driven guides built from real ratings. No paid placements — just what the community actually enjoys.
      </p>
      <div className="blog-grid">
        {articles.map(a => (
          <Link key={a.slug} to={`/blog/${a.slug}`} className="blog-card">
            <h3>{a.title}</h3>
            <p>{a.meta_description}</p>
          </Link>
        ))}
      </div>
      <div className="blog-footer">
        <Link to="/learn" className="btn-secondary">&larr; Learn About Whiskey</Link>
      </div>
    </div>
  )
}
