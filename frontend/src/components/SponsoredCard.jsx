import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'

const styles = {
  card: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '1rem',
    position: 'relative',
  },
  badge: {
    position: 'absolute',
    top: '0.6rem',
    right: '0.6rem',
    background: 'rgba(201, 168, 76, 0.15)',
    color: 'var(--amber)',
    fontSize: '0.65rem',
    fontWeight: 700,
    padding: '0.15rem 0.5rem',
    borderRadius: '4px',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  },
  advertiser: {
    fontSize: '0.75rem',
    color: 'var(--text-muted)',
    marginBottom: '0.3rem',
  },
  title: {
    fontSize: '1rem',
    fontWeight: 700,
    color: 'var(--text)',
    marginBottom: '0.3rem',
  },
  description: {
    fontSize: '0.85rem',
    color: 'var(--text-soft)',
    marginBottom: '0.75rem',
  },
  image: {
    width: '100%',
    borderRadius: 'var(--radius-sm)',
    marginBottom: '0.75rem',
    objectFit: 'cover',
    maxHeight: '200px',
  },
  cta: {
    display: 'inline-block',
    background: 'var(--amber)',
    color: '#1a1a1a',
    padding: '0.4rem 1rem',
    borderRadius: '999px',
    fontSize: '0.8rem',
    fontWeight: 700,
    textDecoration: 'none',
    transition: 'background 0.15s',
  },
  whiskeyLink: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.3rem',
    color: 'var(--amber-light)',
    fontSize: '0.85rem',
    textDecoration: 'none',
    marginTop: '0.5rem',
  },
}

export default function SponsoredCard({ placement }) {
  const tracked = useRef(false)

  // Record impression once when card mounts
  useEffect(() => {
    if (!tracked.current && placement?.id) {
      api.trackSponsoredImpression(placement.id).catch(() => {})
      tracked.current = true
    }
  }, [placement?.id])

  if (!placement) return null

  function handleClick() {
    api.trackSponsoredClick(placement.id).catch(() => {})
  }

  return (
    <div style={styles.card}>
      <span style={styles.badge}>Sponsored</span>
      <p style={styles.advertiser}>{placement.advertiser_name}</p>

      {placement.image_url && (
        <img
          src={placement.image_url}
          alt={placement.title || 'Sponsored'}
          style={styles.image}
          onError={e => { e.target.style.display = 'none' }}
        />
      )}

      {placement.title && <h4 style={styles.title}>{placement.title}</h4>}
      {placement.description && <p style={styles.description}>{placement.description}</p>}

      {placement.link_url && (
        <a
          href={placement.link_url}
          target="_blank"
          rel="noopener noreferrer"
          style={styles.cta}
          onClick={handleClick}
        >
          Learn More
        </a>
      )}

      {placement.whiskey_id && placement.whiskey && (
        <div>
          <Link
            to={`/whiskey/${placement.whiskey_id}`}
            style={styles.whiskeyLink}
            onClick={handleClick}
          >
            🥃 View {placement.whiskey.name}
          </Link>
        </div>
      )}
    </div>
  )
}
