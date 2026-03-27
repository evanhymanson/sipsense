import { useState, useEffect } from 'react'
import { api } from '../api/client'

const SOURCE_COLORS = {
  whisky_advocate: '#b8860b',
  jim_murray: '#8b0000',
  wine_enthusiast: '#4b0082',
}

const SOURCE_EMOJI = {
  whisky_advocate: '\u{1F4F0}',
  jim_murray: '\u{1F4D6}',
  wine_enthusiast: '\u{1F377}',
}

export default function CriticScores({ whiskeyId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!whiskeyId) return
    setLoading(true)
    api.getCriticScores(whiskeyId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [whiskeyId])

  if (loading) return null
  if (!data || !data.scores || data.scores.length === 0) return null

  return (
    <div className="critic-scores">
      <h3>Expert Scores</h3>

      {data.avg_critic_score != null && (
        <div className="critic-avg">
          <span className="critic-avg-score">
            {Math.round(data.avg_critic_score)}
          </span>
          <span className="critic-avg-label">avg critic score</span>
        </div>
      )}

      <div className="critic-list">
        {data.scores.map((s) => (
          <div key={s.source} className="critic-card">
            <div className="critic-source">
              <span className="critic-emoji">
                {SOURCE_EMOJI[s.source] || '\u{2B50}'}
              </span>
              <span className="critic-source-name">{s.source_display}</span>
              {s.review_year && (
                <span className="critic-year">{s.review_year}</span>
              )}
            </div>
            <div className="critic-score-row">
              <div
                className="critic-score-badge"
                style={{
                  backgroundColor: SOURCE_COLORS[s.source] || '#555',
                }}
              >
                {s.score}
                <span className="critic-max">/{s.max_score}</span>
              </div>
              <div className="critic-bar-wrap">
                <div
                  className="critic-bar-fill"
                  style={{
                    width: `${s.normalized_score}%`,
                    backgroundColor: SOURCE_COLORS[s.source] || '#555',
                  }}
                />
              </div>
            </div>
            {s.review_text && (
              <p className="critic-review-text">\"{s.review_text}\"</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
