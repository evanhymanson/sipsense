import { MapContainer, TileLayer, Marker, Popup, Circle } from 'react-leaflet'
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

export default function StoreMap({ userPos, stores, onStoreClick }) {
  return (
    <div className="store-map-container">
      <MapContainer
        center={[userPos.lat, userPos.lng]}
        zoom={13}
        style={{ height: '300px', width: '100%' }}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
        />
        {/* User position */}
        <Circle
          center={[userPos.lat, userPos.lng]}
          radius={50}
          pathOptions={{ color: '#c8872a', fillColor: '#c8872a', fillOpacity: 0.6 }}
        />
        {/* Store markers */}
        {stores.map((store) => (
          <Marker
            key={store.osm_id}
            position={[store.lat, store.lng]}
            eventHandlers={{ click: () => onStoreClick(store) }}
          >
            <Popup>
              <strong>{store.name}</strong>
              {store.address && <><br />{store.address}</>}
              {store.latest_status && (
                <><br />Status: {store.latest_status.replace('_', ' ')}</>
              )}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  )
}
