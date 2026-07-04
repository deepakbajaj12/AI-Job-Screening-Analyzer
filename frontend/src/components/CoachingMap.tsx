import { useMemo, useState } from 'react'

type CoachingMapCoords = {
  lat: number
  lon: number
}

const DEFAULT_CENTER: CoachingMapCoords = {
  lat: 20,
  lon: 0,
}

function buildMapUrl(center: CoachingMapCoords) {
  const delta = 0.05
  const minLon = center.lon - delta
  const maxLon = center.lon + delta
  const minLat = center.lat - delta
  const maxLat = center.lat + delta
  return `https://www.openstreetmap.org/export/embed.html?bbox=${minLon}%2C${minLat}%2C${maxLon}%2C${maxLat}&layer=mapnik&marker=${center.lat}%2C${center.lon}`
}

export default function CoachingMap() {
  const [coords, setCoords] = useState<CoachingMapCoords | null>(null)
  const [status, setStatus] = useState('Use your location to center the coaching map.')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeCenter = coords ?? DEFAULT_CENTER

  const mapUrl = useMemo(() => buildMapUrl(activeCenter), [activeCenter])

  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported in this browser.')
      return
    }

    setLoading(true)
    setError(null)
    setStatus('Requesting your location...')

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCoords({
          lat: position.coords.latitude,
          lon: position.coords.longitude,
        })
        setStatus('Map centered on your current location.')
        setLoading(false)
      },
      () => {
        setError('Location access was denied. Showing the default coaching map view.')
        setCoords(null)
        setStatus('Use your location to center the coaching map.')
        setLoading(false)
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000,
      }
    )
  }

  return (
    <div className="card coaching-map-card">
      <div className="coaching-map-header">
        <div>
          <h3>Coaching Map</h3>
          <p className="coaching-help-text">Center the map on your location to discover nearby coaching options, study spots, or interview venues.</p>
        </div>
        <button className="btn" onClick={useCurrentLocation} disabled={loading}>
          {loading ? 'Locating...' : 'Use My Location'}
        </button>
      </div>

      <div className="coaching-map-meta">
        <span className="chip">Lat: {activeCenter.lat.toFixed(4)}</span>
        <span className="chip">Lon: {activeCenter.lon.toFixed(4)}</span>
      </div>

      <div className="coaching-map-frame">
        <iframe
          title="Coaching map"
          src={mapUrl}
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
        />
      </div>

      {status && <p className="coaching-map-status">{status}</p>}
      {error && <div className="coaching-map-error">{error}</div>}
    </div>
  )
}