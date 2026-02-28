import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import './BlindTasting.css'

const DIFFICULTIES = [
  { key: 'easy', label: 'Easy', desc: 'Most clues shown', points: 10 },
  { key: 'medium', label: 'Medium', desc: 'Fewer clues', points: 25 },
  { key: 'hard', label: 'Hard', desc: 'Minimal clues', points: 50 },
]

export default function BlindTasting() {
  const [difficulty, setDifficulty] = useState('easy')
  const [challenge, setChallenge] = useState(null)
  const [guess, setGuess] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [totalPoints, setTotalPoints] = useState(0)
  const [round, setRound] = useState(0)
  const navigate = useNavigate()

  async function startChallenge() {
    setLoading(true)
    setError(null)
    setResult(null)
    setGuess(null)
    try {
      const data = await api.getChallenge(difficulty)
      setChallenge(data)
      setRound((r) => r + 1)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function submitGuess() {
    if (!guess || !challenge) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.submitGuess({
        whiskey_id: challenge.challenge_id,
        guess_category: guess,
        difficulty,
      })
      setResult(data)
      setTotalPoints((p) => p + data.points)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // ── No challenge yet — show intro ──
  if (!challenge) {
    return (
      <div className="blind-page">
        <h1>Blind Tasting Challenge</h1>
        <p className="blind-subtitle">
          Can you identify a whiskey from clues alone? Test your palate knowledge!
        </p>

        <div className="blind-difficulty-picker">
          <h3>Choose your difficulty</h3>
          <div className="difficulty-options">
            {DIFFICULTIES.map((d) => (
              <button
                key={d.key}
                className={`difficulty-btn ${difficulty === d.key ? 'difficulty-btn--active' : ''}`}
                onClick={() => setDifficulty(d.key)}
              >
                <span className="difficulty-label">{d.label}</span>
                <span className="difficulty-desc">{d.desc}</span>
                <span className="difficulty-points">{d.points} pts</span>
              </button>
            ))}
          </div>
        </div>

        <button className="blind-start-btn" onClick={startChallenge} disabled={loading}>
          {loading ? 'Loading...' : 'Start Challenge'}
        </button>

        {error && <p className="status error">{error}</p>}
      </div>
    )
  }

  const clues = challenge.clues

  // ── Active challenge ──
  return (
    <div className="blind-page">
      <div className="blind-header">
        <div className="blind-round">Round {round}</div>
        <div className="blind-score">Score: {totalPoints} pts</div>
      </div>

      {!result ? (
        <>
          <div className="blind-clue-card">
            <h2>Mystery Whiskey</h2>
            <p className="blind-difficulty-badge">{difficulty.toUpperCase()} — {clues.points} pts</p>

            <div className="blind-clues">
              {clues.abv && (
                <div className="clue-item">
                  <span className="clue-label">ABV</span>
                  <span className="clue-value">{clues.abv}%</span>
                </div>
              )}
              {clues.age && (
                <div className="clue-item">
                  <span className="clue-label">Age</span>
                  <span className="clue-value">{clues.age} years</span>
                </div>
              )}
              {clues.price_range && (
                <div className="clue-item">
                  <span className="clue-label">Price Range</span>
                  <span className="clue-value">{clues.price_range}</span>
                </div>
              )}
              {clues.flavors?.length > 0 && (
                <div className="clue-item clue-item--wide">
                  <span className="clue-label">Tasting Notes</span>
                  <div className="clue-flavors">
                    {clues.flavors.map((f) => (
                      <span key={f} className="clue-flavor-tag">{f}</span>
                    ))}
                  </div>
                </div>
              )}
              {clues.description_hint && (
                <div className="clue-item clue-item--wide">
                  <span className="clue-label">Description</span>
                  <p className="clue-description">{clues.description_hint}</p>
                </div>
              )}
            </div>
          </div>

          <div className="blind-guess-section">
            <h3>What category is this whiskey?</h3>
            <div className="guess-options">
              {clues.guess_options?.map((opt) => (
                <button
                  key={opt}
                  className={`guess-btn ${guess === opt ? 'guess-btn--selected' : ''}`}
                  onClick={() => setGuess(opt)}
                >
                  {opt}
                </button>
              ))}
            </div>
            <button
              className="blind-submit-btn"
              onClick={submitGuess}
              disabled={!guess || loading}
            >
              {loading ? 'Checking...' : 'Submit Guess'}
            </button>
          </div>
        </>
      ) : (
        <div className={`blind-result ${result.correct ? 'blind-result--correct' : result.partial ? 'blind-result--partial' : 'blind-result--wrong'}`}>
          <div className="result-icon">
            {result.correct ? '🎯' : result.partial ? '🤏' : '😅'}
          </div>
          <p className="result-points">+{result.points} points</p>
          <p className="result-message">{result.message}</p>

          <div className="result-reveal">
            <h3>The Reveal</h3>
            <div className="reveal-card" onClick={() => navigate(`/whiskey/${result.reveal.id}`)}>
              <span className="reveal-category">{result.reveal.category}</span>
              <span className="reveal-name">{result.reveal.name}</span>
              <span className="reveal-distillery">{result.reveal.distillery}</span>
              <div className="reveal-meta">
                {result.reveal.region && <span>{result.reveal.region}</span>}
                {result.reveal.age && <span>{result.reveal.age}yr</span>}
                <span>{result.reveal.abv}% ABV</span>
                {result.reveal.price_usd && <span>${result.reveal.price_usd}</span>}
              </div>
            </div>
          </div>

          {result.fun_fact && (
            <div className="result-fun-fact">
              <span className="fun-fact-label">Did you know?</span>
              <p>{result.fun_fact}</p>
            </div>
          )}

          <div className="result-actions">
            <button onClick={startChallenge} disabled={loading}>
              {loading ? 'Loading...' : 'Next Challenge'}
            </button>
            <button className="action-secondary" onClick={() => { setChallenge(null); setResult(null) }}>
              Change Difficulty
            </button>
          </div>
        </div>
      )}

      {error && <p className="status error">{error}</p>}
    </div>
  )
}
