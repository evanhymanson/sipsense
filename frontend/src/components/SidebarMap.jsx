import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'

// Fix default Leaflet marker icons (known bundler issue)
import iconUrl from 'leaflet/dist/images/marker-icon.png'
import iconShadow from 'leaflet/dist/images/marker-shadow.png'
import iconRetina from 'leaflet/dist/images/marker-icon-2x.png'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: iconRetina,
  iconUrl: iconUrl,
  shadowUrl: iconShadow,
})

function formatDistance(meters) {
  if (meters < 1000) return `${Math.round(meters)}m`
  return `${(meters / 1609.34).toFixed(1)} mi`
}

export default function SidebarMap({ stores, center }) {
  if (!stores?.length || !center) return null

  return (
    <div className="sb-map">
      <MapContainer
        center={[center.lat, center.lng]}
        zoom={13}
        style={{ height: '200px', width: '100%', borderRadius: '8px' }}
        scrollWheelZoom={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
        />
        {stores.map((store, i) => (
          <Marker key={i} position={[store.lat, store.lng]}>
            <Popup>
              <strong>{store.name}</strong>
              {store.address && <><br />{store.address}</>}
              {store.distance_m != null && <><br />{formatDistance(store.distance_m)} away</>}
              {store.opening_hours && <><br />Hours: {store.opening_hours}</>}
              {store.phone && <><br />Phone: {store.phone}</>}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      <div className="sb-map-list">
        {stores.slice(0, 5).map((store, i) => (
          <div key={i} className="sb-map-store">
            <span className="sb-map-store-name">{store.name}</span>
            {store.distance_m != null && (
              <span className="sb-map-store-dist">{formatDistance(store.distance_m)}</span>
            )}
          </div>
        ))}
        {stores.length > 5 && (
          <div className="sb-map-more">+{stores.length - 5} more stores</div>
        )}
      </div>
    </div>
  )
}
