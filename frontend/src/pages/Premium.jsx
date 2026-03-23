import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useToast } from '../components/Toast'

const styles = {
  page: {
    maxWidth: '600px',
    margin: '0 auto',
    padding: '2rem 1rem',
  },
  hero: {
    textAlign: 'center',
    marginBottom: '2rem',
  },
  title: {
    fontSize: '2rem',
    fontWeight: 700,
    color: 'var(--amber)',
    marginBottom: '0.5rem',
  },
  subtitle: {
    color: 'var(--text-muted)',
    fontSize: '1rem',
  },
  statusBadge: {
    display: 'inline-block',
    padding: '0.4rem 1rem',
    borderRadius: '999px',
    fontSize: '0.85rem',
    fontWeight: 700,
    marginBottom: '1.5rem',
  },
  active: {
    background: 'rgba(102, 187, 106, 0.15)',
    color: 'var(--green-light)',
    border: '1px solid var(--green)',
  },
  inactive: {
    background: 'var(--amber-dim)',
    color: 'var(--amber-light)',
    border: '1px solid var(--amber)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    marginBottom: '2rem',
  },
  th: {
    textAlign: 'left',
    padding: '0.6rem 0.75rem',
    borderBottom: '2px solid var(--border)',
    fontSize: '0.8rem',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    color: 'var(--text-muted)',
  },
  td: {
    padding: '0.6rem 0.75rem',
    borderBottom: '1px solid var(--border)',
    fontSize: '0.85rem',
    color: 'var(--text-soft)',
  },
  featureName: {
    fontWeight: 600,
    color: 'var(--text)',
  },
  premiumCell: {
    color: 'var(--amber-light)',
    fontWeight: 600,
  },
  cta: {
    display: 'block',
    width: '100%',
    padding: '0.75rem',
    background: 'var(--amber)',
    color: '#1a1a1a',
    border: 'none',
    borderRadius: 'var(--radius)',
    fontSize: '1rem',
    fontWeight: 700,
    cursor: 'pointer',
    fontFamily: 'inherit',
    transition: 'background 0.15s',
    marginBottom: '0.75rem',
  },
  cancelBtn: {
    display: 'block',
    width: '100%',
    padding: '0.65rem',
    background: 'var(--surface)',
    color: 'var(--text-muted)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    fontSize: '0.9rem',
    cursor: 'pointer',
    fontFamily: 'inherit',
  },
  expires: {
    textAlign: 'center',
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
    marginBottom: '1rem',
  },
}

export default function Premium() {
  const addToast = useToast()
  const [status, setStatus] = useState(null)
  const [features, setFeatures] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.getSubscriptionStatus(),
      api.getFeatureComparison(),
    ])
      .then(([s, f]) => {
        setStatus(s)
        setFeatures(f)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function handleActivate() {
    try {
      await api.activatePremium()
      const s = await api.getSubscriptionStatus()
      setStatus(s)
      addToast('Premium activated!', 'success')
    } catch (e) {
      addToast(e.message || 'Activation failed', 'error')
    }
  }

  async function handleCancel() {
    try {
      await api.cancelSubscription()
      const s = await api.getSubscriptionStatus()
      setStatus(s)
      addToast('Subscription canceled', 'info')
    } catch (e) {
      addToast(e.message || 'Cancel failed', 'error')
    }
  }

  if (loading) return <div style={styles.page}><p>Loading...</p></div>

  return (
    <div style={styles.page}>
      <div style={styles.hero}>
        <h1 style={styles.title}>SipSense Premium</h1>
        <p style={styles.subtitle}>Unlock the full whiskey experience</p>
      </div>

      {status && (
        <div style={{ textAlign: 'center' }}>
          <span style={{
            ...styles.statusBadge,
            ...(status.is_premium ? styles.active : styles.inactive),
          }}>
            {status.is_premium ? 'Premium Active' : 'Free Tier'}
          </span>
        </div>
      )}

      {status?.is_premium && status.expires_at && (
        <p style={styles.expires}>
          Renews {new Date(status.expires_at).toLocaleDateString()}
        </p>
      )}

      {features.length > 0 && (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Feature</th>
              <th style={styles.th}>Free</th>
              <th style={styles.th}>Premium</th>
            </tr>
          </thead>
          <tbody>
            {features.map(f => (
              <tr key={f.feature}>
                <td style={{ ...styles.td, ...styles.featureName }}>{f.feature}</td>
                <td style={styles.td}>{f.free_tier}</td>
                <td style={{ ...styles.td, ...styles.premiumCell }}>{f.premium_tier}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {status?.is_premium ? (
        <button style={styles.cancelBtn} onClick={handleCancel}>
          Cancel Subscription
        </button>
      ) : (
        <button style={styles.cta} onClick={handleActivate}>
          Upgrade to Premium
        </button>
      )}
    </div>
  )
}
