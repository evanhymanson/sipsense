/**
 * Shared star display with half-star support.
 */
export function StarDisplay({ rating, max = 5, className = '' }) {
  const full = Math.floor(rating)
  const hasHalf = rating - full >= 0.25 && rating - full < 0.75
  const empty = max - full - (hasHalf ? 1 : 0)

  return (
    <span className={`star-display ${className}`} aria-label={`${rating.toFixed(1)} out of ${max}`}>
      {'★'.repeat(full)}
      {hasHalf && <span className="star-half-icon">★</span>}
      <span className="star-display-empty">{'★'.repeat(Math.max(0, empty))}</span>
    </span>
  )
}
