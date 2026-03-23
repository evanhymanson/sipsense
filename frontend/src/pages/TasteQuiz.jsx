import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api, isLoggedIn } from '../api/client'
import './TasteQuiz.css'

const QUESTIONS = [
  {
    id: 'body',
    emoji: '☕',
    question: 'How do you take your coffee?',
    subtitle: 'This helps us gauge your intensity preference',
    options: [
      { emoji: '🥛', label: 'Light & mild', desc: 'Lattes, cappuccinos', value: 'light' },
      { emoji: '☕', label: 'Medium', desc: 'Drip coffee, just right', value: 'medium' },
      { emoji: '⚡', label: 'Strong & bold', desc: 'Espresso, dark roast', value: 'full' },
    ],
  },
  {
    id: 'chocolate',
    emoji: '🍫',
    question: 'Pick your chocolate',
    subtitle: 'Tells us about your sweetness and flavor leanings',
    options: [
      { emoji: '🤍', label: 'White chocolate', desc: 'Creamy & sweet', value: ['sweet', 'vanilla', 'caramel'] },
      { emoji: '🟤', label: 'Milk chocolate', desc: 'Balanced sweetness', value: ['sweet', 'caramel', 'honey'] },
      { emoji: '🖤', label: 'Dark chocolate', desc: 'Rich & intense', value: ['chocolate', 'oak', 'spicy'] },
      { emoji: '🍋', label: 'Not a chocolate person', desc: 'Prefer fruity or fresh', value: ['fruity', 'floral', 'citrus'] },
    ],
  },
  {
    id: 'smokiness',
    emoji: '🔥',
    question: 'At a barbecue, what draws you in?',
    subtitle: 'Smoke is a big divider in the whiskey world',
    options: [
      { emoji: '🥗', label: 'Fresh salads and fruit', desc: 'Keep it light', value: 'none' },
      { emoji: '🍗', label: 'Grilled chicken', desc: 'Some char, not too much', value: 'light' },
      { emoji: '🥩', label: 'Low & slow brisket', desc: 'Give me all the smoke', value: 'heavy' },
    ],
  },
  {
    id: 'dessert',
    emoji: '🍰',
    question: 'What dessert would you reach for?',
    subtitle: 'Helps us fine-tune your flavor profile',
    options: [
      { emoji: '🍮', label: 'Creme brulee', desc: 'Vanilla custard, caramelized sugar', value: ['vanilla', 'honey'] },
      { emoji: '🥧', label: 'Apple pie', desc: 'Baked fruit, warm spices', value: ['fruity', 'spicy'] },
      { emoji: '🍫', label: 'Salted caramel brownies', desc: 'Rich, gooey, sweet-salty', value: ['caramel', 'chocolate'] },
      { emoji: '🥜', label: 'Nuts & dried fruit', desc: 'Toasted, chewy, earthy', value: ['nutty', 'fruity'] },
    ],
  },
  {
    id: 'budget',
    emoji: '💰',
    question: "What's your spending comfort zone?",
    subtitle: "There's great whiskey at every price point",
    options: [
      { emoji: '🏷️', label: 'Under $30', desc: 'Great starter bottles', value: 'budget' },
      { emoji: '👌', label: '$30 - $70', desc: 'The sweet spot', value: 'mid' },
      { emoji: '🎁', label: '$70 - $150', desc: 'For something special', value: 'premium' },
      { emoji: '✨', label: "Sky's the limit", desc: 'Show me the best', value: 'luxury' },
    ],
  },
  {
    id: 'style',
    emoji: '🌍',
    question: 'Any world of whiskey calling to you?',
    subtitle: "Don't worry, you can explore them all later",
    options: [
      { emoji: '🥃', label: 'American classics', desc: 'Bourbon — sweet, warm, bold', value: 'bourbon' },
      { emoji: '🏔', label: 'Scottish tradition', desc: 'Scotch — malty, complex, smoky', value: 'scotch' },
      { emoji: '☘️', label: 'Smooth Irish', desc: 'Irish — light, approachable, clean', value: 'irish' },
      { emoji: '⛩', label: 'Japanese craft', desc: 'Refined, delicate, balanced', value: 'japanese' },
      { emoji: '🌾', label: 'Spicy rye', desc: 'Rye — peppery, bold, dry', value: 'rye' },
      { emoji: '🎲', label: 'Surprise me!', desc: "Let the quiz decide", value: 'any' },
    ],
  },
]

function buildQuizPayload(answers) {
  const allFlavors = [
    ...(answers.chocolate || []),
    ...(answers.dessert || []),
  ]
  const uniqueFlavors = [...new Set(allFlavors)]

  return {
    flavors: uniqueFlavors,
    smokiness: answers.smokiness || 'none',
    body: answers.body || 'medium',
    budget: answers.budget || 'mid',
    style: answers.style || 'any',
  }
}

