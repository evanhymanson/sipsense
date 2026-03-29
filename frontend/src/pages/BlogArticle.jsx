import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api } from '../api/client'
import { StarDisplay } from '../utils/stars'

export default function BlogArticle() {
  const { slug } = useParams()
  const [article, setArticle] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setArticle(null)
    setError(null)
    api.getBlogArticle(slug)
      .then(setArticle)
      .catch(() => setError('Article not found.'))
  }, [slug])

  if (error) return (
    <div className="page blog-page">
      <p className="status error">{error}</p>
      <Link to="/blog" className="btn-secondary">Back to Blog</Link>
    </div>
  )
  if (!article) return <div className="page blog-page"><p className="status">Loading...</p></div>

  // Schema.org ItemList structured data
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: article.title,
    description: article.meta_description,
    numberOfItems: article.whiskeys.length,
    itemListElement: article.whiskeys.map((w, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      item: {
        '@type': 'Product',
        name: w.name,
        brand: { '@type': 'Brand', name: w.distillery },
        category: `Whiskey > ${w.category}`,
        ...(w.image_url && { image: w.image_url.startsWith('http') ? w.image_url : `https://sipsense.ai${w.image_url}` }),
        ...(w.price_usd && {
          offers: {
            '@type': 'Offer',
            price: w.price_usd,
            priceCurrency: 'USD',
            availability: 'https://schema.org/InStock',
          },
        }),
        ...(w.rating_avg && w.rating_count > 0 && {
          aggregateRating: {
            '@type': 'AggregateRating',
            ratingValue: w.rating_avg,
            bestRating: 5,
            worstRating: 1,
            ratingCount: w.rating_count,
          },
        }),
      },
    })),
  }

  return (
    <div className="page blog-page">
      <Helmet>
        <title>{article.title} | SipSense</title>
        <meta name="description" content={article.meta_description} />
        <meta property="og:title" content={`${article.title} | SipSense`} />
        <meta property="og:description" content={article.meta_description} />
        <link rel="canonical" href={`https://sipsense.ai/blog/${slug}`} />
        <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      </Helmet>

      <Link to="/blog" className="learn-back">&larr; All Guides</Link>
      <h1>{article.title}</h1>

      <div className="blog-intro">
        {article.intro?.map((p, i) => <p key={i}>{p}</p>)}
      </div>

      <div className="blog-list">
        {article.whiskeys.map((w, i) => (
          <Link key={w.id} to={`/whiskey/${w.id}`} className="blog-whiskey-card">
            <span className="blog-rank">#{i + 1}</span>
            {w.image_url && (
              <img
                src={w.image_url}
                alt={w.name}
                className="blog-whiskey-img"
                loading="lazy"
              />
            )}
            <div className="blog-whiskey-info">
              <h3>{w.name}</h3>
              <p className="blog-whiskey-meta">
                {w.distillery}
                {w.region && <> &middot; {w.region}</>}
                {w.age && <> &middot; {w.age}yr</>}
                {w.abv && <> &middot; {w.abv}%</>}
              </p>
              <div className="blog-whiskey-stats">
                {w.rating_avg != null && (
                  <span className="blog-rating">
                    <StarDisplay rating={w.rating_avg} /> {w.rating_avg}
                    {w.rating_count > 0 && <span className="blog-count"> ({w.rating_count})</span>}
                  </span>
                )}
                {w.price_usd && (
                  <span className="blog-price">${w.price_usd.toFixed(0)}</span>
                )}
              </div>
              {w.flavor_profile && (
                <div className="blog-flavors">
                  {w.flavor_profile.split(',').slice(0, 4).map(f => (
                    <span key={f.trim()} className="tag">{f.trim()}</span>
                  ))}
                </div>
              )}
            </div>
          </Link>
        ))}
      </div>

      {article.whiskeys.length === 0 && (
        <p className="status">No whiskeys match this criteria yet. Check back as more ratings come in!</p>
      )}

      <div className="blog-footer">
        <Link to="/blog" className="btn-secondary">&larr; More Guides</Link>
        <Link to="/" className="btn-secondary">Browse All Whiskeys</Link>
      </div>
    </div>
  )
}
