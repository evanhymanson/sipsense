export default function UserLevel({ level, showProgress = false }) {
  if (!level) return null

  return (
    <div className="user-level">
      <span className="user-level-badge">
        <span className="user-level-emoji">{level.emoji}</span>
        <span className="user-level-name">{level.name}</span>
      </span>
      {showProgress && level.next_level_name && (
        <div className="user-level-progress">
          <div className="user-level-progress-bar">
            <div
              className="user-level-progress-fill"
              style={{ width: `${level.progress_pct}%` }}
            />
          </div>
          <span className="user-level-progress-text">
            {level.points} pts — {level.next_level_name} at{' '}
            {level.next_level_points}
          </span>
        </div>
      )}
    </div>
  )
}
