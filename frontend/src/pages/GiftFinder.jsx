import { useState } from 'react'
import { api } from '../api/client'
import './GiftFinder.css'

const STEPS = [
  {
    id: 'drinker_level',
    question: 'How would you describe their whiskey experience?',
    options: [
      { value: 'newbie', label: '🌱 Whiskey Newcomer', desc: 'Just starting out, likes smooth and sweet' },
      { value: 'casual', label: '🥃 Casual Drinker', desc: 'Enjoys whiskey socially, has some favorites' },
      { value: 'enthusiast', label: '📚 Enthusiast', desc: 'Explores styles, has opinions on distilleries' },
      { value: 'connoisseur', label: '🎓 Connoisseur', desc: 'Drinks rare bottles, deeply knowledgeable' },
    ],
  },
  {
    id: 'style',
    question: 'What style do they usually reach for?',
    options: [
      { value: 'bourbon', label: '🇺🇸 Bourbon', desc: 'Sweet, vanilla, American oak' },
      { value: 'scotch', label: '🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scotch', desc: 'Complex, often smoky or sherried' },
      { value: 'irish', label: '🍀 Irish', desc: 'Smooth, triple-distilled, easy to love' },
      { value: 'japanese', label: '🗾 Japanese', desc: 'Delicate, precise, beautifully balanced' },
      { value: 'rye', label: '🌾 Rye', desc: 'Spicy, drier finish, bartender favorite' },
      { value: 'any', label: '🌍 Not Sure / Open to Anything', desc: 'Best picks across all styles' },
    ],
  },
  {
    id: 'budget',
    question: 'What is your budget?',
    options: [
      { value: 'budget', label: '$25 – $55', desc: 'Great bottles at everyday prices' },
      { value: 'mid', label: '$55 – $110', desc: 'The sweet spot for gift whiskey' },
      { value: 'premium', label: '$110 – $220', desc: 'A bottle they would not buy themselves' },
      { value: 'luxury', label: '$220+', desc: 'Rare, aged, or allocated — the real deal' },
    ],
  },
  {
    id: 'occasion',
    question: 'Any particular occasion? (optional)',
    optional: true,
    options: [
      { value: 'birthday', label: '🎂 Birthday', desc: '' },
      { value: 'holiday', label: '🎄 Holiday', desc: '' },
      { value: 'host_gift', label: '🏠 Host Gift', desc: '' },
      { value: 'just_because', label: '💛 Just Because', desc: '' },
    ],
  },
]

function OptionCard({ option, selected, onSelect }) {
  return (
    <button
      className={`option-card ${selected ? 'selected' : ''}`}
      onClick={() => onSelect(option.value)}
    >
      <span className="option-label">{option.label}</span>
      {option.desc && <span className="option-desc">{option.desc}</span>}
    </button>
  )
}

function GiftCard({ whiskey }) {
  return (
    <div className="gift-card">
      <div className="gift-card-header">
        <div className="gift-name">{whiskey.name}</div>
        <div className="gift-distillery">{whiskey.distillery}</div>
      </div>
      <div className="gift-meta">
        <span className="gift-category">{whiskey.category}</span>
        {whiskey.region && <span>{whiskey.region}</span>}
        {whiskey.age && <span>{whiskey.age}yr</span>}
        {whiskey.abv && <span>{whiskey.abv}% ABV</span>}
      </div>
      {whiskey.price_usd && (
        <div className="gift-price">${whiskey.price_usd.toFixed(0)}</div>
      )}
      <div className="gift-rating">
        {[1, 2, 3, 4, 5].map(n => (
          <span key={n} className={n <= Math.round(whiskey.rating_avg) ? 'star filled' : 'star'}>★</span>
        ))}
        <span className="rating-num">{whiskey.rating_avg.toFixed(1)}</span>
      </div>
      {whiskey.flavor_profile && (
        <div className="gift-flavors">
          {whiskey.flavor_profile.split(',').slice(0, 4).map(f => (
            <span key={f} className="flavor-chip">{f.trim()}</span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function GiftFinder() {
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState({})
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const currentStep = STEPS[step]

  const select = (value) => {
    const updated = { ...answers, [currentStep.id]: value }
    setAnswers(updated)

    if (step < STEPS.length - 1) {
      setStep(step + 1)
    } else {
      submit(updated)
    }
  }

  const skip = () => {
    const updated = { ...answers }
    delete updated[currentStep.id]
    if (step < STEPS.length - 1) {
      setStep(step + 1)
    } else {
      submit(updated)
    }
  }

  const submit = (finalAnswers) => {
    setLoading(true)
    api.findGift({
      drinker_level: finalAnswers.drinker_level || 'casual',
      style: finalAnswers.style || 'any',
      budget: finalAnswers.budget || 'mid',
      occasion: finalAnswers.occasion || '',
    })
      .then(setResult)
      .finally(() => setLoading(false))
  }

  const reset = () => {
    setStep(0)
    setAnswers({})
    setResult(null)
  }

  if (loading) {
    return (
      <div className="gift-page">
        <div className="gift-loading">
          <div className="loading-gift">🎁</div>
          <p>Finding the perfect bottles…</p>
        </div>
      </div>
    )
  }

  if (result) {
    return (
      <div className="gift-page">
        <div className="gift-results">
          <div className="results-header">
            <h2>🎁 Gift Picks</h2>
            <p className="results-message">{result.message}</p>
          </div>
          <div className="gift-grid">
            {result.picks.map(w => <GiftCard key={w.id} whiskey={w} />)}
          </div>
          {result.picks.length === 0 && (
            <p className="no-picks">
              No bottles matched exactly — try a wider budget or a different style.
            </p>
          )}
          <button className="restart-btn" onClick={reset}>← Start Over</button>
        </div>
      </div>
    )
  }

  return (
    <div className="gift-page">
      <div className="gift-hero">
        <h1>🎁 Gift Finder</h1>
        <p>Answer three quick questions and get the perfect bottle for someone you appreciate.</p>
      </div>

      <div className="wizard-progress">
        {STEPS.map((s, i) => (
          <div key={s.id} className={`progress-dot ${i < step ? 'done' : i === step ? 'active' : ''}`} />
        ))}
      </div>

      <div className="wizard-step">
        <h2 className="step-question">{currentStep.question}</h2>
        <div className="options-grid">
          {currentStep.options.map(opt => (
            <OptionCard
              key={opt.value}
              option={opt}
              selected={answers[currentStep.id] === opt.value}
              onSelect={select}
            />
          ))}
        </div>
        {currentStep.optional && (
          <button className="skip-btn" onClick={skip}>Skip this step →</button>
        )}
      </div>

      {step > 0 && (
        <button className="back-btn" onClick={() => setStep(step - 1)}>← Back</button>
      )}
    </div>
  )
}
