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
  const [rememberMe, setRememberMe] = useState(true)
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
        const data = await api.login(username.trim(), password, rememberMe)
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

            {mode === 'login' && (
              <label className="remember-me-row">
                <input type="checkbox" checked={rememberMe} onChange={e => setRememberMe(e.target.checked)} />
                <span>Remember me for 30 days</span>
              </label>
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

          {(mode === 'login' || mode === 'register') && (
            <div className="oauth-divider">
              <span>or continue with</span>
            </div>
          )}
          {(mode === 'login' || mode === 'register') && (
            <div className="oauth-buttons">
              <button className="oauth-btn oauth-btn--google" onClick={() => {
                // Google OAuth - in production, integrate with Google Sign-In SDK
                // For now, show a placeholder message
                setError('Google Sign-In coming soon! Use email registration for now.')
              }}>
                <svg width="18" height="18" viewBox="0 0 18 18"><path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/><path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/><path d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332z" fill="#FBBC05"/><path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.166 6.656 3.58 9 3.58z" fill="#EA4335"/></svg>
                Google
              </button>
              <button className="oauth-btn oauth-btn--apple" onClick={() => {
                setError('Apple Sign-In coming soon! Use email registration for now.')
              }}>
                <svg width="18" height="18" viewBox="0 0 18 18"><path d="M15.5 12.5c-.3.7-.4 1-.8 1.6-.5.9-1.2 2-2.1 2-.8 0-1-.5-2.1-.5s-1.3.5-2.2.5c-.9 0-1.5-1-2.1-2C4.9 11.8 4.7 9.3 5.7 8c.7-1 1.8-1.5 2.8-1.5.9 0 1.5.5 2.2.5.7 0 1.2-.5 2.3-.5.8 0 1.7.4 2.3 1.2-2 1.1-1.7 4 .2 4.8zM12 4.5c.4-.5.7-1.2.6-2-.6 0-1.3.5-1.8 1-.4.5-.7 1.2-.6 1.9.7 0 1.4-.4 1.8-.9z" fill="currentColor"/></svg>
                Apple
              </button>
            </div>
          )}

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
