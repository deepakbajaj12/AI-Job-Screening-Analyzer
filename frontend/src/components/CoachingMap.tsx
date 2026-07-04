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
  onSaved?: () => void | Promise<void>
}

function buildMapUrl(center: CoachingMapCoords) {
  const delta = 0.05
  const minLon = center.lon - delta
  const maxLon = center.lon + delta
  const minLat = center.lat - delta
  const maxLat = center.lat + delta
  return `https://www.openstreetmap.org/export/embed.html?bbox=${minLon}%2C${minLat}%2C${maxLon}%2C${maxLat}&layer=mapnik&marker=${center.lat}%2C${center.lon}`
}

export default function CoachingMap({ onSaved }: CoachingMapProps) {
  const { token } = useAuth()
  const [coords, setCoords] = useState<CoachingMapCoords | null>(null)
  const [status, setStatus] = useState('Use your location to center the coaching map.')
  const [searching, setSearching] = useState(false)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [role, setRole] = useState('Software Engineer')
  const [city, setCity] = useState('')
  const [radiusKm, setRadiusKm] = useState('250')
  const [locations, setLocations] = useState<CoachingMapLocation[]>([])
  const [savedSelections, setSavedSelections] = useState<CoachingMapSelection[]>([])
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null)

  const activeCenter = coords ?? (locations[0] ? { lat: locations[0].lat, lon: locations[0].lon } : DEFAULT_CENTER)

  const mapUrl = useMemo(() => buildMapUrl(activeCenter), [activeCenter])

  const refreshLocations = async (centerOverride?: CoachingMapCoords | null) => {
    if (!token) {
      setError('Sign in to search coaching locations.')
      return
    }

    const centerToUse = centerOverride ?? coords

    setSearching(true)
    setError(null)
    try {
      const data = await coachingLocations(token, {
        role: role.trim(),
        city: city.trim(),
        radiusKm: radiusKm ? Number(radiusKm) : undefined,
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
  }, [token])

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
        setStatus('Map centered on your current location.')
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
      const saved = await coachingSelectLocation(token, { locationId: location.id })
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
          <p className="coaching-help-text">Search by role, city, or radius, then save a nearby mentor or coaching center to your coaching progress.</p>
        </div>
      </div>

      <div className="coaching-map-controls">
        <label>Target Role
          <input type="text" value={role} onChange={e => setRole(e.target.value)} placeholder="e.g. Software Engineer" />
        </label>
        <label>City
          <input type="text" value={city} onChange={e => setCity(e.target.value)} placeholder="e.g. Bengaluru" />
        </label>
        <label>Radius (km)
          <input type="number" min="5" max="2000" value={radiusKm} onChange={e => setRadiusKm(e.target.value)} />
        </label>
        <div className="coaching-map-actions">
          <button className="btn" onClick={useCurrentLocation} disabled={searching}>
            {searching ? 'Locating...' : 'Use My Location'}
          </button>
          <button className="btn secondary" onClick={refreshLocations} disabled={searching || !token}>
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
          title="Coaching map"
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
              </div>
              <div className="coaching-map-result-actions">
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