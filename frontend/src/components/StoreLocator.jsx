import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import StoreMap from './StoreMap'
import ReportModal from './ReportModal'
import './StoreLocator.css'

export default function StoreLocator({ whiskeyId, whiskeyName }) {
  const [stores, setStores] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [userPos, setUserPos] = useState(null)
  const [locationDenied, setLocationDenied] = useState(false)
  const [reportStore, setReportStore] = useState(null)
  const [radius, setRadius] = useState(5000)


  useEffect(() => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => {
        setLocationDenied(true)
        setError('Location access denied. Enable location to find nearby stores.')
      },
      { enableHighAccuracy: false, timeout: 10000 }
    )
  }, [])

  const fetchStores = useCallback(async () => {
    if (!userPos) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.getStoresForWhiskey(whiskeyId, userPos.lat, userPos.lng, radius)
      setStores(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
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

  return (
    <div className="store-locator">
      <h3>Find This Nearby</h3>

      {locationDenied && (
        <p className="store-locator__denied">
          Enable location access in your browser to find nearby stores.
        </p>
      )}

      {loading && <p className="status">Searching for nearby stores...</p>}
      {error && !locationDenied && <p className="status error">{error}</p>}

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
        <div className="store-list">
          {stores.map((store) => {
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
      )}

      {!loading && userPos && stores.length === 0 && !error && (
        <p className="store-locator__empty">
          No liquor stores found within {formatDistance(radius)}. Try increasing the radius.
        </p>
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
