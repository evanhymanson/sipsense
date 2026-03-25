import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setAuth } from '../api/client'
import './Onboarding.css'

export default function Onboarding() {
  const [mode, setMode] = useState('register') // 'register' | 'login'
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const canSubmit = mode === 'login'
    ? username.trim() && password.length >= 6
    : username.trim() && email.trim() && password.length >= 6

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      let data
      if (mode === 'register') {
        data = await api.register(username.trim(), email.trim(), password)
      } else {
        data = await api.login(username.trim(), password)
      }
      setAuth(data.access_token, data.username)
      navigate(mode === 'register' ? '/quiz' : '/')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="onboarding">
      {/* ── Hero (left on desktop, top on mobile) ── */}
      <div className="onboarding-hero">
        <div className="onboarding-hero-content">
          <h1 className="onboarding-headline">
            Discover your<br />perfect pour
          </h1>
          <ul className="onboarding-features">
            <li>5,000+ whiskeys to explore</li>
            <li>AI-powered recommendations</li>
            <li>Track your tasting journey</li>
          </ul>
          <p className="onboarding-hero-brand">SipSense</p>
        </div>
      </div>

      {/* ── Auth panel (right on desktop, below on mobile) ── */}
      <div className="onboarding-panel">
        <div className="onboarding-card">
          <h2 className="onboarding-title">SipSense</h2>
          <p className="onboarding-subtitle">Your personal whiskey guide</p>

          <div className="onboarding-tabs">
            <button
              className={`onboarding-tab ${mode === 'register' ? 'onboarding-tab--active' : ''}`}
              onClick={() => { setMode('register'); setError(null) }}
            >
              Create Account
            </button>
            <button
              className={`onboarding-tab ${mode === 'login' ? 'onboarding-tab--active' : ''}`}
              onClick={() => { setMode('login'); setError(null) }}
            >
              Sign In
            </button>
          </div>

          <form className="onboarding-form" onSubmit={handleSubmit}>
            <label className="onboarding-label" htmlFor="username">Username</label>
            <input
              id="username"
              className="onboarding-input"
              type="text"
              placeholder="e.g. whiskey_evan"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoFocus
              maxLength={30}
            />

            {mode === 'register' && (
              <>
                <label className="onboarding-label" htmlFor="email">Email</label>
                <input
                  id="email"
                  className="onboarding-input"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                />
              </>
            )}

            <label className="onboarding-label" htmlFor="password">Password</label>
            <div className="password-wrapper">
              <input
                id="password"
                className="onboarding-input"
                type={showPassword ? 'text' : 'password'}
                placeholder="At least 6 characters"
                value={password}
                onChange={e => setPassword(e.target.value)}
                minLength={6}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword(v => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? '🙈' : '👁'}
              </button>
            </div>
            {mode === 'register' && password.length > 0 && password.length < 6 && (
              <p className="onboarding-error">Password must be at least 6 characters</p>
            )}

            {error && <p className="onboarding-error">{error}</p>}

            <button
              className="onboarding-btn"
              type="submit"
              disabled={!canSubmit || loading}
            >
              {loading
                ? 'Please wait...'
                : mode === 'register'
                  ? 'Create Account & Take Quiz'
                  : 'Sign In'}
            </button>
          </form>

          <p className="onboarding-fine">
            {mode === 'register'
              ? 'Your data stays private. We never share your information.'
              : 'Welcome back! Sign in to pick up where you left off.'}
          </p>
        </div>
      </div>
    </div>
  )
}
