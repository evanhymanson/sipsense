import { memo } from 'react'
import { Link } from 'react-router-dom'

function imageCls(category) {
  const c = (category || '').toLowerCase()
  if (c === 'bourbon') return 'card-img--bourbon'
  if (c === 'scotch') return 'card-img--scotch'
  if (c === 'irish') return 'card-img--irish'
  if (c === 'japanese') return 'card-img--japanese'
  if (c === 'rye') return 'card-img--rye'
  if (c === 'canadian') return 'card-img--canadian'
  if (c === 'single malt') return 'card-img--single-malt'
  if (c === 'blended') return 'card-img--blended'
  return 'card-img--default'
}

export default memo(function WhiskeyCard({ whiskey, score, compareMode, isCompared, onCompareToggle }) {
  const hasRating = whiskey.rating_avg > 0

  function handleImgError(e) {
    e.target.style.display = 'none'
    e.target.nextElementSibling?.style && (e.target.nextElementSibling.style.display = 'flex')
  }

  function handleCompareClick(e) {
    e.preventDefault()
    e.stopPropagation()
    onCompareToggle?.(whiskey)
  }

  return (
    <Link to={`/whiskey/${whiskey.id}`} className={`card${isCompared ? ' card--compared' : ''}`}>
      {/* Compare checkbox overlay */}
      {compareMode && (
        <button
          className={`card-compare-check${isCompared ? ' card-compare-check--active' : ''}`}
          onClick={handleCompareClick}
          title={isCompared ? 'Remove from comparison' : 'Add to comparison'}
        >
          {isCompared ? '✓' : '+'}
        </button>
      )}

      {/* ── Bottle image ─────────────────────────────────── */}
      <div className={`card-img ${imageCls(whiskey.category)}`}>
        {whiskey.image_url && (
          <img
            src={whiskey.image_url}
            alt={whiskey.name}
            className="card-bottle"
            loading="lazy"
            decoding="async"
            width={120}
            height={240}
            onError={handleImgError}
          />
        )}
        {/* SVG placeholder — shown if no image or image fails */}
        <div className="card-bottle-placeholder" style={whiskey.image_url ? { display: 'none' } : undefined}>
          <svg viewBox="0 0 40 100" className="card-bottle-svg">
            <rect x="14" y="0" width="12" height="12" rx="2" fill="currentColor" opacity="0.25" />
            <rect x="16" y="12" width="8" height="8" rx="1" fill="currentColor" opacity="0.2" />
            <path d="M12 20 Q12 30 10 40 L10 92 Q10 98 16 98 L24 98 Q30 98 30 92 L30 40 Q28 30 28 20 Z"
              fill="currentColor" opacity="0.15" />
          </svg>
        </div>
      </div>

      {/* ── Card info ────────────────────────────────────── */}
      <div className="card-body">
        <h3 className="card-name">{whiskey.name}</h3>

        {/* Rating row: number + stars + count */}
        <div className="card-rating-row">
          <span className="card-rating-num">{hasRating ? whiskey.rating_avg.toFixed(1) : '—'}</span>
          <span className="card-stars" aria-label={`${whiskey.rating_avg?.toFixed(1) || 0} out of 5`}>
            {'★'.repeat(Math.round(whiskey.rating_avg || 0))}
            <span className="card-stars-empty">{'★'.repeat(Math.max(0, 5 - Math.round(whiskey.rating_avg || 0)))}</span>
          </span>
          <span className="card-rating-count">
            {whiskey.rating_count > 0 ? `${whiskey.rating_count} ratings` : 'No ratings yet'}
          </span>
        </div>

        {/* Price + match */}
        <div className="card-bottom-row">
          {whiskey.price_usd ? (
            <span className={`card-price${whiskey.price_is_estimated ? ' card-price--estimated' : ''}`}>
              {whiskey.price_is_estimated ? '~' : ''}${Number(whiskey.price_usd).toFixed(2)}
              {whiskey.price_is_estimated && <span className="est-label">Est.</span>}
            </span>
          ) : (
            <span className="card-price card-price--na">Price N/A</span>
          )}
          {score != null && (
            <span className="card-match">
              <span className="card-match-num">{Math.round(score * 100)}%</span> Match
            </span>
          )}
        </div>
      </div>
    </Link>
  )
})
