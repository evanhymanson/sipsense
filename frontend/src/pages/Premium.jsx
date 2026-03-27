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
  ctaSecondary: {
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
    marginBottom: '0.5rem',
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
  planToggle: {
    display: 'flex',
    gap: '0.5rem',
    marginBottom: '1.5rem',
    justifyContent: 'center',
  },
  planBtn: {
    padding: '0.5rem 1.25rem',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    background: 'var(--surface)',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: '0.85rem',
    fontWeight: 600,
    transition: 'all 0.15s',
  },
  planBtnActive: {
    background: 'var(--amber-dim)',
    borderColor: 'var(--amber)',
    color: 'var(--amber-light)',
  },
  priceDisplay: {
    textAlign: 'center',
    marginBottom: '1rem',
  },
  priceMain: {
    fontSize: '2rem',
    fontWeight: 700,
    color: 'var(--text)',
  },
  priceSub: {
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
  },
  trialNote: {
    textAlign: 'center',
    fontSize: '0.8rem',
    color: 'var(--text-muted)',
    marginBottom: '1.5rem',
  },
}

export default function Premium() {
  const addToast = useToast()
  const [status, setStatus] = useState(null)
  const [features, setFeatures] = useState([])
  const [loading, setLoading] = useState(true)
  const [plan, setPlan] = useState('monthly')
  const [checkoutLoading, setCheckoutLoading] = useState(false)

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

  async function handleCheckout() {
    setCheckoutLoading(true)
    try {
      const { checkout_url } = await api.createCheckoutSession(plan)
      window.location.href = checkout_url
    } catch (e) {
      if (e.message?.includes('503') || e.message?.includes('not configured')) {
        addToast('Payments coming soon! Stay tuned.', 'info')
      } else {
        addToast(e.message || 'Checkout failed', 'error')
      }
      setCheckoutLoading(false)
    }
  }

  async function handleManageSubscription() {
    try {
      const { url } = await api.createPortalSession()
      window.location.href = url
    } catch {
      addToast('Could not open subscription management', 'error')
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
        <>
          {status.has_stripe ? (
            <button style={styles.ctaSecondary} onClick={handleManageSubscription}>
              Manage Subscription
            </button>
          ) : (
            <button style={styles.cancelBtn} onClick={handleCancel}>
              Cancel Subscription
            </button>
          )}
        </>
      ) : (
        <>
          {/* Plan toggle */}
          <div style={styles.planToggle}>
            <button
              style={{ ...styles.planBtn, ...(plan === 'monthly' ? styles.planBtnActive : {}) }}
              onClick={() => setPlan('monthly')}
            >
              Monthly
            </button>
            <button
              style={{ ...styles.planBtn, ...(plan === 'yearly' ? styles.planBtnActive : {}) }}
              onClick={() => setPlan('yearly')}
            >
              Yearly (Save 33%)
            </button>
          </div>

          {/* Price display */}
          <div style={styles.priceDisplay}>
            <div style={styles.priceMain}>
              {plan === 'monthly' ? '$4.99' : '$39.99'}
              <span style={styles.priceSub}>{plan === 'monthly' ? '/month' : '/year'}</span>
            </div>
          </div>

          <p style={styles.trialNote}>
            Includes a 7-day free trial. Cancel anytime.
          </p>

          <button
            style={{ ...styles.cta, opacity: checkoutLoading ? 0.6 : 1 }}
            onClick={handleCheckout}
            disabled={checkoutLoading}
          >
            {checkoutLoading ? 'Loading...' : 'Start Free Trial'}
          </button>
        </>
      )}
    </div>
  )
}
