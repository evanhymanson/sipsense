import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api/client'
import StoreMap from './StoreMap'
import ReportModal from './ReportModal'
import './StoreLocator.css'

const INITIAL_STORE_COUNT = 3

export default function StoreLocator({ whiskeyId, whiskeyName }) {
  const [stores, setStores] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [userPos, setUserPos] = useState(null)
  const [reportStore, setReportStore] = useState(null)
  const [radius, setRadius] = useState(5000)
  const [locSource, setLocSource] = useState(null) // 'gps', 'ip', or 'manual'
  const [locLoading, setLocLoading] = useState(true)
  const [manualInput, setManualInput] = useState('')
  const [manualError, setManualError] = useState(null)
  const [showAll, setShowAll] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const isMountedRef = useRef(true)
  useEffect(() => () => { isMountedRef.current = false }, [])

  // ── Try multiple IP geolocation services ──────────────────────────
  async function fallbackIpLocation(signal) {
    const services = [
      {
        url: 'https://ipapi.co/json/',
        parse: (d) => d.latitude && d.longitude ? { lat: d.latitude, lng: d.longitude } : null,
      },
      {
        url: 'https://ip-api.com/json/?fields=lat,lon,status',
        parse: (d) => d.status === 'success' ? { lat: d.lat, lng: d.lon } : null,
      },
    ]

    for (const svc of services) {
      if (signal?.aborted) return
      try {
        const res = await fetch(svc.url, { signal })
        if (!res.ok) continue
        const data = await res.json()
        const pos = svc.parse(data)
        if (pos) {
          if (!isMountedRef.current) return
          setUserPos(pos)
          setLocSource('ip')
          setError(null)
          setLocLoading(false)
          return
        }
      } catch {
        // try next service or aborted
      }
    }

    // All IP services failed
    if (isMountedRef.current) setLocLoading(false)
  }

  // ── Request browser GPS, fall back to IP ──────────────────────────
  function requestLocation(signal) {
    setLocLoading(true)
    if (!navigator.geolocation) {
      fallbackIpLocation(signal)
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (!isMountedRef.current) return
        setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setLocSource('gps')
        setError(null)
        setLocLoading(false)
      },
      () => {
        if (!isMountedRef.current) return
        fallbackIpLocation(signal)
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
    )
  }

  useEffect(() => {
    const controller = new AbortController()
    requestLocation(controller.signal)
    return () => controller.abort()
  // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only; requestLocation uses only stable setters
  }, [])

  // ── Manual location: geocode a zip code or city name ──────────────
  async function handleManualSearch(e) {
    e.preventDefault()
    const q = manualInput.trim()
    if (!q) return
    setManualError(null)

    // Detect if input is purely numeric
    const isNumeric = /^\d+$/.test(q)

    // 3-digit numbers are phone area codes, not locations
    if (isNumeric && q.length === 3) {
      setManualError('That looks like a phone area code. Please enter a 5-digit zip code or city name.')
      return
    }

    // Build the Nominatim query — use postalcode param for zip codes
    let url
    if (isNumeric && q.length === 5) {
      url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&postalcode=${q}&countrycodes=us`
    } else {
      url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=us&q=${encodeURIComponent(q)}`
    }

    try {
      const res = await fetch(url, { headers: { 'Accept': 'application/json' } })
      if (!res.ok) throw new Error('Geocoding failed')
      const results = await res.json()
      if (results.length === 0) {
        setManualError('Location not found. Try a 5-digit zip code or city name.')
        return
      }
      const { lat, lon } = results[0]
      setUserPos({ lat: parseFloat(lat), lng: parseFloat(lon) })
      setLocSource('manual')
      setError(null)
      setLocLoading(false)
    } catch {
      setManualError('Could not look up that location. Try again.')
    }
  }

  // ── Fetch stores when position changes ────────────────────────────
  const fetchStores = useCallback(async () => {
    if (!userPos) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.getStoresForWhiskey(whiskeyId, userPos.lat, userPos.lng, radius)
      if (isMountedRef.current) setStores(data)
    } catch (e) {
      if (isMountedRef.current) setError(e.message)
    } finally {
      if (isMountedRef.current) setLoading(false)
    }
  }, [whiskeyId, userPos, radius])

  useEffect(() => { fetchStores() }, [fetchStores])

  function handleReportSubmitted() {
    setReportStore(null)
    fetchStores()
  }

  function formatDistance(meters) {
    if (meters < 1000) return `${Math.round(meters)}m`
    return `${(meters / 1609.34).toFixed(1)} mi`
  }

  function statusInfo(status) {
    if (status === 'in_stock') return { cls: 'status-dot--green', label: 'In Stock' }
    if (status === 'out_of_stock') return { cls: 'status-dot--red', label: 'Out of Stock' }
    return { cls: 'status-dot--gray', label: 'Unknown' }
  }

  const visibleStores = showAll ? stores : stores.slice(0, INITIAL_STORE_COUNT)
  const hiddenCount = stores.length - INITIAL_STORE_COUNT

  return (
    <div className="store-locator">
      <div className="store-locator__header" onClick={() => stores.length > 0 && setCollapsed(!collapsed)}>
        <h3>
          Find This Nearby
          {!loading && stores.length > 0 && (
            <span className="store-locator__count">{stores.length} store{stores.length !== 1 ? 's' : ''}</span>
          )}
        </h3>
        {stores.length > 0 && (
          <button className="store-locator__collapse-btn" onClick={(e) => { e.stopPropagation(); setCollapsed(!collapsed) }}>
            {collapsed ? '▼' : '▲'}
          </button>
        )}
      </div>

      {!collapsed && (
        <>
          {/* Location source info */}
          {locSource === 'ip' && (
            <p className="store-locator__approx">
              Using approximate location from your IP address.
            </p>
          )}
          {locSource === 'manual' && (
            <p className="store-locator__approx">
              Showing results near "{manualInput.trim()}".
            </p>
          )}

          {/* Manual location input — always shown so user can override */}
          <form className="store-locator__manual" onSubmit={handleManualSearch}>
            <input
              type="text"
              placeholder="Enter 5-digit zip code or city..."
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              className="store-locator__manual-input"
            />
            <button type="submit" className="store-card__report-btn">Search</button>
          </form>
          {manualError && <p className="store-locator__manual-error">{manualError}</p>}

          {locLoading && <p className="status">Detecting your location...</p>}

          {loading && <p className="status">Searching for nearby stores...</p>}
          {error && <p className="status error">{error}</p>}

          {userPos && (
            <div className="store-locator__controls">
              <label>
                Search radius:
                <select value={radius} onChange={(e) => setRadius(Number(e.target.value))}>
                  <option value={2000}>1.2 mi</option>
                  <option value={5000}>3 mi</option>
                  <option value={10000}>6 mi</option>
                  <option value={25000}>15 mi</option>
                </select>
              </label>
            </div>
          )}

          {userPos && stores.length > 0 && (
            <StoreMap
              userPos={userPos}
              stores={stores}
              onStoreClick={(store) => setReportStore(store)}
            />
          )}

          {stores.length > 0 && (
            <>
              <div className="store-list">
                {visibleStores.map((store) => {
                  const si = statusInfo(store.latest_status)
                  return (
                    <div key={store.osm_id} className="store-card">
                      <div className="store-card__header">
                        <span className={`status-dot ${si.cls}`} title={si.label} />
                        <span className="store-card__name">{store.name}</span>
                        {store.distance_m != null && (
                          <span className="store-card__distance">
                            {formatDistance(store.distance_m)}
                          </span>
                        )}
                      </div>
                      {store.address && <p className="store-card__address">{store.address}</p>}
                      {store.opening_hours && (
                        <p className="store-card__hours">Hours: {store.opening_hours}</p>
                      )}
                      <div className="store-card__actions">
                        {store.report_count > 0 && (
                          <span className="store-card__reports">
                            {store.report_count} report{store.report_count !== 1 ? 's' : ''}
                            {' '}&mdash; {si.label}
                          </span>
                        )}
                        <button
                          className="store-card__report-btn"
                          onClick={() => setReportStore(store)}
                        >
                          Report Availability
                        </button>
                        {store.phone && (
                          <a href={`tel:${store.phone}`} className="store-card__phone">Call</a>
                        )}
                        {store.website && (
                          <a href={store.website} target="_blank" rel="noopener noreferrer" className="store-card__website">
                            Website
                          </a>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
              {hiddenCount > 0 && (
                <button className="store-locator__show-all" onClick={() => setShowAll(!showAll)}>
                  {showAll ? 'Show fewer' : `Show ${hiddenCount} more store${hiddenCount !== 1 ? 's' : ''}`}
                </button>
              )}
            </>
          )}

          {!loading && userPos && stores.length === 0 && !error && (
            <p className="store-locator__empty">
              No liquor stores found within {formatDistance(radius)}. Try increasing the radius.
            </p>
          )}
        </>
      )}

      {reportStore && (
        <ReportModal
          store={reportStore}
          whiskeyId={whiskeyId}
          whiskeyName={whiskeyName}
          onClose={() => setReportStore(null)}
          onSubmitted={handleReportSubmitted}
        />
      )}
    </div>
  )
}
