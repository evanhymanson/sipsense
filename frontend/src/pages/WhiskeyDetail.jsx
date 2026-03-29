import { useState, useEffect, useRef, useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api, isLoggedIn } from '../api/client'
import { useToast } from '../components/Toast'
import { StarDisplay } from '../utils/stars'
import { getCategoryEmoji, foodEmoji, MAX_UPLOAD_SIZE, MAX_UPLOAD_SIZE_LABEL } from '../constants'
import { mediaUrl } from '../utils/media'
import WhiskeyCard from '../components/WhiskeyCard'
import FlavorMap from '../components/FlavorMap'
import StoreLocator from '../components/StoreLocator'
import CriticScores from '../components/CriticScores'
import WhiskeyJsonLd from '../components/WhiskeyJsonLd'

const SERVING_STYLES = ['neat', 'rocks', 'cocktail', 'highball']
const SERVING_EMOJI = { neat: '🥃', rocks: '🧊', cocktail: '🍸', highball: '🥂' }

export default function WhiskeyDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [whiskey, setWhiskey] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [blurb, setBlurb] = useState(null)
  const [blurbLoading, setBlurbLoading] = useState(false)
  const [blurbStatus, setBlurbStatus] = useState(null)
  const [similar, setSimilar] = useState([])
  const [reviews, setReviews] = useState([])

  const [favorited, setFavorited] = useState(false)
  const [watching, setWatching] = useState(false)
  const [pairings, setPairings] = useState(null)
  const [pairingsError, setPairingsError] = useState(false)
  const [pairingsLoading, setPairingsLoading] = useState(false)
  const [shelfMsg, setShelfMsg] = useState('')

  // New features: price context, buy links, share
  const [priceContext, setPriceContext] = useState(null)
  const [buyLinks, setBuyLinks] = useState(null)
  const [lastRatingId, setLastRatingId] = useState(null)
  const [whiskeyVideos, setWhiskeyVideos] = useState([])
  const [matchScore, setMatchScore] = useState(null)
  const [priceAlertActive, setPriceAlertActive] = useState(false)

  // Rating form state
  const [score, setScore] = useState(0)
  const [notes, setNotes] = useState('')
  const [servingStyle, setServingStyle] = useState(null)
  const [locationNote, setLocationNote] = useState('')
  const [batchNumber, setBatchNumber] = useState('')
  const [vintageYear, setVintageYear] = useState('')
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const imagePreviewRef = useRef(null)
  const [ratingMsg, setRatingMsg] = useState('')
  const [newBadges, setNewBadges] = useState([])
  const [postCheckinRec, setPostCheckinRec] = useState(null)
  const [postCheckinBuyLink, setPostCheckinBuyLink] = useState(null)
  const [checkinInsights, setCheckinInsights] = useState([])
  const [checkinStreak, setCheckinStreak] = useState(null)
  const [checkinChallenges, setCheckinChallenges] = useState([])
  const [showAllReviews, setShowAllReviews] = useState(false)
  const [reviewSummary, setReviewSummary] = useState(null)
  const [reviewSort, setReviewSort] = useState('recent')
  const [selectedTags, setSelectedTags] = useState([])
  const [availableTags, setAvailableTags] = useState([])
  const addToast = useToast()
  const initialMount = useRef(true)
  const REVIEW_PAGE_SIZE = 10
  const visibleReviews = useMemo(
    () => showAllReviews ? reviews : reviews.slice(0, REVIEW_PAGE_SIZE),
    [reviews, showAllReviews]
  )

  // Keep ref in sync for cleanup on unmount
  useEffect(() => { imagePreviewRef.current = imagePreview }, [imagePreview])
  useEffect(() => {
    return () => { if (imagePreviewRef.current) URL.revokeObjectURL(imagePreviewRef.current) }
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setBlurb(null)
    setSimilar([])
    setReviews([])
    setFavorited(false)
    setWatching(false)
    setPairings(null)
    setPairingsError(false)
    setShelfMsg('')
    setPriceContext(null)
    setBuyLinks(null)
    setWhiskeyVideos([])
    setRatingMsg('')
    setLastRatingId(null)
    setScore(0)
    setNotes('')
    setServingStyle(null)
    setLocationNote('')
    setNewBadges([])
    setPostCheckinRec(null)
    setPostCheckinBuyLink(null)
    setShowAllReviews(false)
    setReviewSummary(null)
    setReviewSort('recent')
    setSelectedTags([])

    // Safety timeout: if loading hasn't cleared in 15s, show an error.
    // Cleared as soon as getWhiskey resolves so it can never overwrite a
    // successfully loaded page.
    const loadingTimeout = setTimeout(() => {
      if (!cancelled) { setLoading(false); setError('Page took too long to load.') }
    }, 15000)

    // Fire the critical render-blocking request first. Secondary requests
    // are chained off its completion so getWhiskey() never competes with
    // them for the 2-worker backend pool.
    api.getWhiskey(id)
      .then((w) => {
        if (cancelled) return
        setWhiskey(w)

        // Page can now render — fire all secondary requests in parallel
        api.getFlavorTags().then(t => { if (!cancelled) setAvailableTags(t) }).catch(() => {})

        setBlurbLoading(true)
        const blurbTimeout = setTimeout(() => {
          if (!cancelled) { setBlurbLoading(false); setBlurbStatus('timeout') }
        }, 15000)
        api.getBlurb(id)
          .then((r) => {
            clearTimeout(blurbTimeout)
            if (cancelled) return
            setBlurb(r?.blurb || null)
            setBlurbStatus(r?.status || null)
            if (r?.flavor_x != null && r?.flavor_y != null) {
              setWhiskey(prev => prev ? { ...prev, flavor_x: r.flavor_x, flavor_y: r.flavor_y } : prev)
            }
          })
          .catch(() => { clearTimeout(blurbTimeout); if (!cancelled) setBlurbStatus('error') })
          .finally(() => { if (!cancelled) setBlurbLoading(false) })

        api.getSimilar(id, 5).then(s => { if (!cancelled) setSimilar(s) }).catch(() => {})
        api.getRatings(id).then(r => { if (!cancelled) setReviews(r) }).catch(() => {})
        api.getReviewSummary(id).then(r => { if (!cancelled) setReviewSummary(r) }).catch(() => {})
        setPairingsError(false)
        setPairingsLoading(true)
        api.getPairings(id)
          .then(p => { if (!cancelled) setPairings(p) })
          .catch(() => { if (!cancelled) setPairingsError(true) })
          .finally(() => { if (!cancelled) setPairingsLoading(false) })
        api.getPriceContext(id).then(p => { if (!cancelled) setPriceContext(p) }).catch(() => {})
        api.getBuyLinks(id).then(b => { if (!cancelled) setBuyLinks(b) }).catch(() => {})
        api.getWhiskeyVideos(id, { limit: 4 }).then(r => { if (!cancelled) setWhiskeyVideos(r.items || []) }).catch(() => {})
      })
      .catch((e) => { if (!cancelled) setError(e.message) })
      .finally(() => {
        clearTimeout(loadingTimeout)
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
      clearTimeout(loadingTimeout)
    }
  }, [id])

  // Check if favorited + watching + price alert
  useEffect(() => {
    if (!isLoggedIn()) return
    api.getFavoriteIds()
      .then((r) => setFavorited(r.ids.includes(Number(id))))
      .catch(() => {})
    api.getWatchStatus(id)
      .then((r) => setWatching(r.watching))
      .catch(() => {})
    api.getPriceAlertStatus(id)
      .then((r) => setPriceAlertActive(r.has_alert))
      .catch(() => {})
  }, [id])

  // Fetch personal match score
  useEffect(() => {
    if (!isLoggedIn()) return
    setMatchScore(null)
    api.getMatchScores([Number(id)])
      .then(r => {
        if (r.scores?.[id] != null) setMatchScore(r.scores[id])
      })
      .catch(() => {})
  }, [id])

  // Re-fetch reviews when sort order changes (skip initial mount — already fetched above)
  useEffect(() => {
    if (initialMount.current) { initialMount.current = false; return }
    if (!id) return
    api.getRatings(id, { sort_by: reviewSort }).then(setReviews).catch(() => {})
  }, [id, reviewSort])

  async function toggleFavorite() {
    try {
      if (favorited) {
        await api.removeFavorite(id)
        setFavorited(false)
      } else {
        await api.addFavorite(id)
        setFavorited(true)
      }
    } catch {
      addToast('Failed to update favorite', 'error')
    }
  }

  async function toggleWatch() {
    try {
      if (watching) {
        await api.unwatchWhiskey(id)
        setWatching(false)
      } else {
        await api.watchWhiskey(id)
        setWatching(true)
      }
    } catch {
      addToast('Failed to update watch status', 'error')
    }
  }

  async function submitRating(e) {
    e.preventDefault()
    if (score === 0) return
    try {
      const body = { score, notes: notes || undefined }
      if (servingStyle) body.serving_style = servingStyle
      if (locationNote.trim()) body.location_note = locationNote.trim()
      if (batchNumber.trim()) body.batch_number = batchNumber.trim()
      if (vintageYear) body.vintage_year = parseInt(vintageYear, 10) || undefined
      if (selectedTags.length > 0) body.flavor_tags = selectedTags
      const result = await api.rateWhiskey(id, body)
      const [updated, updatedReviews, updatedSummary] = await Promise.all([
        api.getWhiskey(id),
        api.getRatings(id, { sort_by: reviewSort }),
        api.getReviewSummary(id),
      ])
      setWhiskey(updated)
      setReviews(updatedReviews)
      setReviewSummary(updatedSummary)
      setRatingMsg('Check-in saved!')
      setLastRatingId(result.rating.id)
      // Upload photo if attached
      if (imageFile && result.rating?.id) {
        api.uploadRatingImage(result.rating.id, imageFile).catch(() => addToast('Photo upload failed', 'error'))
      }
      setScore(0)
      setNotes('')
      setServingStyle(null)
      setLocationNote('')
      setBatchNumber('')
      setVintageYear('')
      setSelectedTags([])
      setImageFile(null)
      if (imagePreview) URL.revokeObjectURL(imagePreview)
      setImagePreview(null)
      // Show post-check-in insights, streak, challenges
      setCheckinInsights(result.insights || [])
      setCheckinStreak(result.streak || null)
      setCheckinChallenges(result.challenge_updates || [])
      // Show badge celebration
      if (result.new_badges?.length > 0) {
        setNewBadges(result.new_badges)
        setTimeout(() => setNewBadges([]), 5000)
      }
      // Fetch "what to try next" recommendation
      api.getSimilar(id, 3)
        .then(sims => {
          if (sims.length > 0) {
            setPostCheckinRec(sims[0])
            return api.getBuyLinks(sims[0].id)
          }
        })
        .then(links => { if (links) setPostCheckinBuyLink(links) })
        .catch(() => {})
    } catch (err) {
      const msg = err.message || ''
      if (msg.includes('already rated') || msg.includes('duplicate')) {
        setRatingMsg('You already checked in this whiskey — your review has been updated.')
      } else if (msg.includes('401') || msg.includes('auth') || msg.includes('log in')) {
        setRatingMsg('Please log in to check in.')
      } else {
        setRatingMsg('Something went wrong saving your check-in. Please try again.')
      }
    }
  }

  function retryPairings() {
    setPairingsError(false)
    setPairingsLoading(true)
    api.getPairings(id)
      .then(setPairings)
      .catch(() => {
        setPairingsError(true)
      })
      .finally(() => setPairingsLoading(false))
  }

  if (loading) return <div className="page detail-page"><p className="status">Loading...</p></div>
  if (error) return (
    <div className="page detail-page">
      <p className="status error">{error}</p>
      <div style={{ textAlign: 'center', marginTop: '0.5rem' }}>
        <button className="retry-btn" onClick={() => window.location.reload()}>Retry</button>
      </div>
    </div>
  )
  if (!whiskey) return null

  const pageTitle = `${whiskey.name} — ${whiskey.distillery} | SipSense`
  const pageDesc = whiskey.description
    ? whiskey.description.slice(0, 160)
    : `${whiskey.name} by ${whiskey.distillery}. ${whiskey.category}${whiskey.age ? `, ${whiskey.age} Year` : ''}, ${whiskey.abv}% ABV${whiskey.price_usd ? `. $${Number(whiskey.price_usd).toFixed(0)}` : ''}. Ratings and reviews on SipSense.`
  const pageImage = whiskey.image_url
    ? (whiskey.image_url.startsWith('http') ? whiskey.image_url : `https://sipsense.ai${whiskey.image_url}`)
    : 'https://sipsense.ai/og-image.png'

  const flavors = whiskey.flavor_profile?.split(',').map((f) => f.trim()).filter(Boolean) ?? []

  const emoji = getCategoryEmoji(whiskey.category)

  const cat = (whiskey.category || '').toLowerCase()
  const IMG_CLS = {
    bourbon: 'detail-bottle-bg--bourbon', scotch: 'detail-bottle-bg--scotch',
    irish: 'detail-bottle-bg--irish', japanese: 'detail-bottle-bg--japanese',
    rye: 'detail-bottle-bg--rye', canadian: 'detail-bottle-bg--canadian',
    'single malt': 'detail-bottle-bg--single-malt', blended: 'detail-bottle-bg--blended',
  }
  const bgCls = IMG_CLS[cat] ?? 'detail-bottle-bg--default'

  return (
    <div className="page detail-page">
      <Helmet>
        <title>{pageTitle}</title>
        <meta name="description" content={pageDesc} />
        <meta property="og:type" content="product" />
        <meta property="og:title" content={pageTitle} />
        <meta property="og:description" content={pageDesc} />
        <meta property="og:image" content={pageImage} />
        <meta property="og:url" content={`https://sipsense.ai/whiskey/${whiskey.id}`} />
        <link rel="canonical" href={`https://sipsense.ai/whiskey/${whiskey.id}`} />
      </Helmet>
      <WhiskeyJsonLd whiskey={whiskey} />

      {/* ── Hero: bottle image + key info ─────────────────── */}
      <div className="detail-hero">
        <div className={`detail-bottle-bg ${bgCls}`}>
          {!whiskey.image_url && <span className="detail-bottle-icon">{emoji}</span>}
          {whiskey.image_url && (
            <img
              src={whiskey.image_url}
              alt={whiskey.name}
              className="detail-bottle-img"
              decoding="async"
              onError={(e) => {
                e.target.style.display = 'none'
                const icon = document.createElement('span')
                icon.className = 'detail-bottle-icon'
                icon.textContent = emoji
                icon.style.display = 'flex'
                e.target.parentElement.appendChild(icon)
              }}
            />
          )}
        </div>

        <div className="detail-hero-info">
          <div className="detail-title-row">
            <h1>{whiskey.name}</h1>
            {isLoggedIn() && (
            <div className="detail-title-actions">
              <button
                className={`watch-btn ${watching ? 'watch-btn--active' : ''}`}
                onClick={toggleWatch}
                title={watching ? 'Stop watching' : 'Watch for new activity'}
                aria-label={watching ? 'Stop watching this whiskey' : 'Watch this whiskey for new activity'}
              >
                {watching ? '🔔' : '🔕'}
              </button>
              <button
                className={`fav-btn ${favorited ? 'fav-btn--active' : ''}`}
                onClick={toggleFavorite}
                title={favorited ? 'Remove from favorites' : 'Add to favorites'}
                aria-label={favorited ? 'Remove from favorites' : 'Add to favorites'}
              >
                {favorited ? '♥' : '♡'}
              </button>
              <button
                className="share-whiskey-btn"
                title="Share this whiskey"
                onClick={async () => {
                  try {
                    const url = api.getWhiskeyShareCardUrl(id)
                    const res = await fetch(url)
                    const blob = await res.blob()
                    const file = new File([blob], 'sipsense-whiskey.png', { type: 'image/png' })
                    if (navigator.share && navigator.canShare?.({ files: [file] })) {
                      await navigator.share({ title: `${whiskey.name} on SipSense`, files: [file] })
                    } else {
                      const a = document.createElement('a')
                      a.href = URL.createObjectURL(blob)
                      a.download = 'sipsense-whiskey.png'
                      a.click()
                      URL.revokeObjectURL(a.href)
                    }
                  } catch {
                    addToast('Share failed — please try again', 'error')
                  }
                }}
              >
                ↗
              </button>
            </div>
            )}
          </div>
          <p className="detail-distillery">{whiskey.distillery}</p>
          <div className="detail-badges">
            <span className="badge">{whiskey.category}</span>
            {whiskey.region && <span className="badge">{whiskey.region}</span>}
            {whiskey.age && <span className="badge">{whiskey.age} Year</span>}
            <span className="badge">{whiskey.abv}% ABV</span>
            {whiskey.price_usd && <span className={`badge${whiskey.price_is_estimated ? ' badge--estimated' : ''}`}>{whiskey.price_is_estimated ? '~' : ''}${Number(whiskey.price_usd).toFixed(2)}{whiskey.price_is_estimated ? ' Est.' : ''}</span>}
          </div>
          {whiskey.price_usd && (
            <div className="detail-hero-price">
              <span className={`big-price${whiskey.price_is_estimated ? ' big-price--estimated' : ''}`}>
                {whiskey.price_is_estimated ? '~' : ''}${Number(whiskey.price_usd).toFixed(2)}
              </span>
              {whiskey.price_is_estimated && <span className="estimated-label">Estimated Price</span>}
            </div>
          )}
          <div className="detail-hero-rating">
            <span className="big-rating">{(whiskey.rating_avg ?? 0).toFixed(1)}</span>
            <StarDisplay rating={whiskey.rating_avg || 0} className="detail-hero-stars" />
            <span className="rating-count">{whiskey.rating_count} ratings</span>
          </div>
          {matchScore != null && (
            <div className="detail-match-score">
              <span className="detail-match-num">{matchScore}%</span>
              <span className="detail-match-label">Match for You</span>
            </div>
          )}
        </div>
      </div>

      <div className="detail-header">

      {/* Price context */}
      {priceContext?.available && (
        <div className="price-context">
          <span className={`price-verdict price-verdict--${priceContext.verdict}`}>
            {priceContext.verdict_text}
          </span>
          <span className="price-detail">
            Category avg: ${priceContext.category_avg_price} &middot; Cheaper than {priceContext.price_percentile}% of {priceContext.category}
          </span>
          {priceContext.budget_alternatives?.length > 0 && (
            <div className="budget-alts">
              <h4>Similar for Less</h4>
              <div className="budget-alts-list">
                {priceContext.budget_alternatives.map((alt) => (
                  <Link key={alt.id} to={`/whiskey/${alt.id}`} className="budget-alt-card">
                    <span className="alt-name">{alt.name}</span>
                    <span className={`alt-price${alt.price_is_estimated ? ' alt-price--estimated' : ''}`}>{alt.price_is_estimated ? '~' : ''}${Number(alt.price_usd).toFixed(2)}{alt.price_is_estimated ? ' Est.' : ''}</span>
                    <span className="alt-rating">★ {alt.rating_avg?.toFixed(1)}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* What makes this special */}
      <div className="detail-blurb">
        <h3>What makes this special</h3>
        {blurbLoading ? (
          <p className="blurb-loading">
            <span className="spinner" /> Generating description…
          </p>
        ) : (blurb || whiskey.description) ? (
          <p>{blurb || whiskey.description}</p>
        ) : (blurbStatus === 'error' || blurbStatus === 'timeout') ? (
          <p className="blurb-empty">
            Couldn't load description.{' '}
            <button className="retry-btn" onClick={() => {
              setBlurbLoading(true)
              setBlurbStatus(null)
              const t = setTimeout(() => { setBlurbLoading(false); setBlurbStatus('timeout') }, 15000)
              api.getBlurb(id)
                .then(r => { clearTimeout(t); setBlurb(r?.blurb || null); setBlurbStatus(r?.status || null) })
                .catch(() => { clearTimeout(t); setBlurbStatus('error') })
                .finally(() => setBlurbLoading(false))
            }}>Retry</button>
          </p>
        ) : (
          <p className="blurb-empty">No description available yet.</p>
        )}
      </div>

      {/* Clickable flavor tags */}
      {flavors.length > 0 && (
        <div className="flavor-tags">
          <h3>Flavor Profile</h3>
          <div className="tags">
            {flavors.map((f) => (
              <button
                key={f}
                className="tag tag--clickable"
                onClick={() => navigate(`/?flavor=${encodeURIComponent(f)}`)}
                title={`Browse ${f} whiskeys`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Flavor Map plot */}
      <FlavorMap whiskey={whiskey} similar={similar} />

      {/* Community Reviews — Vivino style */}
      <div className="reviews-section">
        <h3>Community Reviews</h3>

        {/* Rating Summary Block */}
        {reviewSummary && reviewSummary.distribution.total > 0 && (
          <div className="rating-summary">
            <div className="rating-summary-left">
              <span className="rating-summary-score">
                {reviewSummary.distribution.average.toFixed(1)}
              </span>
              <StarDisplay rating={reviewSummary.distribution.average} className="rating-summary-stars" />
              <span className="rating-summary-count">
                {reviewSummary.distribution.total} rating{reviewSummary.distribution.total !== 1 ? 's' : ''}
              </span>
            </div>
            <div className="rating-summary-right">
              {[5, 4, 3, 2, 1].map(star => {
                const count = reviewSummary.distribution[`star_${star}`]
                const pct = reviewSummary.distribution.total > 0
                  ? (count / reviewSummary.distribution.total * 100)
                  : 0
                return (
                  <div key={star} className="distribution-row">
                    <span className="distribution-label">{star}★</span>
                    <div className="distribution-bar-bg">
                      <div
                        className="distribution-bar-fill"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="distribution-count">{count}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Community Flavor Tags */}
        {reviewSummary?.community_tags?.length > 0 && (
          <div className="community-tags">
            <h4>Community Taste Profile</h4>
            <div className="community-tags-list">
              {reviewSummary.community_tags.map(t => (
                <span key={t.tag} className="community-tag">
                  {t.tag}
                  <span className="community-tag-count">{t.count}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Sort Dropdown */}
        {reviews.length > 0 && (
          <div className="review-sort-bar">
            <label htmlFor="review-sort">Sort by:</label>
            <select
              id="review-sort"
              value={reviewSort}
              onChange={(e) => setReviewSort(e.target.value)}
              className="review-sort-select"
            >
              <option value="recent">Most Recent</option>
              <option value="helpful">Most Helpful</option>
              <option value="highest">Highest Rated</option>
              <option value="lowest">Lowest Rated</option>
            </select>
          </div>
        )}

        {/* Review Cards */}
        {reviews.length > 0 ? (
          <div className="review-list">
            {visibleReviews.map((r) => (
              <div key={r.id} className="review-item">
                <div className="review-header">
                  <Link to={`/user/${r.username || r.user_id}`} className="review-user">{r.username || r.user_id}</Link>
                  <StarDisplay rating={r.score || 0} className="review-stars" />
                  {r.serving_style && (
                    <span className="checkin-serving">{SERVING_EMOJI[r.serving_style] || ''} {r.serving_style}</span>
                  )}
                  <span className="review-date">{new Date(r.created_at).toLocaleDateString()}</span>
                </div>
                {r.location_note && <p className="review-location">{r.location_note}</p>}
                {r.flavor_tags?.length > 0 && (
                  <div className="review-tags">
                    {r.flavor_tags.map(tag => (
                      <span key={tag} className="review-tag">{tag}</span>
                    ))}
                  </div>
                )}
                {r.image_url && (
                  <img src={mediaUrl(r.image_url)} alt="Tasting photo" className="review-photo" loading="lazy" decoding="async" />
                )}
                {r.notes && <p className="review-notes">{r.notes}</p>}
                <div className="review-actions">
                  {r.toast_count > 0 && (
                    <span className="review-toasts">🍻 {r.toast_count}</span>
                  )}
                  {r.helpful_count > 0 && (
                    <span className="review-toasts">👍 {r.helpful_count}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="reviews-empty">
            <p>No reviews yet.</p>
            <button className="btn-secondary" onClick={() => document.getElementById('check-in')?.scrollIntoView({ behavior: 'smooth' })}>
              Be the first to check in
            </button>
          </div>
        )}

        {!showAllReviews && reviews.length > REVIEW_PAGE_SIZE && (
          <button className="btn-secondary" style={{ marginTop: '1rem', width: '100%' }} onClick={() => setShowAllReviews(true)}>
            Show All {reviews.length} Reviews
          </button>
        )}
      </div>

      {/* Expert / Critic Scores */}
      <CriticScores whiskeyId={whiskey.id} />

      {/* Community Videos */}
      {whiskeyVideos.length > 0 && (
        <div className="whiskey-videos-section">
          <h3>Community Videos</h3>
          <div className="whiskey-videos-grid">
            {whiskeyVideos.map(v => (
              <Link key={v.id} to={`/videos?v=${v.id}`} className="whiskey-video-thumb">
                {v.thumbnail_url ? (
                  <img src={mediaUrl(v.thumbnail_url)} alt={v.title || 'Video'} />
                ) : (
                  <div className="whiskey-video-placeholder">▶</div>
                )}
                <div className="whiskey-video-meta">
                  <span>@{v.user_id}</span>
                  <span>{v.toast_count} 🤍</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Add to Shelf */}
      {isLoggedIn() ? (
      <div className="shelf-action">
        <button
          className="shelf-add-btn"
          onClick={async () => {
            try {
              await api.addToCollection({ whiskey_id: Number(id) })
              setShelfMsg('Added to your collection!')
            } catch (err) {
              setShelfMsg(err.message)
            }
          }}
        >
          + Add to Collection
        </button>
        {shelfMsg && (
          <span className="shelf-msg">
            {shelfMsg}
            {shelfMsg.includes('Added') && (
              <>{' '}<Link to="/me?tab=collection" className="shelf-msg-link">View Collection</Link></>
            )}
          </span>
        )}
      </div>
      ) : (
        <div className="shelf-action"><Link to="/onboarding" className="shelf-add-btn">Sign in to save this bottle</Link></div>
      )}

      {/* Buy this bottle */}
      {buyLinks?.links?.length > 0 && (
        <div className="buy-links-section">
          <h3>Buy This Bottle</h3>
          {/* Price context badge */}
          {priceContext?.available && (
            <div className={`price-verdict price-verdict--${priceContext.verdict}`}>
              {priceContext.verdict_text} — {priceContext.price_percentile}th percentile for {priceContext.category}
              {priceContext.category_avg_price && (
                <span className="price-verdict-avg"> (avg ${priceContext.category_avg_price.toFixed(0)})</span>
              )}
            </div>
          )}
          <div className="buy-links-grid">
            {buyLinks.links.map((link, i) => (
              <a
                key={i}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="buy-link-btn"
                onClick={() => {
                  api.recordAffiliateClick({
                    whiskey_id: Number(id),
                    retailer: link.retailer,
                    source: 'detail',
                  }).catch(() => {})
                }}
              >
                {link.retailer} &rarr;
              </a>
            ))}
          </div>
          {/* Price alert toggle */}
          {isLoggedIn() && whiskey.price_usd && (
            <button
              className={`price-alert-btn ${priceAlertActive ? 'price-alert-btn--active' : ''}`}
              onClick={async () => {
                try {
                  if (priceAlertActive) {
                    await api.removePriceAlert(id)
                    setPriceAlertActive(false)
                    addToast('Price alert removed', 'info')
                  } else {
                    await api.createPriceAlert({ whiskey_id: Number(id) })
                    setPriceAlertActive(true)
                    addToast('Price alert set! We\'ll notify you of drops.', 'success')
                  }
                } catch {
                  addToast('Could not update price alert', 'error')
                }
              }}
            >
              {priceAlertActive ? 'Price Alert On' : 'Notify Me of Price Drops'}
            </button>
          )}
          {/* Budget alternatives */}
          {priceContext?.budget_alternatives?.length > 0 && (
            <div className="budget-alts">
              <h4>Similar for Less</h4>
              <div className="budget-alts-list">
                {priceContext.budget_alternatives.map(alt => (
                  <Link key={alt.id} to={`/whiskey/${alt.id}`} className="budget-alt-item">
                    <span className="budget-alt-name">{alt.name}</span>
                    <span className="budget-alt-price">${Number(alt.price_usd).toFixed(0)}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
          <p className="affiliate-disclosure">Links may earn SipSense a small commission at no cost to you.</p>
        </div>
      )}

      {/* Food Pairings & Cocktails */}
      {pairingsLoading && (
        <div className="pairings-section">
          <h3>Pairs Well With</h3>
          <p className="blurb-loading">Loading pairings...</p>
        </div>
      )}
      {pairingsError && !pairings && (
        <div className="pairings-section">
          <h3>Pairs Well With</h3>
          <p className="blurb-empty">
            Couldn't load pairings.{' '}
            <button className="retry-btn" onClick={retryPairings}>Tap to retry</button>
          </p>
        </div>
      )}
      {pairings && (
        <div className="pairings-section">
          {pairings.food_pairings?.length > 0 && (
            <>
              <h3>Pairs Well With</h3>
              <div className="pairing-grid">
                {pairings.food_pairings.map((p, i) => (
                  <div key={i} className="pairing-card">
                    {p.image_url ? (
                      <img
                        src={mediaUrl(p.image_url)}
                        alt={p.item}
                        className="pairing-img"
                        onError={(e) => {
                          e.target.style.display = 'none'
                          e.target.nextElementSibling && (e.target.nextElementSibling.style.display = 'flex')
                        }}
                      />
                    ) : null}
                    <span className="pairing-emoji" style={p.image_url ? { display: 'none' } : undefined}>
                      {foodEmoji(p.item)}
                    </span>
                    <div className="pairing-text">
                      <span className="pairing-name">{p.item}</span>
                      <span className="pairing-why">{p.why}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
          {pairings.cocktails?.length > 0 && (
            <>
              <h3>Cocktail Ideas</h3>
              <div className="cocktail-list">
                {pairings.cocktails.map((c, i) => (
                  <div key={i} className="cocktail-item">
                    {c.image_url && (
                      <img
                        src={c.image_url}
                        alt={c.name}
                        className="cocktail-img"
                        onError={(e) => { e.target.style.display = 'none' }}
                      />
                    )}
                    <div className="cocktail-text">
                      <div className="cocktail-name">{c.name}</div>
                      <div className="cocktail-ingredients">{c.ingredients}</div>
                      <div className="cocktail-desc">{c.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Find this nearby */}
      <StoreLocator whiskeyId={Number(id)} whiskeyName={whiskey.name} />

      {/* If you like this, try... */}
      {similar.length > 0 && (
        <div className="similar-section">
          <h3>If you like this, try...</h3>
          <div className="similar-grid">
            {similar.map((w) => (
              <WhiskeyCard key={w.id} whiskey={w} />
            ))}
          </div>
        </div>
      )}

      {/* Badge celebration */}
      {newBadges.length > 0 && (
        <div className="badge-celebration">
          <div className="badge-celebration-inner">
            <h3>Badge Unlocked!</h3>
            {newBadges.map(b => (
              <div key={b.slug} className="badge-celebration-item">
                <span className="badge-celebration-emoji">{b.emoji}</span>
                <div>
                  <strong>{b.name}</strong>
                  <p>{b.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Post-check-in insights */}
      {checkinInsights.length > 0 && (
        <div className="checkin-insights">
          {checkinInsights.map((insight, i) => (
            <div key={i} className="checkin-insight-card">{insight}</div>
          ))}
        </div>
      )}

      {/* Streak update after check-in */}
      {checkinStreak && checkinStreak.is_new_day && (
        <div className="checkin-streak-banner">
          Day {checkinStreak.current_streak} streak! Keep it going!
        </div>
      )}

      {/* Challenge progress after check-in */}
      {checkinChallenges.length > 0 && (
        <div className="checkin-challenges">
          {checkinChallenges.map((cu, i) => (
            <div key={i} className="checkin-challenge-card">
              <strong>{cu.challenge_title}</strong>
              <div className="checkin-challenge-progress">
                <div className="checkin-challenge-bar">
                  <div className="checkin-challenge-fill" style={{ width: `${Math.min(100, (cu.progress / cu.goal) * 100)}%` }} />
                </div>
                <span>{cu.progress}/{cu.goal}{cu.completed ? ' — Complete!' : ''}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <div id="check-in" className="rate-form">
        <h3>Check In This Whiskey</h3>
        {!isLoggedIn() ? (
          <div className="sign-in-cta">
            <p>Sign in to rate and review this whiskey.</p>
            <Link to="/onboarding" className="btn-primary">Sign In</Link>
          </div>
        ) : (
        <form onSubmit={submitRating}>
          <div className="star-picker half-star-picker" role="radiogroup" aria-label="Rating">
            {[1, 2, 3, 4, 5].map((n) => (
              <span key={n} className="half-star-group">
                <button
                  type="button"
                  className={`half-star half-star--left ${score >= n - 0.5 ? 'filled' : ''}`}
                  onClick={() => setScore(n - 0.5)}
                  aria-label={`${n - 0.5} stars`}
                  aria-checked={score === n - 0.5}
                  role="radio"
                >★</button>
                <button
                  type="button"
                  className={`half-star half-star--right ${score >= n ? 'filled' : ''}`}
                  onClick={() => setScore(n)}
                  aria-label={`${n} star${n > 1 ? 's' : ''}`}
                  aria-checked={score === n}
                  role="radio"
                >★</button>
              </span>
            ))}
            {score > 0 && <span className="half-star-value">{score.toFixed(1)}</span>}
          </div>

          <div className="serving-picker">
            <span className="serving-label">How are you drinking it?</span>
            <div className="serving-options">
              {SERVING_STYLES.map(s => (
                <button
                  key={s}
                  type="button"
                  className={`serving-btn ${servingStyle === s ? 'serving-btn--active' : ''}`}
                  onClick={() => setServingStyle(servingStyle === s ? null : s)}
                >
                  {SERVING_EMOJI[s]} {s}
                </button>
              ))}
            </div>
          </div>

          <input
            type="text"
            placeholder="Where are you? (optional)"
            value={locationNote}
            onChange={(e) => setLocationNote(e.target.value)}
            className="location-input"
          />

          <div className="vintage-batch-row">
            <input
              type="text"
              placeholder="Batch # (optional)"
              value={batchNumber}
              onChange={(e) => setBatchNumber(e.target.value)}
              className="batch-input"
            />
            <input
              type="number"
              placeholder="Vintage year"
              value={vintageYear}
              onChange={(e) => setVintageYear(e.target.value)}
              min={1900}
              max={new Date().getFullYear()}
              className="vintage-input"
            />
          </div>

          <textarea
            placeholder="Tasting notes (optional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
          />

          {/* Flavor tag picker */}
          {availableTags.length > 0 && (
            <div className="flavor-tag-picker">
              <span className="flavor-tag-label">What do you taste?</span>
              <div className="flavor-tag-options">
                {availableTags.map(tag => (
                  <button
                    key={tag}
                    type="button"
                    className={`flavor-tag-btn ${selectedTags.includes(tag) ? 'flavor-tag-btn--active' : ''}`}
                    onClick={() => {
                      setSelectedTags(prev =>
                        prev.includes(tag)
                          ? prev.filter(t => t !== tag)
                          : prev.length < 10 ? [...prev, tag] : prev
                      )
                    }}
                  >
                    {tag}
                  </button>
                ))}
              </div>
              {selectedTags.length > 0 && (
                <span className="flavor-tag-count">{selectedTags.length}/10 selected</span>
              )}
            </div>
          )}

          <div className="photo-upload">
            <label className="photo-upload-btn">
              {imagePreview ? 'Change Photo' : 'Add Photo'}
              <input
                type="file"
                accept="image/*"
                capture="environment"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) {
                    if (f.size > MAX_UPLOAD_SIZE) {
                      addToast(`Photo must be under ${MAX_UPLOAD_SIZE_LABEL}`, 'error')
                      return
                    }
                    if (imagePreview) URL.revokeObjectURL(imagePreview)
                    setImageFile(f)
                    setImagePreview(URL.createObjectURL(f))
                  }
                }}
                style={{ display: 'none' }}
              />
            </label>
            {imagePreview && (
              <img src={imagePreview} className="photo-preview" alt="Preview" />
            )}
          </div>

          <button type="submit" disabled={score === 0}>Check In</button>
          {ratingMsg && <p className="status">{ratingMsg}</p>}
          {ratingMsg === 'Check-in saved!' && postCheckinRec && (
            <div className="post-checkin-rec">
              <h4 className="post-checkin-label">What to Try Next</h4>
              <div className="post-checkin-card">
                <Link to={`/whiskey/${postCheckinRec.id}`} className="post-checkin-link">
                  <div className="post-checkin-bottle">
                    {postCheckinRec.image_url ? (
                      <img src={postCheckinRec.image_url} alt={postCheckinRec.name} loading="lazy" />
                    ) : (
                      <span>{getCategoryEmoji(postCheckinRec.category)}</span>
                    )}
                  </div>
                  <div className="post-checkin-info">
                    <span className="post-checkin-name">{postCheckinRec.name}</span>
                    <span className="post-checkin-detail">
                      {postCheckinRec.category}
                      {postCheckinRec.price_usd && ` · $${Number(postCheckinRec.price_usd).toFixed(0)}`}
                    </span>
                  </div>
                </Link>
                {postCheckinBuyLink?.links?.[0] && (
                  <a
                    href={postCheckinBuyLink.links[0].url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="post-checkin-buy"
                    onClick={() => {
                      api.recordAffiliateClick({
                        whiskey_id: postCheckinRec.id,
                        retailer: postCheckinBuyLink.links[0].retailer,
                        source: 'post_checkin',
                      }).catch(() => {})
                    }}
                  >
                    Buy &rarr;
                  </a>
                )}
              </div>
            </div>
          )}
          {lastRatingId && (
            <button
              type="button"
              className="share-btn"
              onClick={async () => {
                try {
                  const url = api.getShareCardUrl(lastRatingId)
                  const res = await fetch(url)
                  const blob = await res.blob()
                  const file = new File([blob], 'sipsense-rating.png', { type: 'image/png' })
                  if (navigator.share && navigator.canShare?.({ files: [file] })) {
                    await navigator.share({
                      title: `My ${whiskey.name} rating on SipSense`,
                      files: [file],
                    })
                  } else {
                    const a = document.createElement('a')
                    a.href = URL.createObjectURL(blob)
                    a.download = 'sipsense-rating.png'
                    a.click()
                    URL.revokeObjectURL(a.href)
                  }
                } catch {
                  addToast('Share failed — please try again', 'error')
                }
              }}
            >
              Share This Check-In
            </button>
          )}
        </form>
        )}
      </div>

    </div>{/* detail-header */}
  </div>
  )
}
