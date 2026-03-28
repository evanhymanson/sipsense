import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, setAuth } from '../api/client'
import './Onboarding.css'

export default function Onboarding() {
  const [searchParams] = useSearchParams()
  const resetToken = searchParams.get('reset_token')

  // Modes: 'register' | 'login' | 'forgot' | 'reset'
  const [mode, setMode] = useState(resetToken ? 'reset' : 'register')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [successMsg, setSuccessMsg] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (resetToken) setMode('reset')
  }, [resetToken])

  const canSubmit = (() => {
    if (mode === 'login') return username.trim() && password.length >= 6
    if (mode === 'register') return username.trim() && email.trim() && password.length >= 6
    if (mode === 'forgot') return email.trim()
    if (mode === 'reset') return password.length >= 8
    return false
  })()

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSuccessMsg(null)
    setLoading(true)
    try {
      if (mode === 'register') {
        const data = await api.register(username.trim(), email.trim(), password)
        setAuth(data.access_token, data.username, data.refresh_token)
        navigate('/quiz')
      } else if (mode === 'login') {
        const data = await api.login(username.trim(), password)
        setAuth(data.access_token, data.username, data.refresh_token)
        navigate('/')
      } else if (mode === 'forgot') {
        await api.forgotPassword(email.trim())
        setSuccessMsg('If an account with that email exists, we\'ve sent a reset link. Check your inbox.')
      } else if (mode === 'reset') {
        await api.resetPassword(resetToken, password)
        setSuccessMsg('Password reset successfully! You can now sign in.')
        setTimeout(() => { setMode('login'); setSuccessMsg(null) }, 3000)
      }
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

          {(mode === 'register' || mode === 'login') && (
            <div className="onboarding-tabs">
              <button
                className={`onboarding-tab ${mode === 'register' ? 'onboarding-tab--active' : ''}`}
                onClick={() => { setMode('register'); setError(null); setSuccessMsg(null) }}
              >
                Create Account
              </button>
              <button
                className={`onboarding-tab ${mode === 'login' ? 'onboarding-tab--active' : ''}`}
                onClick={() => { setMode('login'); setError(null); setSuccessMsg(null) }}
              >
                Sign In
              </button>
            </div>
          )}

          {mode === 'forgot' && (
            <h3 className="onboarding-mode-title">Reset Your Password</h3>
          )}
          {mode === 'reset' && (
            <h3 className="onboarding-mode-title">Choose a New Password</h3>
          )}

          <form className="onboarding-form" onSubmit={handleSubmit}>
            {(mode === 'register' || mode === 'login') && (
              <>
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
              </>
            )}

            {(mode === 'register' || mode === 'forgot') && (
              <>
                <label className="onboarding-label" htmlFor="email">Email</label>
                <input
                  id="email"
                  className="onboarding-input"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  autoFocus={mode === 'forgot'}
                />
              </>
            )}

            {(mode === 'register' || mode === 'login' || mode === 'reset') && (
              <>
                <label className="onboarding-label" htmlFor="password">
                  {mode === 'reset' ? 'New Password' : 'Password'}
                </label>
                <div className="password-wrapper">
                  <input
                    id="password"
                    className="onboarding-input"
                    type={showPassword ? 'text' : 'password'}
                    placeholder={mode === 'reset' ? 'At least 8 characters' : 'At least 6 characters'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    minLength={mode === 'reset' ? 8 : 6}
                    autoFocus={mode === 'reset'}
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
                {mode === 'reset' && password.length > 0 && password.length < 8 && (
                  <p className="onboarding-error">Password must be at least 8 characters</p>
                )}
              </>
            )}

            {error && <p className="onboarding-error">{error}</p>}
            {successMsg && <p className="onboarding-success">{successMsg}</p>}

            <button
              className="onboarding-btn"
              type="submit"
              disabled={!canSubmit || loading}
            >
              {loading
                ? 'Please wait...'
                : mode === 'register'
                  ? 'Create Account & Take Quiz'
                  : mode === 'login'
                    ? 'Sign In'
                    : mode === 'forgot'
                      ? 'Send Reset Link'
                      : 'Reset Password'}
            </button>
          </form>

          {mode === 'login' && (
            <button
              className="onboarding-forgot-link"
              onClick={() => { setMode('forgot'); setError(null); setSuccessMsg(null) }}
            >
              Forgot your password?
            </button>
          )}

          {(mode === 'forgot' || mode === 'reset') && (
            <button
              className="onboarding-forgot-link"
              onClick={() => { setMode('login'); setError(null); setSuccessMsg(null) }}
            >
              Back to Sign In
            </button>
          )}

          <p className="onboarding-fine">
            {mode === 'register'
              ? 'Your data stays private. We never share your information.'
              : mode === 'login'
                ? 'Welcome back! Sign in to pick up where you left off.'
                : mode === 'forgot'
                  ? 'Enter the email associated with your account.'
                  : 'Choose a strong password for your account.'}
          </p>
        </div>
      </div>
    </div>
  )
}
