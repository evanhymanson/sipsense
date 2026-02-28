import { useState, useEffect } from 'react'
import { api } from '../api/client'
import BadgeGrid from '../components/BadgeGrid'
import './MyPalate.css'


function StatCard({ label, value, sub }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

function BarRow({ label, count, max }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="bar-count">{count}</span>
    </div>
  )
}

function ScorePips({ score }) {
  return (
    <div className="score-pips">
      {[1, 2, 3, 4, 5].map(n => (
        <span key={n} className={`pip ${n <= Math.round(score) ? 'filled' : ''}`}>&#9679;</span>
      ))}
    </div>
  )
}

function RatingRow({ entry }) {
  const { whiskey, score, notes, created_at } = entry
  const date = created_at ? new Date(created_at).toLocaleDateString() : ''
  return (
    <div className="rating-row">
      <div className="rating-row-info">
        <span className="rating-name">{whiskey.name}</span>
        <span className="rating-dist">{whiskey.distillery} &middot; {whiskey.category}</span>
        {notes && <span className="rating-notes">&ldquo;{notes}&rdquo;</span>}
      </div>
      <div className="rating-row-right">
        <ScorePips score={score} />
        <span className="rating-score">{score.toFixed(1)}</span>
        {date && <span className="rating-date">{date}</span>}
      </div>
    </div>
  )
}

function FavCard({ whiskey }) {
  return (
    <div className="fav-card">
      <div className="fav-name">{whiskey.name}</div>
      <div className="fav-dist">{whiskey.distillery}</div>
      <div className="fav-meta">
        <span>{whiskey.category}</span>
        {whiskey.price_usd && <span>${whiskey.price_usd}</span>}
      </div>
    </div>
  )
}

export default function MyPalate() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [aiSummary, setAiSummary] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)

  useEffect(() => {
    api.getPalate()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function loadAiSummary() {
    setAiLoading(true)
    try {
      const result = await api.getAiPalateSummary()
      setAiSummary(result.narrative)
    } catch {
      setAiSummary(null)
    } finally {
      setAiLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="palate-page">
        <div className="palate-loading">Loading your palate&hellip;</div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="palate-page">
        <p className="palate-empty">Could not load your palate. Try rating some whiskeys first.</p>
      </div>
    )
  }

  const { narrative, stats, top_categories, top_flavors, recent_ratings, favorites, badges } = data
  const maxCat = top_categories[0]?.count || 1
  const maxFlavor = top_flavors[0]?.count || 1

  const isEmpty = stats.total_rated === 0 && stats.total_favorites === 0

  return (
    <div className="palate-page">
      <div className="palate-hero">
        <h1>My Palate</h1>
        <p className="palate-narrative">{aiSummary || narrative}</p>
        {!isEmpty && !aiSummary && !aiLoading && (
          <button className="ai-summary-btn" onClick={loadAiSummary}>
            Generate AI Portrait
          </button>
        )}
        {aiLoading && <p className="ai-summary-loading">Writing your taste portrait...</p>}
      </div>

      {isEmpty ? (
        <div className="palate-empty-state">
          <div className="empty-glass">{'\u{1F943}'}</div>
          <h2>Your palate profile is empty</h2>
          <p>
            Rate some whiskeys in Browse or via the chat assistant to start
            building your taste portrait.
          </p>
        </div>
      ) : (
        <>
          {/* Stats */}
          <div className="stats-row">
            <StatCard label="Bottles Rated" value={stats.total_rated} />
            <StatCard label="Favorites Saved" value={stats.total_favorites} />
            <StatCard
              label="Avg Rating"
              value={stats.avg_score > 0 ? `${stats.avg_score.toFixed(1)} / 5` : '\u2014'}
            />
            <StatCard
              label="Avg Price"
              value={stats.avg_price > 0 ? `$${stats.avg_price.toFixed(0)}` : '\u2014'}
              sub="per bottle"
            />
          </div>

          {/* Badges */}
          {badges?.length > 0 && (
            <div className="palate-section full-width">
              <h2>Your Badges</h2>
              <BadgeGrid badges={badges} showDate />
            </div>
          )}

          {/* Two-column breakdown */}
          <div className="palate-columns">
            {top_categories.length > 0 && (
              <div className="palate-section">
                <h2>Styles You Reach For</h2>
                <div className="bars">
                  {top_categories.map(c => (
                    <BarRow key={c.name} label={c.name} count={c.count} max={maxCat} />
                  ))}
                </div>
              </div>
            )}

            {top_flavors.length > 0 && (
              <div className="palate-section">
                <h2>Flavor Fingerprint</h2>
                <div className="flavor-cloud">
                  {top_flavors.map((f, i) => (
                    <span
                      key={f.name}
                      className="cloud-tag"
                      style={{ fontSize: `${1.1 - i * 0.07}rem`, opacity: 1 - i * 0.06 }}
                    >
                      {f.name}
                    </span>
                  ))}
                </div>
                <div className="bars mt-bar">
                  {top_flavors.slice(0, 6).map(f => (
                    <BarRow key={f.name} label={f.name} count={f.count} max={maxFlavor} />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Recent ratings */}
          {recent_ratings.length > 0 && (
            <div className="palate-section full-width">
              <h2>Your Ratings</h2>
              <div className="ratings-list">
                {recent_ratings.map((r, i) => (
                  <RatingRow key={i} entry={r} />
                ))}
              </div>
            </div>
          )}

          {/* Favorites */}
          {favorites.length > 0 && (
            <div className="palate-section full-width">
              <h2>Saved Favorites</h2>
              <div className="fav-grid">
                {favorites.map(w => <FavCard key={w.id} whiskey={w} />)}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
