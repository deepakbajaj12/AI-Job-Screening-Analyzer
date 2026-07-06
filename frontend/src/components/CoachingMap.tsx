import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { coachingLocations, coachingSelectLocation, type CoachingMapLocation } from '../api/client'

type CoachingMapCoords = {
  lat: number
  lon: number
}

const DEFAULT_CENTER: CoachingMapCoords = {
  lat: 20,
  lon: 0,
}

type CoachingMapSelection = {
  selectedAt: string
  locationId: string
  location: CoachingMapLocation
  note?: string
}

type CoachingMapProps = {
  role?: string
  onSaved?: () => void | Promise<void>
}


// Read API key from Vite env — set VITE_GOOGLE_MAPS_API_KEY in frontend/.env
const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined

/** Build an embed iframe URL.
 *  - With key  → uses the official Maps Embed API v1 (no watermark, no rate-limit)
 *  - Without key → falls back to OpenStreetMap so the map is never blank.
 */
function buildEmbedUrl(locationQuery: string, center: CoachingMapCoords | null): string {
  const query = locationQuery.trim()

  if (GOOGLE_MAPS_API_KEY) {
    // Official Maps Embed API v1 — search mode
    if (query) {
      return `https://www.google.com/maps/embed/v1/search?key=${GOOGLE_MAPS_API_KEY}&q=${encodeURIComponent(query)}`
    }
    if (center) {
      return `https://www.google.com/maps/embed/v1/view?key=${GOOGLE_MAPS_API_KEY}&center=${center.lat},${center.lon}&zoom=13`
    }
    return `https://www.google.com/maps/embed/v1/search?key=${GOOGLE_MAPS_API_KEY}&q=coaching+centers`
  }

  // ── Fallback: OpenStreetMap (no API key needed) ────────────────────────────
  if (center) {
    const delta = 0.05
    return (
      `https://www.openstreetmap.org/export/embed.html` +
      `?bbox=${center.lon - delta}%2C${center.lat - delta}%2C${center.lon + delta}%2C${center.lat + delta}` +
      `&layer=mapnik&marker=${center.lat}%2C${center.lon}`
    )
  }
  // Generic world view
  return 'https://www.openstreetmap.org/export/embed.html?bbox=-180,-85,180,85&layer=mapnik'
}