export default function TasteQuiz() {
  const navigate = useNavigate()

  useEffect(() => {
    if (!isLoggedIn()) navigate('/onboarding', { replace: true })
  }, [navigate])

  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState({})
  const [selected, setSelected] = useState(null) // for brief highlight before advance
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const totalQuestions = QUESTIONS.length
  const isResults = step >= totalQuestions

  function selectAnswer(questionId, value) {
    setSelected(value)
    const updated = { ...answers, [questionId]: value }
    setAnswers(updated)

    setTimeout(() => {
      setSelected(null)
      if (step < totalQuestions - 1) {
        setStep(step + 1)
      } else {
        submitQuiz(updated)
      }
    }, 350)
  }

  async function submitQuiz(finalAnswers) {
    setStep(totalQuestions) // move to results view
    setLoading(true)
    setError(null)
    try {
      const payload = buildQuizPayload(finalAnswers)
      const recs = await api.submitQuiz(payload, 5)
      setResults(recs)
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  function retake() {
    setStep(0)
    setAnswers({})
    setResults(null)
    setError(null)
  }

  // Results screen
  if (isResults) {
    return (
      <div className="taste-quiz">
        <div className="tq-card">
          <span className="tq-emoji">🥃</span>
          <h1 className="tq-results-title">Your Starter Bottles</h1>
          <p className="tq-results-subtitle">
            Based on your taste preferences, we think you'll love these
          </p>

          {loading && <p className="tq-loading">Finding your perfect matches...</p>}
          {error && (
            <div className="tq-error">
              <p>{error}</p>
              <button className="retry-btn" style={{ marginTop: '0.75rem' }} onClick={() => submitQuiz(answers)}>Retry</button>
            </div>
          )}

          {results && results.length > 0 && (
            <div className="tq-results-list">
              {results.map((rec) => (
                <Link
                  key={rec.whiskey.id}
                  to={`/whiskey/${rec.whiskey.id}`}
                  className="tq-result-item"
                >
                  <div className="tq-result-name">{rec.whiskey.name}</div>
                  <div className="tq-result-meta">
                    {rec.whiskey.distillery} · {rec.whiskey.category}
                    {rec.whiskey.price_usd && ` · $${Number(rec.whiskey.price_usd).toFixed(2)}`}
                  </div>
                  <div className="tq-result-reason">{rec.reason}</div>
                </Link>
              ))}
            </div>
          )}

          {!loading && (
            <>
              <button className="tq-cta" onClick={() => navigate('/')}>
                Start Exploring
              </button>
              <button className="tq-retake" onClick={retake}>
                Retake Quiz
              </button>
            </>
          )}
        </div>
      </div>
    )
  }

  // Question screen
  const q = QUESTIONS[step]

  return (
    <div className="taste-quiz">
      <div className="tq-card">
        {/* Progress dots */}
        <div className="tq-progress" role="progressbar" aria-valuenow={step + 1} aria-valuemin={1} aria-valuemax={totalQuestions} aria-label={`Step ${step + 1} of ${totalQuestions}`}>
          {QUESTIONS.map((_, i) => (
            <div
              key={i}
              className={`tq-dot ${i < step ? 'tq-dot--done' : ''} ${i === step ? 'tq-dot--active' : ''}`}
              aria-label={`Step ${i + 1}${i < step ? ' completed' : i === step ? ' current' : ''}`}
            />
          ))}
        </div>

        <span className="tq-emoji">{q.emoji}</span>
        <h2 className="tq-question">{q.question}</h2>
        <p className="tq-subtitle">{q.subtitle}</p>

        <div className="tq-options">
          {q.options.map((opt) => {
            const isSelected = selected !== null &&
              JSON.stringify(selected) === JSON.stringify(opt.value)
            return (
              <button
                key={opt.label}
                className={`tq-option ${isSelected ? 'tq-option--selected' : ''}`}
                onClick={() => selectAnswer(q.id, opt.value)}
                disabled={selected !== null}
              >
                <span className="tq-option-emoji">{opt.emoji}</span>
                <span className="tq-option-text">
                  <span className="tq-option-label">{opt.label}</span>
                  <span className="tq-option-desc">{opt.desc}</span>
                </span>
              </button>
            )
          })}
        </div>

        {step > 0 && (
          <button className="tq-back" onClick={() => { setSelected(null); setStep(step - 1) }}>
            ← Back
          </button>
        )}
      </div>
    </div>
  )
}
