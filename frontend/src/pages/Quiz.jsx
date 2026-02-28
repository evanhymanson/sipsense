import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'
import './Quiz.css'

const QUESTIONS = [
  {
    id: 'flavors',
    question: 'What flavors do you love?',
    subtitle: 'Pick all that apply',
    multi: true,
    options: [
      { value: 'sweet',     label: '🍯 Sweet' },
      { value: 'fruity',    label: '🍎 Fruity' },
      { value: 'spicy',     label: '🌶️ Spicy' },
      { value: 'vanilla',   label: '🌿 Vanilla' },
      { value: 'caramel',   label: '🍮 Caramel' },
      { value: 'citrus',    label: '🍋 Citrus' },
      { value: 'honey',     label: '🐝 Honey' },
      { value: 'oak',       label: '🪵 Oak' },
      { value: 'floral',    label: '🌸 Floral' },
      { value: 'nutty',     label: '🌰 Nutty' },
    ],
  },
  {
    id: 'smokiness',
    question: 'How smoky do you like it?',
    subtitle: 'Choose one',
    multi: false,
    options: [
      { value: 'none',  label: '🌊 No smoke',        desc: 'Clean and smooth' },
      { value: 'light', label: '🌫️ Just a hint',     desc: 'Subtle complexity' },
      { value: 'heavy', label: '🔥 Bring the peat',  desc: 'Bold campfire character' },
    ],
  },
  {
    id: 'body',
    question: 'How bold should it be?',
    subtitle: 'Choose one',
    multi: false,
    options: [
      { value: 'light',  label: '🥤 Light & easy',    desc: 'Approachable, smooth sipping' },
      { value: 'medium', label: '🥃 Medium-bodied',   desc: 'Balanced and versatile' },
      { value: 'full',   label: '💪 Bold & full',     desc: 'Rich, warming, complex' },
    ],
  },
  {
    id: 'budget',
    question: "What's your budget per bottle?",
    subtitle: 'Choose one',
    multi: false,
    options: [
      { value: 'budget',  label: '💵 Under $30',   desc: 'Great everyday sippers' },
      { value: 'mid',     label: '💰 $30–$80',     desc: 'The sweet spot for quality' },
      { value: 'premium', label: '💎 $80–$200',    desc: 'Special occasion bottles' },
      { value: 'luxury',  label: '🏆 $200+',       desc: 'No limits, just greatness' },
    ],
  },
  {
    id: 'style',
    question: 'Any style preference?',
    subtitle: 'Choose one',
    multi: false,
    options: [
      { value: 'bourbon',  label: '🇺🇸 Bourbon',      desc: 'American oak sweetness' },
      { value: 'scotch',   label: '🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotch',      desc: 'Complex and refined' },
      { value: 'irish',    label: '☘️ Irish',         desc: 'Smooth triple-distilled' },
      { value: 'japanese', label: '🇯🇵 Japanese',     desc: 'Delicate and precise' },
      { value: 'any',      label: '🎲 Surprise me!', desc: "Open to anything" },
    ],
  },
]

const EMPTY = { flavors: [], smokiness: null, body: null, budget: null, style: null }

export default function Quiz() {
  const navigate              = useNavigate()
  const [step, setStep]       = useState(0)
  const [answers, setAnswers] = useState(EMPTY)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  const q             = QUESTIONS[step]
  const currentAnswer = answers[q?.id]
  const canProceed    = q?.multi ? currentAnswer?.length > 0 : currentAnswer !== null

  function toggleFlavor(value) {
    setAnswers(a => ({
      ...a,
      flavors: a.flavors.includes(value)
        ? a.flavors.filter(f => f !== value)
        : [...a.flavors, value],
    }))
  }

  function selectSingle(id, value) {
    setAnswers(a => ({ ...a, [id]: value }))
  }

  async function handleNext() {
    if (step < QUESTIONS.length - 1) {
      setStep(s => s + 1)
    } else {
      setLoading(true)
      setError(null)
      try {
        const data = await api.submitQuiz({
          flavors:   answers.flavors,
          smokiness: answers.smokiness,
          body:      answers.body,
          budget:    answers.budget,
          style:     answers.style,
        })
        setResults(data)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
  }

  function restart() {
    setStep(0)
    setAnswers(EMPTY)
    setResults(null)
    setError(null)
  }

  // ── Results ───────────────────────────────────────────────────────────────
  if (results) {
    return (
      <div className="quiz-container">
        <div className="quiz-results-header">
          <h1>🥃 Your Perfect Matches</h1>
          <p>Based on your taste profile, we found these for you.</p>
          <div className="quiz-results-actions">
            <button className="quiz-restart-btn" onClick={restart}>Retake Quiz</button>
            <button className="quiz-explore-btn" onClick={() => navigate('/')}>Start Exploring →</button>
          </div>
        </div>
        <div className="quiz-results-grid">
          {results.map(({ whiskey, score, reason }) => (
            <div key={whiskey.id} className="quiz-result-card">
              <WhiskeyCard whiskey={whiskey} score={score} />
              <div className="quiz-reason">{reason}</div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // ── Loading ───────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="quiz-container quiz-loading">
        <div className="quiz-spinner">🥃</div>
        <p>Finding your perfect whiskeys…</p>
      </div>
    )
  }

  // ── Quiz steps ────────────────────────────────────────────────────────────
  return (
    <div className="quiz-container">
      <div className="quiz-progress-bar">
        <div
          className="quiz-progress-fill"
          style={{ width: `${((step + 1) / QUESTIONS.length) * 100}%` }}
        />
      </div>
      <div className="quiz-step-count">Question {step + 1} of {QUESTIONS.length}</div>

      <div className="quiz-question">
        <h1>{q.question}</h1>
        <p className="quiz-subtitle">{q.subtitle}</p>
      </div>

      <div className={`quiz-options ${q.multi ? 'quiz-options-grid' : 'quiz-options-list'}`}>
        {q.options.map(opt => {
          const selected = q.multi
            ? answers.flavors.includes(opt.value)
            : answers[q.id] === opt.value
          return (
            <button
              key={opt.value}
              className={`quiz-option${selected ? ' quiz-option-selected' : ''}`}
              onClick={() =>
                q.multi ? toggleFlavor(opt.value) : selectSingle(q.id, opt.value)
              }
            >
              <span className="quiz-option-label">{opt.label}</span>
              {opt.desc && <span className="quiz-option-desc">{opt.desc}</span>}
            </button>
          )
        })}
      </div>

      {error && <p className="quiz-error">{error}</p>}

      <div className="quiz-footer">
        {step > 0 && (
          <button className="quiz-back-btn" onClick={() => setStep(s => s - 1)}>
            ← Back
          </button>
        )}
        <button
          className="quiz-next-btn"
          disabled={!canProceed}
          onClick={handleNext}
        >
          {step === QUESTIONS.length - 1 ? 'Find My Whiskeys 🥃' : 'Next →'}
        </button>
      </div>
    </div>
  )
}
