import { useEffect, useState } from 'react'
import { getHealth, getVersion } from '../api/client'

export default function HealthBadge() {
  const [status, setStatus] = useState<'ok' | 'down' | 'checking'>('checking')
  const [version, setVersion] = useState<string>('')
  useEffect(() => {
    let mounted = true
    Promise.allSettled([getHealth(), getVersion()])
      .then(([h, v]) => {
        if (!mounted) return
        if (h.status === 'fulfilled' && h.value.status === 'ok') setStatus('ok')
        else setStatus('down')
        if (v.status === 'fulfilled') setVersion(v.value.version)
      })
      .catch(() => setStatus('down'))
    return () => { mounted = false }
  }, [])
  return (
    <span className={`badge ${status}`} title={`Backend ${version || ''}`}>
      {status === 'checking' ? 'Checking…' : status === 'ok' ? `Healthy${version ? ` · v${version}` : ''}` : 'Down'}
    </span>
  )
}
