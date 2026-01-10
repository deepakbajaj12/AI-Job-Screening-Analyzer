import { useEffect, useState } from 'react'
import { getHealth, getVersion } from '../api/client'

export default function HealthBadge() {
  const [status, setStatus] = useState<'ok' | 'down' | 'checking'>('checking')
  const [version, setVersion] = useState<string>('')
  useEffect(() => {
    const controller = new AbortController()
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
      .catch((e) => {
        if (!controller.signal.aborted) setStatus('down')
      })
    return () => { controller.abort() }
  }, [])
  return (
    <span className={`badge ${status}`} title={`Backend ${version || ''}`}>
      {status === 'checking' ? 'Checking…' : status === 'ok' ? `Healthy${version ? ` · v${version}` : ''}` : 'Down'}
    </span>
  )
}
