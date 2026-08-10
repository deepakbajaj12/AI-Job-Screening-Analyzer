import { useEffect, useState } from 'react'
import { getHealth, getVersion } from '../api/client'

export default function HealthBadge() {
  const [status, setStatus] = useState<'ok' | 'down' | 'checking'>('checking')
  const [version, setVersion] = useState<string>('')

  useEffect(() => {
    const controller = new AbortController()

    // Render free tier cold-starts can take up to 60s — use a generous timeout
    const timer = setTimeout(() => {
      if (status === 'checking') setStatus('down')
    }, 65000)

    Promise.allSettled([
      getHealth(controller.signal),
      getVersion(controller.signal)
    ])
      .then(([h, v]) => {
        if (controller.signal.aborted) return
        if (h.status === 'fulfilled' && h.value.status === 'ok') setStatus('ok')
        else setStatus('down')
        if (v.status === 'fulfilled') setVersion(v.value.version)
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus('down')
      })
      .finally(() => clearTimeout(timer))

    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [])

  return (
    <span
      className={`badge ${status}`}
      title={status === 'checking' ? 'Waiting for backend to wake up (free tier cold-start ~30s)…' : `Backend ${version || ''}`}
    >
      {status === 'checking'
        ? '⏳ Waking up…'
        : status === 'ok'
        ? `✅ Healthy${version ? ` · v${version}` : ''}`
        : '🔴 Down'}
    </span>
  )
}
