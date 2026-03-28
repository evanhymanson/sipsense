import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, isLoggedIn } from '../api/client'
import { getCategoryEmoji } from '../constants'
import './Discover.css'

const CATEGORIES_MAP = [
  { value: 'irish',       label: 'Irish',       x: '22%', y: '15%' },
  { value: 'japanese',    label: 'Japanese',     x: '42%', y: '20%' },
  { value: 'canadian',    label: 'Canadian',     x: '18%', y: '38%' },
  { value: 'single malt', label: 'Single Malt', x: '62%', y: '38%' },
  { value: 'wheat',       label: 'Wheat',        x: '30%', y: '50%' },
  { value: 'bourbon',     label: 'Bourbon',      x: '25%', y: '70%' },
  { value: 'rye',         label: 'Rye',          x: '58%', y: '72%' },
  { value: 'scotch',      label: 'Scotch',       x: '78%', y: '58%' },
]

export default function Discover() {
  const navigate = useNavigate()
  const [daily, setDaily] = useState(null)
  const [dailyCollapsed, setDailyCollapsed] = useState(false)
  const [dailyError, setDailyError] = useState(false)
  const [dailyBuyLinks, setDailyBuyLinks] = useState(null)

  // Streak
  const [streak, setStreak] = useState(null)

  // Quiz
  const [quizQ, setQuizQ] = useState(null)
  const [quizAnswer, setQuizAnswer] = useState(null)
  const [quizResult, setQuizResult] = useState(null)
  const [quizLoading, setQuizLoading] = useState(false)

  // Challenges
  const [challenges, setChallenges] = useState([])
  const [joiningSlug, setJoiningSlug] = useState(null)

  // Load daily discovery + buy links
  useEffect(() => {
    api.getDailyDiscovery()
      .then(data => {
        setDaily(data)
        if (data?.whiskey?.id) {
          api.getBuyLinks(data.whiskey.id)
            .then(setDailyBuyLinks)
            .catch(() => {})
        }
      })
      .catch(() => setDailyError(true))
  }, [])

  // Load streak + challenges for logged-in users
  useEffect(() => {
    if (!isLoggedIn()) return
    api.getStreak().then(setStreak).catch(() => {})
    api.getChallenges().then(setChallenges).catch(() => {})
  }, [])

  // Load quiz question
  useEffect(() => {
    api.getDailyQuizQuestion().then(setQuizQ).catch(() => {})
  }, [])

  function handleQuizAnswer(answerId) {
    if (!quizQ || quizResult) return
    setQuizLoading(true)
    api.submitDailyQuizAnswer(quizQ.correct_id, answerId)
      .then(res => {
        setQuizResult(res)
        // Refresh streak if logged in
        if (isLoggedIn()) api.getStreak().then(setStreak).catch(() => {})
      })
      .catch(() => setQuizResult({ correct: false, error: true }))
      .finally(() => setQuizLoading(false))
  }

  async function handleJoinChallenge(slug) {
    setJoiningSlug(slug)
    try {
      await api.joinChallenge(slug)
      const updated = await api.getChallenges()
      setChallenges(updated)
    } catch { /* already joined or error */ }
    finally { setJoiningSlug(null) }
  }

  const dailyWhiskey = daily?.whiskey

  return (
    <div className="discover-page">
      {/* ── Daily Discovery Banner ─────────────────────────────── */}
      {dailyWhiskey && (
        <div className={`discover-daily ${dailyCollapsed ? 'discover-daily--collapsed' : ''}`}>
          <div className="discover-daily-main" role="button" tabIndex={0} aria-label={`View ${dailyWhiskey.name}`} onClick={() => navigate(`/whiskey/${dailyWhiskey.id}`)} onKeyDown={e => e.key === 'Enter' && navigate(`/whiskey/${dailyWhiskey.id}`)}>
            <span className="discover-daily-badge">Today's Discovery</span>
            <span className="discover-daily-name">{dailyWhiskey.name}</span>
            <span className="discover-daily-meta">
              {dailyWhiskey.distillery} · {dailyWhiskey.category}
              {dailyWhiskey.price_usd && ` · ${dailyWhiskey.price_is_estimated ? '~' : ''}$${Number(dailyWhiskey.price_usd).toFixed(2)}${dailyWhiskey.price_is_estimated ? ' Est.' : ''}`}
            </span>
          </div>
          {!dailyCollapsed && dailyBuyLinks?.links?.[0] && (
            <a
              href={dailyBuyLinks.links[0].url}
              target="_blank"
              rel="noopener noreferrer"
              className="discover-daily-buy"
              onClick={(e) => {
                e.stopPropagation()
                api.recordAffiliateClick({
                  whiskey_id: dailyWhiskey.id,
                  retailer: dailyBuyLinks.links[0].retailer,
                  source: 'daily_discovery',
                }).catch(() => {})
              }}
            >
              Buy at {dailyBuyLinks.links[0].retailer} &rarr;
            </a>
          )}
          {!dailyCollapsed && daily.tasting_tip && (
            <div className="discover-daily-tip">
              <span>Tasting Tip:</span> {daily.tasting_tip}
            </div>
          )}
          <button className="discover-daily-toggle" onClick={(e) => { e.stopPropagation(); setDailyCollapsed(!dailyCollapsed) }}>
            {dailyCollapsed ? '▼' : '▲'}
          </button>
        </div>
      )}
      {dailyError && !dailyWhiskey && (
        <p className="page-subtitle" style={{ textAlign: 'center', padding: '0.5rem' }}>Could not load today's discovery.</p>
      )}

      {/* ── Streak Counter ────────────────────────────────────── */}
      {isLoggedIn() && streak && (
        <div className="discover-streak">
          <span className="discover-streak-fire">{streak.current_streak > 0 ? '🔥' : '💤'}</span>
          <span className="discover-streak-text">
            {streak.current_streak > 0
              ? `Day ${streak.current_streak} streak!`
              : 'Start a streak — check in today!'
            }
          </span>
          {streak.longest_streak > streak.current_streak && (
            <span className="discover-streak-best">Best: {streak.longest_streak}</span>
          )}
        </div>
      )}

      {/* ── Page Header ──────────────────────────────────────── */}
      <div className="discover-graph-header">
        <h1>Discover</h1>
        <p>Explore the world of whiskey by style, flavor, and more.</p>
      </div>

      {/* ── Daily Taste Quiz ──────────────────────────────────── */}
      {quizQ && (
        <div className="discover-quiz-section">
          <h2>Test Your Palate</h2>
          <p className="discover-quiz-subtitle">Can you identify the whiskey from its flavor profile?</p>
          <div className="discover-quiz-clues">
            {quizQ.flavor_clues?.map((clue, i) => (
              <span key={i} className="discover-quiz-clue">{clue}</span>
            ))}
            {quizQ.category_hint && <span className="discover-quiz-clue">{quizQ.category_hint}</span>}
          </div>
          <div className="discover-quiz-options">
            {quizQ.options?.map(opt => (
              <button
                key={opt.id}
                className={`discover-quiz-option${
                  quizResult
                    ? opt.id === quizQ.correct_id
                      ? ' discover-quiz-option--correct'
                      : quizAnswer === opt.id
                        ? ' discover-quiz-option--wrong'
                        : ''
                    : ''
                }`}
                disabled={!!quizResult || quizLoading}
                onClick={() => { setQuizAnswer(opt.id); handleQuizAnswer(opt.id) }}
              >
                <span className="dqo-name">{opt.name}</span>
                <span className="dqo-distillery">{opt.distillery}</span>
              </button>
            ))}
          </div>
          {quizResult && (
            <div className={`discover-quiz-result ${quizResult.correct ? 'discover-quiz-result--correct' : 'discover-quiz-result--wrong'}`}>
              {quizResult.correct ? 'Correct!' : 'Not quite!'}{' '}
              {quizResult.correct_whiskey && (
                <span>It was <strong>{quizResult.correct_whiskey.name}</strong> — {quizResult.correct_whiskey.category}</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Active Challenges ─────────────────────────────────── */}
      {challenges.length > 0 && (
        <div className="discover-challenges-section">
          <h2>Active Challenges</h2>
          <div className="discover-challenges-grid">
            {challenges.map(ch => (
              <div key={ch.slug} className="discover-challenge-card">
                <div className="discover-challenge-header">
                  <span className="discover-challenge-emoji">{ch.image_emoji}</span>
                  <div>
                    <strong>{ch.title}</strong>
                    {ch.description && <p className="discover-challenge-desc">{ch.description}</p>}
                  </div>
                </div>
                {ch.joined ? (
                  <div className="discover-challenge-progress">
                    <div className="discover-challenge-bar">
                      <div className="discover-challenge-fill" style={{ width: `${Math.min(100, (ch.progress / ch.goal_count) * 100)}%` }} />
                    </div>
                    <span className="discover-challenge-count">
                      {ch.completed ? 'Complete!' : `${ch.progress}/${ch.goal_count}`}
                    </span>
                  </div>
                ) : (
                  <button
                    className="discover-challenge-join"
                    disabled={joiningSlug === ch.slug || !isLoggedIn()}
                    onClick={() => handleJoinChallenge(ch.slug)}
                  >
                    {isLoggedIn() ? 'Join Challenge' : 'Sign in to join'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Whiskey Compass ─────────────────────────────────── */}
      <div className="category-map-section">
        <h2>Whiskey Compass</h2>
        <p>Tap a style to explore bottles in that world</p>
        <div className="category-map">
          <span className="cm-axis cm-axis--top">Light</span>
          <span className="cm-axis cm-axis--bottom">Bold</span>
          <span className="cm-axis cm-axis--left">Sweet</span>
          <span className="cm-axis cm-axis--right">Smoky</span>
          <div className="cm-crosshair-h" />
          <div className="cm-crosshair-v" />
          {CATEGORIES_MAP.map(cat => (
            <button
              key={cat.value}
              className="cm-node"
              style={{ left: cat.x, top: cat.y }}
              onClick={() => navigate(`/?category=${encodeURIComponent(cat.value)}`)}
            >
              <span className="cm-node-emoji">{getCategoryEmoji(cat.value)}</span>
              <span className="cm-node-label">{cat.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Quick Access Cards ─────────────────────────────────── */}
      <div className="discover-quick">
        <h2>Quick Access</h2>
        <div className="discover-quick-grid">
          <button className="discover-quick-card" onClick={() => navigate('/quiz')}>
            <span className="dqc-emoji">🎯</span>
            <span className="dqc-label">Taste Quiz</span>
            <span className="dqc-desc">Find your perfect match</span>
          </button>
          <button className="discover-quick-card" onClick={() => navigate('/')}>
            <span className="dqc-emoji">🔍</span>
            <span className="dqc-label">Browse All</span>
            <span className="dqc-desc">Explore the full catalog</span>
          </button>
        </div>
      </div>
    </div>
  )
}
