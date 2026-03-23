import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import { getCategoryEmoji, MAX_UPLOAD_SIZE, MAX_UPLOAD_SIZE_LABEL } from '../constants'
import './ScanBottle.css'

const RECENT_KEY = 'sipsense_recent_scans'
const MAX_RECENT = 5

function loadRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') } catch { return [] }
}

function saveRecent(whiskey) {
  const prev = loadRecent().filter(w => w.id !== whiskey.id)
  const next = [{ id: whiskey.id, name: whiskey.name, distillery: whiskey.distillery,
    category: whiskey.category, image_url: whiskey.image_url }, ...prev].slice(0, MAX_RECENT)
  localStorage.setItem(RECENT_KEY, JSON.stringify(next))
}

function imageCls(category) {
  const c = (category || '').toLowerCase()
  const map = { bourbon: 'bourbon', scotch: 'scotch', irish: 'irish', japanese: 'japanese',
    rye: 'rye', canadian: 'canadian', 'single malt': 'single-malt', blended: 'blended' }
  return `scan-bottle-bg--${map[c] || 'default'}`
}

export default function ScanBottle() {
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const addToast = useToast()

  const [preview, setPreview] = useState(null)      // data URL of selected image
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)         // { found_in_db, whiskey, ai_identified }
  const [error, setError] = useState(null)
  const [shelfMsg, setShelfMsg] = useState('')
  const [recent, setRecent] = useState(loadRecent)
  const [showBarcode, setShowBarcode] = useState(false)
  const [manualUpc, setManualUpc] = useState('')

  // Clean up preview object URL on unmount
  const previewRef = useRef(preview)
  previewRef.current = preview
  useEffect(() => {
    return () => { if (previewRef.current) URL.revokeObjectURL(previewRef.current) }
  }, [])

  // ── Label scan ────────────────────────────────────────────────────────

  function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > MAX_UPLOAD_SIZE) {
      addToast(`Photo must be under ${MAX_UPLOAD_SIZE_LABEL}`, 'error')
      return
    }
    setError(null)
    setResult(null)
    setShelfMsg('')
    if (preview) URL.revokeObjectURL(preview)
    setPreview(URL.createObjectURL(file))
    scanFile(file)
  }

  async function scanFile(file) {
    setLoading(true)
    try {
      const data = await api.scanLabel(file)
      setResult(data)
      if (data.whiskey) {
        saveRecent(data.whiskey)
        setRecent(loadRecent())
      }
    } catch (err) {
      const msg = err.message || 'Could not identify label'
      setError(msg.includes('not a whiskey') ? 'No whiskey label detected — try a clearer photo of the front label.' : msg)
    } finally {
      setLoading(false)
    }
  }

  // ── Barcode fallback ──────────────────────────────────────────────────

  async function lookupBarcode(upc) {
    setLoading(true)
    setError(null)
    setResult(null)
    setShelfMsg('')
    try {
      const whiskey = await api.lookupBarcode(upc)
      setResult({ found_in_db: true, whiskey, ai_identified: null })
      saveRecent(whiskey)
      setRecent(loadRecent())
    } catch (err) {
      setError(err.message || 'Barcode not found in our database')
    } finally {
      setLoading(false)
    }
  }

  function handleManualSubmit(e) {
    e.preventDefault()
    if (manualUpc.trim()) lookupBarcode(manualUpc.trim())
  }

  // ── Shelf action ──────────────────────────────────────────────────────

  async function addToShelf() {
    if (!result?.whiskey) return
    try {
      await api.addToCollection({ whiskey_id: result.whiskey.id })
      setShelfMsg('Added to your shelf!')
    } catch (err) {
      setShelfMsg(err.message?.includes('401') ? 'Sign in to add to shelf' : 'Already on your shelf')
    }
  }

  // ── Reset ─────────────────────────────────────────────────────────────

  function handleReset() {
    setResult(null)
    setError(null)
    if (preview) URL.revokeObjectURL(preview)
    setPreview(null)
    setManualUpc('')
    setShelfMsg('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // ── Derived ───────────────────────────────────────────────────────────

  const displayWhiskey = result?.whiskey
  const aiInfo = result?.ai_identified
  const emoji = getCategoryEmoji(displayWhiskey?.category || aiInfo?.category)

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <div className="page">
      <div className="scan-page">
        <h1>Scan a Bottle</h1>
        <p className="scan-subtitle">
          Take a photo of the label — AI identifies it instantly.
        </p>

        {/* ── Idle / upload state ── */}
        {!result && !loading && (
          <>
            <div
              className={`label-drop-zone ${preview ? 'label-drop-zone--has-preview' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInputRef.current?.click() } }}
              role="button"
              tabIndex={0}
              aria-label="Take a photo or choose from gallery"
            >
              {preview ? (
                <img src={preview} alt="Label preview" className="label-preview-img" />
              ) : (
                <>
                  <span className="label-drop-icon">📷</span>
                  <p className="label-drop-text">Tap to take a photo or choose from gallery</p>
                  <p className="label-drop-hint">Point at the front label for best results</p>
                </>
              )}
            </div>

            {/* Hidden file input — capture="environment" opens rear camera on mobile */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />

            {/* Barcode fallback toggle */}
            <button
              className="scan-toggle-link"
              onClick={() => setShowBarcode(b => !b)}
            >
              {showBarcode ? 'Hide barcode entry' : 'Use barcode instead'}
            </button>

            {showBarcode && (
              <div className="manual-entry">
                <form onSubmit={handleManualSubmit} className="manual-form">
                  <input
                    type="text"
                    value={manualUpc}
                    onChange={e => setManualUpc(e.target.value)}
                    placeholder="Enter barcode number (e.g. 080432400005)"
                    className="manual-input"
                  />
                  <button type="submit" className="manual-submit" disabled={!manualUpc.trim()}>
                    Look Up
                  </button>
                </form>
              </div>
            )}

            {error && (
              <div className="scan-error">
                <p>{error}</p>
                <button className="scan-retry-btn" onClick={handleReset}>Try Again</button>
              </div>
            )}

            {recent.length > 0 && (
              <div className="recent-scans">
                <h3>Recent Scans</h3>
                <div className="recent-list">
                  {recent.map(w => (
                    <Link key={w.id} to={`/whiskey/${w.id}`} className="recent-item">
                      <div className={`recent-img ${imageCls(w.category)}`}>
                        <span className="recent-emoji">{getCategoryEmoji(w.category)}</span>
                        {w.image_url && (
                          <img src={w.image_url} alt={w.name} className="recent-bottle-img"
                            onError={e => { e.target.style.display = 'none' }} />
                        )}
                      </div>
                      <div className="recent-info">
                        <span className="recent-name">{w.name}</span>
                        <span className="recent-distillery">{w.distillery}</span>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* ── Loading state ── */}
        {loading && (
          <div className="scan-loading-state">
            {preview && (
              <img src={preview} alt="Scanning..." className="label-scanning-preview" />
            )}
            <div className="scan-loading-spinner" />
            <p className="scan-loading-text">AI is identifying your bottle…</p>
          </div>
        )}

        {/* ── Result: found in DB ── */}
        {result && displayWhiskey && (
          <div className="scan-result">
            {result.found_in_db && (
              <div className="scan-match-badge">✓ Found in SipSense</div>
            )}
            {!result.found_in_db && aiInfo && (
              <div className="scan-match-badge scan-match-badge--ai">
                ✦ AI identified — not yet in our database
              </div>
            )}

            <div className="scan-result-card">
              <div className={`scan-bottle-hero ${imageCls(displayWhiskey.category)}`}>
                <span className="scan-bottle-icon">{emoji}</span>
                {displayWhiskey.image_url && (
                  <img src={displayWhiskey.image_url} alt={displayWhiskey.name}
                    className="scan-bottle-img"
                    onError={e => { e.target.style.display = 'none' }} />
                )}
                {displayWhiskey.rating_avg > 0 && (
                  <div className="scan-score-badge">{displayWhiskey.rating_avg.toFixed(1)}</div>
                )}
              </div>

              <div className="scan-result-body">
                <h2>{displayWhiskey.name}</h2>
                <p className="scan-distillery">{displayWhiskey.distillery}</p>

                <div className="scan-result-details">
                  <span className="scan-badge">{displayWhiskey.category}</span>
                  {displayWhiskey.region && <span className="scan-badge">{displayWhiskey.region}</span>}
                  {displayWhiskey.abv && <span className="scan-badge">{displayWhiskey.abv}% ABV</span>}
                  {displayWhiskey.age && <span className="scan-badge">{displayWhiskey.age}yr</span>}
                </div>

                {displayWhiskey.price_usd && (
                  <p className={`scan-price${displayWhiskey.price_is_estimated ? ' scan-price--estimated' : ''}`}>
                    {displayWhiskey.price_is_estimated ? '~' : ''}${Number(displayWhiskey.price_usd).toFixed(2)}
                    {displayWhiskey.price_is_estimated && <span className="est-label"> Est.</span>}
                  </p>
                )}

                {displayWhiskey.flavor_profile && (
                  <div className="scan-flavors">
                    {displayWhiskey.flavor_profile.split(',').slice(0, 5).map(f => (
                      <span key={f.trim()} className="flavor-tag">{f.trim()}</span>
                    ))}
                  </div>
                )}

                <div className="scan-actions">
                  <button className="scan-action-btn scan-action-btn--shelf" onClick={addToShelf}>
                    + Collection
                  </button>
                  <button
                    className="scan-action-btn scan-action-btn--checkin"
                    onClick={() => navigate(`/whiskey/${displayWhiskey.id}#check-in`)}
                  >
                    Log Check-in
                  </button>
                </div>
                {shelfMsg && <p className="scan-shelf-msg">{shelfMsg}</p>}

                <Link to={`/whiskey/${displayWhiskey.id}`} className="scan-detail-btn">
                  View Full Details →
                </Link>
              </div>
            </div>

            <button className="scan-another-btn" onClick={handleReset}>
              Scan Another Bottle
            </button>
          </div>
        )}

        {/* ── Result: AI identified but not in DB ── */}
        {result && !displayWhiskey && aiInfo && (
          <div className="scan-result">
            <div className="scan-match-badge scan-match-badge--ai">
              ✦ AI identified — not yet in our database
            </div>

            <div className="scan-result-card scan-result-card--ai">
              <div className={`scan-bottle-hero ${imageCls(aiInfo.category)}`}>
                <span className="scan-bottle-icon">{emoji}</span>
                {preview && (
                  <img src={preview} alt="Scanned label" className="scan-bottle-img" />
                )}
              </div>

              <div className="scan-result-body">
                <h2>{aiInfo.name || 'Unknown Whiskey'}</h2>
                {aiInfo.distillery && <p className="scan-distillery">{aiInfo.distillery}</p>}

                <div className="scan-result-details">
                  {aiInfo.category && <span className="scan-badge">{aiInfo.category}</span>}
                  {aiInfo.region && <span className="scan-badge">{aiInfo.region}</span>}
                  {aiInfo.abv && <span className="scan-badge">{aiInfo.abv}% ABV</span>}
                  {aiInfo.age && <span className="scan-badge">{aiInfo.age}yr</span>}
                </div>

                <p className="scan-not-in-db">
                  This bottle isn't in our database yet. Try browsing or searching for it manually.
                </p>

                <Link
                  to={`/?q=${encodeURIComponent(aiInfo.name || '')}`}
                  className="scan-detail-btn"
                >
                  Search for "{aiInfo.name}" →
                </Link>
              </div>
            </div>

            <button className="scan-another-btn" onClick={handleReset}>
              Scan Another Bottle
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
