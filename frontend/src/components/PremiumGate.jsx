import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

const styles = {
  gate: {
    background: 'var(--surface)',
    border: '1px solid var(--amber)',
    borderRadius: 'var(--radius)',
    padding: '1.5rem',
    textAlign: 'center',
  },
  title: {
    fontSize: '1.1rem',
    fontWeight: 700,
    color: 'var(--amber)',
    marginBottom: '0.4rem',
  },
  desc: {
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
    marginBottom: '1rem',
  },
  btn: {
    background: 'var(--amber)',
    color: '#1a1a1a',
    border: 'none',
    padding: '0.5rem 1.25rem',
    borderRadius: '999px',
    fontWeight: 700,
    fontSize: '0.85rem',
    cursor: 'pointer',
    fontFamily: 'inherit',
  },
}

export default function PremiumGate({ feature, children }) {
  const navigate = useNavigate()
  const [isPremium, setIsPremium] = useState(null)

  useEffect(() => {
    api.getSubscriptionStatus()
      .then(s => setIsPremium(s.is_premium))
      .catch(() => setIsPremium(false))
  }, [])

  // Show loading state while checking subscription (don't leak premium content)
  if (isPremium === null) return (
    <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
      Loading…
    </div>
  )
  if (isPremium) return children

  return (
    <div style={styles.gate}>
      <h3 style={styles.title}>SipSense Premium</h3>
      <p style={styles.desc}>Unlock {feature} with Premium</p>
      <button style={styles.btn} onClick={() => navigate('/premium')}>
        Learn More
      </button>
    </div>
  )
}
