import './BadgeGrid.css'

export default function BadgeGrid({ badges, showDate = false }) {
  if (!badges || badges.length === 0) {
    return <p className="badge-grid-empty">No badges earned yet. Keep sipping!</p>
  }

  return (
    <div className="badge-grid">
      {badges.map((b) => {
        // Supports both flat (from palate) and nested (UserBadgeRead) shapes
        const badge = b.badge || b
        const awardedAt = b.awarded_at || b.awardedAt
        return (
          <div key={badge.slug} className="badge-item" title={badge.description}>
            <span className="badge-emoji">{badge.emoji}</span>
            <div className="badge-info">
              <span className="badge-name">{badge.name}</span>
              <span className="badge-desc">{badge.description}</span>
              {showDate && awardedAt && (
                <span className="badge-date">
                  {new Date(awardedAt).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