export default function CoachingMap({ role, onSaved }: CoachingMapProps) {
  const { token } = useAuth()
  const [coords, setCoords] = useState<CoachingMapCoords | null>(null)
  const [status, setStatus] = useState('Type any location to see the top 5 coaching options.')
  const [searching, setSearching] = useState(false)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [locationQuery, setLocationQuery] = useState('')
  const [locations, setLocations] = useState<CoachingMapLocation[]>([])
  const [savedSelections, setSavedSelections] = useState<CoachingMapSelection[]>([])
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null)

  const activeCenter = coords ?? DEFAULT_CENTER

  const mapUrl = useMemo(() => buildEmbedUrl(locationQuery, activeCenter), [locationQuery, activeCenter])

  const refreshLocations = async (centerOverride?: CoachingMapCoords | null) => {
    if (!token) {
      setError('Sign in to search coaching locations.')
      return
    }

    if (!locationQuery.trim() && !centerOverride && !coords) {
      setError('Type a location to search coaching options.')
      return
    }

    const centerToUse = centerOverride ?? coords

    setSearching(true)
    setError(null)
    try {
      const data = await coachingLocations(token, {
        location: locationQuery.trim(),
        role: role,
        lat: centerToUse?.lat,
        lon: centerToUse?.lon,
      })
      setLocations(data.locations || [])
      setSavedSelections(data.savedSelections || [])
      if (data.center?.lat !== undefined && data.center?.lon !== undefined) {
        setCoords({ lat: data.center.lat, lon: data.center.lon })
      }
      setStatus(data.locations?.length ? `Found ${data.locations.length} nearby coaching options.` : 'No locations matched the current filters.')
    } catch (err: any) {
      setError(err?.message || 'Failed to load coaching locations')
    } finally {
      setSearching(false)
    }
  }

  useEffect(() => {
    if (!token) return
    void refreshLocations()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role])


  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported in this browser.')
      return
    }

    setSearching(true)
    setError(null)
    setStatus('Requesting your location...')

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const nextCoords = {
          lat: position.coords.latitude,
          lon: position.coords.longitude,
        }
        setCoords(nextCoords)
        setStatus('Map centered on your current location. Search to see the top 5 coaching options nearby.')
        void refreshLocations(nextCoords)
      },
      () => {
        setError('Location access was denied. Showing the default coaching map view.')
        setCoords(null)
        setStatus('Use your location to center the coaching map.')
        setSearching(false)
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000,
      }
    )
  }

  const saveLocation = async (location: CoachingMapLocation) => {
    if (!token) {
      setError('Sign in to save coaching locations.')
      return
    }

    setSavingId(location.id)
    setError(null)
    try {
      const saved = await coachingSelectLocation(token, { locationId: location.id, location })
      setSelectedLocationId(location.id)
      const savedSelection = saved.selection
      setSavedSelections(prev => [savedSelection, ...prev.filter(item => item.locationId !== savedSelection.locationId)])
      setStatus(`${location.name} saved to coaching progress.`)
      await onSaved?.()
    } catch (err: any) {
      setError(err?.message || 'Failed to save location')
    } finally {
      setSavingId(null)
    }
  }

  return (
    <div className="card coaching-map-card">
      <div className="coaching-map-header">
        <div>
          <h3>Coaching Map</h3>
          <p className="coaching-help-text">Type any location to see the top 5 coaching centers or mentors, then open each one in Google Maps.</p>
        </div>
      </div>

      <div className="coaching-map-controls">
        <label>Location
          <input type="text" value={locationQuery} onChange={e => setLocationQuery(e.target.value)} placeholder="e.g. Delhi, Pune, Hyderabad, or any place" />
        </label>
        <div className="coaching-map-actions">
          <button className="btn" onClick={useCurrentLocation} disabled={searching}>
            {searching ? 'Locating...' : 'Use My Location'}
          </button>
          <button className="btn secondary" onClick={() => refreshLocations()} disabled={searching || !token}>
            {searching ? 'Searching...' : 'Search Locations'}
          </button>
        </div>
      </div>

      <div className="coaching-map-meta">
        <span className="chip">Lat: {activeCenter.lat.toFixed(4)}</span>
        <span className="chip">Lon: {activeCenter.lon.toFixed(4)}</span>
        <span className="chip">Saved: {savedSelections.length}</span>
      </div>

      <div className="coaching-map-frame">
        <iframe
          title="Coaching map search"
          src={mapUrl}
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
        />
      </div>

      {status && <p className="coaching-map-status">{status}</p>}
      {error && <div className="coaching-map-error">{error}</div>}

      {locations.length > 0 && (
        <div className="coaching-map-results">
          {locations.map((location) => (
            <article key={location.id} className={`coaching-map-result ${selectedLocationId === location.id ? 'is-selected' : ''}`}>
              <div className="coaching-map-result-head">
                <div>
                  <h4>{location.name}</h4>
                  <p>{location.city}, {location.state}</p>
                </div>
                <span className="chip">{location.type}</span>
              </div>
              <p className="coaching-map-address">{location.address}</p>
              <div className="chip-row">
                {(location.roleTags || []).slice(0, 4).map(tag => <span key={tag} className="chip">{tag}</span>)}
                {typeof location.distanceKm === 'number' && <span className="chip">{location.distanceKm.toFixed(1)} km</span>}
                {typeof location.rating === 'number' && <span className="chip">{location.rating.toFixed(1)} ★</span>}
                {typeof location.score === 'number' && <span className="chip">Score {location.score.toFixed(0)}</span>}
              </div>
              <div className="coaching-map-result-actions">
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() => {
                    setCoords({ lat: location.lat, lon: location.lon })
                    setSelectedLocationId(location.id)
                  }}
                >
                  📍 Center on Map
                </button>
                <a className="btn secondary" href={location.googleMapsUrl || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${location.name}, ${location.address}, ${location.city}`)}`} target="_blank" rel="noreferrer">
                  Open in Google Maps
                </a>
                <button className="btn" onClick={() => saveLocation(location)} disabled={savingId === location.id}>
                  {savingId === location.id ? 'Saving...' : 'Save to Progress'}
                </button>
              </div>

            </article>
          ))}
        </div>
      )}

      {savedSelections.length > 0 && (
        <div className="coaching-map-saved">
          <h4>Saved Locations</h4>
          <div className="chip-row">
            {savedSelections.slice(0, 6).map(selection => (
              <span key={`${selection.locationId}-${selection.selectedAt}`} className="chip">
                {selection.location.name} - {selection.location.city}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}