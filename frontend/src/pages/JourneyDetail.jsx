import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import './Journeys.css'

export default function JourneyDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const addToast = useToast()
  const [journey, setJourney] = useState(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    api.getJourney(slug)
      .then(setJourney)
      .catch(() => addToast('Failed to load journey', 'error'))
      .finally(() => setLoading(false))
  }, [slug])

  async function handleStart() {
    setActionLoading(true)
    try {
      await api.startJourney(slug)
      const updated = await api.getJourney(slug)
      setJourney(updated)
    } catch {
      addToast('Failed to start journey', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  async function handleComplete(stepNumber) {
    setActionLoading(true)
    try {
      await api.completeStep(slug, stepNumber)
      const updated = await api.getJourney(slug)
      setJourney(updated)
    } catch {
      addToast('Failed to complete step', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="page">
        <div className="journey-detail-page">
          <p className="journeys-loading">Loading journey...</p>
        </div>
      </div>
    )
  }

  if (!journey) {
    return (
      <div className="page">
        <div className="journey-detail-page">
          <p>Journey not found.</p>
          <Link to="/discover">Back to Journeys</Link>
        </div>
      </div>
    )
  }

  const progress = journey.user_progress
  const currentStep = progress?.current_step || 0
  const isComplete = progress?.completed_at != null

  return (
    <div className="page">
      <div className="journey-detail-page">
        <button className="back-btn" onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: 'var(--amber-light)', cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.9rem', padding: '0.25rem 0', marginBottom: '0.5rem' }}>&larr; Back</button>

        <div className="journey-header">
          <span className="journey-hero-emoji">{journey.image_emoji}</span>
          <div>
            <h1>{journey.title}</h1>
            <p className="journey-hero-desc">{journey.description}</p>
            <div className="journey-meta">
              <span className={`difficulty-badge difficulty--${journey.difficulty}`}>
                {journey.difficulty}
              </span>
              <span className="journey-bottles">{journey.bottle_count} bottles</span>
            </div>
          </div>
        </div>

        {!progress && (
          <button
            className="journey-start-btn"
            onClick={handleStart}
            disabled={actionLoading}
          >
            {actionLoading ? 'Starting...' : 'Start This Journey'}
          </button>
        )}

        {isComplete && (
          <div className="journey-complete-banner">
            Journey complete! You've tasted all {journey.bottle_count} whiskeys.
          </div>
        )}

        {progress && !isComplete && (
          <div className="journey-progress-bar-wrap">
            <div className="progress-bar progress-bar--lg">
              <div
                className="progress-fill"
                style={{ width: `${Math.round((currentStep / journey.bottle_count) * 100)}%` }}
              />
            </div>
            <span className="progress-label">
              Step {currentStep} of {journey.bottle_count}
            </span>
          </div>
        )}

        <div className="journey-steps">
          {journey.steps.map((step) => {
            const isCurrent = progress && step.step_number === currentStep
            const isDone = progress && step.step_number < currentStep
            const isLocked = !progress || step.step_number > currentStep

            return (
              <div
                key={step.step_number}
                className={`journey-step ${isCurrent ? 'step--current' : ''} ${isDone ? 'step--done' : ''} ${isLocked ? 'step--locked' : ''}`}
              >
                <div className="step-indicator">
                  {isDone ? '\u2713' : step.step_number}
                </div>

                <div className="step-content">
                  {step.whiskey && (
                    <div className="step-whiskey-header">
                      <Link to={`/whiskey/${step.whiskey.id}`} className="step-whiskey-name">
                        {step.whiskey.name}
                      </Link>
                      <div className="step-whiskey-meta">
                        <span>{step.whiskey.category}</span>
                        {step.whiskey.region && <span>{step.whiskey.region}</span>}
                        {step.whiskey.price_usd && <span>${Number(step.whiskey.price_usd).toFixed(2)}</span>}
                      </div>
                    </div>
                  )}

                  {(!isLocked || isDone) && (
                    <>
                      <div className="step-lesson">
                        <h4>Learn</h4>
                        <p>{step.lesson_text}</p>
                      </div>
                      <div className="step-prompt">
                        <h4>Tasting Prompt</h4>
                        <p>{step.tasting_prompt}</p>
                      </div>
                    </>
                  )}

                  {isLocked && !isDone && (
                    <p className="step-locked-msg">Complete the previous step to unlock</p>
                  )}

                  {isCurrent && !isComplete && (
                    <button
                      className="step-complete-btn"
                      onClick={() => handleComplete(step.step_number)}
                      disabled={actionLoading}
                    >
                      {actionLoading ? 'Saving...' : 'Mark as Tasted'}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
