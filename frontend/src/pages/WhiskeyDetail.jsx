import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'
import StoreLocator from '../components/StoreLocator'

const SERVING_STYLES = ['neat', 'rocks', 'cocktail', 'highball']
const SERVING_EMOJI = { neat: '🥃', rocks: '🧊', cocktail: '🍸', highball: '🥂' }

export default function WhiskeyDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [whiskey, setWhiskey] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [blurb, setBlurb] = useState(null)
  const [blurbLoading, setBlurbLoading] = useState(false)
  const [blurbStatus, setBlurbStatus] = useState(null)
  const [similar, setSimilar] = useState([])
  const [reviews, setReviews] = useState([])

  const [favorited, setFavorited] = useState(false)
  const [pairings, setPairings] = useState(null)
  const [shelfMsg, setShelfMsg] = useState('')
  const [tastingNotes, setTastingNotes] = useState(null)
  const [tastingLoading, setTastingLoading] = useState(false)

  // Rating form state
  const [score, setScore] = useState(0)
  const [notes, setNotes] = useState('')
  const [servingStyle, setServingStyle] = useState(null)
  const [locationNote, setLocationNote] = useState('')
  const [ratingMsg, setRatingMsg] = useState('')
  const [newBadges, setNewBadges] = useState([])

  useEffect(() => {
    setLoading(true)
    setBlurb(null)
    setSimilar([])

    api.getWhiskey(id)
      .then((w) => {
        setWhiskey(w)
        setBlurbLoading(true)
        api.getBlurb(id)
          .then((r) => { setBlurb(r?.blurb || null); setBlurbStatus(r?.status || null) })
          .catch(() => setBlurbStatus('error'))
          .finally(() => setBlurbLoading(false))
        api.getSimilar(id, 5).then(setSimilar).catch(() => {})
        api.getRatings(id).then(setReviews).catch(() => {})
        api.getPairings(id).then(setPairings).catch(() => {})
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  // Check if favorited
  useEffect(() => {
    api.getFavoriteIds()
      .then((r) => setFavorited(r.ids.includes(Number(id))))
      .catch(() => {})
  }, [id])

  async function toggleFavorite() {
    try {
      if (favorited) {
        await api.removeFavorite(id)
        setFavorited(false)
      } else {
        await api.addFavorite(id)
        setFavorited(true)
      }
    } catch (err) {
      console.error('Favorite error:', err)
    }
  }

  async function submitRating(e) {
    e.preventDefault()
    if (score === 0) return
    try {
      const body = { score, notes: notes || undefined }
      if (servingStyle) body.serving_style = servingStyle
      if (locationNote.trim()) body.location_note = locationNote.trim()
      const result = await api.rateWhiskey(id, body)
      const [updated, updatedReviews] = await Promise.all([
        api.getWhiskey(id),
        api.getRatings(id),
      ])
      setWhiskey(updated)
      setReviews(updatedReviews)
      setRatingMsg('Check-in saved!')
      setScore(0)
      setNotes('')
      setServingStyle(null)
      setLocationNote('')
      // Show badge celebration
      if (result.new_badges?.length > 0) {
        setNewBadges(result.new_badges)
        setTimeout(() => setNewBadges([]), 5000)
      }
    } catch (err) {
      setRatingMsg(`Error: ${err.message}`)
    }
  }

  if (loading) return <p className="status">Loading...</p>
  if (error) return <p className="status error">{error}</p>
  if (!whiskey) return null

  const flavors = whiskey.flavor_profile?.split(',').map((f) => f.trim()).filter(Boolean) ?? []

  return (
    <div className="page detail-page">
      <div className="detail-header">
        <div className="detail-title-row">
          <h1>{whiskey.name}</h1>
          <button
            className={`fav-btn ${favorited ? 'fav-btn--active' : ''}`}
            onClick={toggleFavorite}
            title={favorited ? 'Remove from favorites' : 'Add to favorites'}
          >
            {favorited ? '♥' : '♡'}
          </button>
        </div>
        <p className="detail-distillery">{whiskey.distillery}</p>
        <div className="detail-badges">
          <span className="badge">{whiskey.category}</span>
          {whiskey.region && <span className="badge">{whiskey.region}</span>}
          {whiskey.age && <span className="badge">{whiskey.age} Year</span>}
          <span className="badge">{whiskey.abv}% ABV</span>
          {whiskey.price_usd && <span className="badge">${whiskey.price_usd}</span>}
        </div>
      </div>

      {/* What makes this special */}
      <div className="detail-blurb">
        <h3>What makes this special</h3>
        {blurbLoading ? (
          <p className="blurb-loading">Generating description…</p>
        ) : (blurb || whiskey.description) ? (
          <p>{blurb || whiskey.description}</p>
        ) : blurbStatus === 'error' ? (
          <p className="blurb-empty">Description generation failed — try refreshing.</p>
        ) : (
          <p className="blurb-empty">No description available yet.</p>
        )}
      </div>

      {/* Clickable flavor tags */}
      {flavors.length > 0 && (
        <div className="flavor-tags">
          <h3>Flavor Profile</h3>
          <div className="tags">
            {flavors.map((f) => (
              <button
                key={f}
                className="tag tag--clickable"
                onClick={() => navigate(`/?flavor=${encodeURIComponent(f)}`)}
                title={`Browse ${f} whiskeys`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* AI Tasting Notes */}
      <div className="tasting-notes-section">
        <div className="tasting-notes-header">
          <h3>AI Tasting Notes</h3>
          {!tastingNotes && !tastingLoading && (
            <button
              className="tasting-notes-btn"
              onClick={async () => {
                setTastingLoading(true)
                try {
                  const data = await api.getAiTastingNotes(id)
                  setTastingNotes(data)
                } catch { setTastingNotes(null) }
                finally { setTastingLoading(false) }
              }}
            >
              Generate
            </button>
          )}
        </div>
        {tastingLoading && <p className="blurb-loading">Generating tasting notes...</p>}
        {tastingNotes && (
          <div className="tasting-notes-grid">
            <div className="tasting-note-card">
              <div className="tasting-note-label">Nose</div>
              <p>{tastingNotes.nose}</p>
            </div>
            <div className="tasting-note-card">
              <div className="tasting-note-label">Palate</div>
              <p>{tastingNotes.palate}</p>
            </div>
            <div className="tasting-note-card">
              <div className="tasting-note-label">Finish</div>
              <p>{tastingNotes.finish}</p>
            </div>
            {tastingNotes.overall && (
              <div className="tasting-note-card tasting-note-card--overall">
                <div className="tasting-note-label">Overall</div>
                <p>{tastingNotes.overall}</p>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="detail-rating">
        <h3>Community Rating</h3>
        <span className="big-rating">{whiskey.rating_avg.toFixed(1)} / 5</span>
        <span className="rating-count">({whiskey.rating_count} ratings)</span>
      </div>

      {/* Community reviews */}
      {reviews.length > 0 && (
        <div className="reviews-section">
          <h3>Community Reviews</h3>
          <div className="review-list">
            {reviews.map((r) => (
              <div key={r.id} className="review-item">
                <div className="review-header">
                  <Link to={`/user/${r.user_id}`} className="review-user">{r.user_id}</Link>
                  <span className="review-stars">{'★'.repeat(Math.round(r.score))}{'☆'.repeat(5 - Math.round(r.score))}</span>
                  {r.serving_style && (
                    <span className="checkin-serving">{SERVING_EMOJI[r.serving_style] || ''} {r.serving_style}</span>
                  )}
                  <span className="review-date">{new Date(r.created_at).toLocaleDateString()}</span>
                </div>
                {r.location_note && <p className="review-location">📍 {r.location_note}</p>}
                {r.notes && <p className="review-notes">{r.notes}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Add to Shelf */}
      <div className="shelf-action">
        <button
          className="shelf-add-btn"
          onClick={async () => {
            try {
              await api.addToCollection({ whiskey_id: Number(id) })
              setShelfMsg('Added to your shelf!')
            } catch (err) {
              setShelfMsg(err.message)
            }
          }}
        >
          + Add to My Shelf
        </button>
        {shelfMsg && <span className="shelf-msg">{shelfMsg}</span>}
      </div>

      {/* Food Pairings & Cocktails */}
      {pairings && (
        <div className="pairings-section">
          {pairings.food_pairings?.length > 0 && (
            <>
              <h3>Pairs Well With</h3>
              <div className="pairing-list">
                {pairings.food_pairings.map((p, i) => (
                  <div key={i} className="pairing-item">
                    <span className="pairing-name">{p.item}</span>
                    <span className="pairing-why">{p.why}</span>
                  </div>
                ))}
              </div>
            </>
          )}
          {pairings.cocktails?.length > 0 && (
            <>
              <h3>Cocktail Ideas</h3>
              <div className="cocktail-list">
                {pairings.cocktails.map((c, i) => (
                  <div key={i} className="cocktail-item">
                    <div className="cocktail-name">{c.name}</div>
                    <div className="cocktail-ingredients">{c.ingredients}</div>
                    <div className="cocktail-desc">{c.desc}</div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Find this nearby */}
      <StoreLocator whiskeyId={Number(id)} whiskeyName={whiskey.name} />

      {/* If you like this, try... */}
      {similar.length > 0 && (
        <div className="similar-section">
          <h3>If you like this, try...</h3>
          <div className="similar-grid">
            {similar.map((w) => (
              <WhiskeyCard key={w.id} whiskey={w} />
            ))}
          </div>
        </div>
      )}

      {/* Badge celebration */}
      {newBadges.length > 0 && (
        <div className="badge-celebration">
          <div className="badge-celebration-inner">
            <h3>Badge Unlocked!</h3>
            {newBadges.map(b => (
              <div key={b.slug} className="badge-celebration-item">
                <span className="badge-celebration-emoji">{b.emoji}</span>
                <div>
                  <strong>{b.name}</strong>
                  <p>{b.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rate-form">
        <h3>Check In This Whiskey</h3>
        <form onSubmit={submitRating}>
          <div className="star-picker">
            {[1, 2, 3, 4, 5].map((n) => (
              <span
                key={n}
                className={`star ${n <= score ? 'filled' : ''}`}
                onClick={() => setScore(n)}
              >★</span>
            ))}
          </div>

          <div className="serving-picker">
            <span className="serving-label">How are you drinking it?</span>
            <div className="serving-options">
              {SERVING_STYLES.map(s => (
                <button
                  key={s}
                  type="button"
                  className={`serving-btn ${servingStyle === s ? 'serving-btn--active' : ''}`}
                  onClick={() => setServingStyle(servingStyle === s ? null : s)}
                >
                  {SERVING_EMOJI[s]} {s}
                </button>
              ))}
            </div>
          </div>

          <input
            type="text"
            placeholder="Where are you? (optional)"
            value={locationNote}
            onChange={(e) => setLocationNote(e.target.value)}
            className="location-input"
          />

          <textarea
            placeholder="Tasting notes (optional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
          />
          <button type="submit" disabled={score === 0}>Check In</button>
          {ratingMsg && <p className="status">{ratingMsg}</p>}
        </form>
      </div>
    </div>
  )
}
