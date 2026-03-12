import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { getHistory } from '../api/client'

interface HistoryEntry {
  mode: string
  timestamp: string
  strengths?: string[]
  improvementAreas?: string[]
  recommendedRoles?: string[]
  generalFeedback?: string
  lexicalMatchPercentage?: number
  semanticMatchPercentage?: number
  combinedMatchPercentage?: number
}

export default function History() {
  const { user, token } = useAuth()
  const [entries, setEntries] = useState<HistoryEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)

  useEffect(() => {
    if (!token) return
    setLoading(true)
    setError('')
    getHistory(token)
      .then(data => setEntries(data.history ?? []))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [token])

  if (!user) {
    return (
      <div>
        <h2>Analysis History</h2>
        <div className="card"><p style={{ color: 'var(--muted)' }}>Please sign in to view your analysis history.</p></div>
      </div>
    )
  }

  return (
    <div>
      <h2>Analysis History</h2>
      <p style={{ color: 'var(--muted)', marginBottom: 24 }}>Your past resume analyses stored in the cloud.</p>

      {loading && <p>Loading history...</p>}
      {error && <div className="error">{error}</div>}

      {!loading && !error && entries.length === 0 && (
        <div className="card">
          <p style={{ color: 'var(--muted)' }}>No analyses yet. Go to <a href="/job-seeker">Job Seeker</a> or <a href="/recruiter">Recruiter</a> to run your first analysis.</p>
        </div>
      )}

      {entries.map((entry, idx) => (
        <div className="card" key={idx} style={{ cursor: 'pointer' }} onClick={() => setExpanded(expanded === idx ? null : idx)}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span className="chip" style={{ marginRight: 8 }}>
                {entry.mode === 'recruiter' ? '👔 Recruiter' : '🎯 Job Seeker'}
              </span>
              <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
                {new Date(entry.timestamp).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
            {entry.combinedMatchPercentage != null && (
              <span style={{ fontWeight: 700, color: entry.combinedMatchPercentage >= 70 ? 'var(--success)' : entry.combinedMatchPercentage >= 50 ? '#f59e0b' : 'var(--danger)' }}>
                {entry.combinedMatchPercentage.toFixed(1)}% Match
              </span>
            )}
            <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>{expanded === idx ? '▲' : '▼'}</span>
          </div>

          {expanded === idx && (
            <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
              {entry.lexicalMatchPercentage != null && (
                <div style={{ display: 'flex', gap: 24, marginBottom: 16 }}>
                  <ScoreBadge label="Lexical" value={entry.lexicalMatchPercentage} />
                  <ScoreBadge label="Semantic" value={entry.semanticMatchPercentage ?? 0} />
                  <ScoreBadge label="Combined" value={entry.combinedMatchPercentage ?? 0} />
                </div>
              )}

              {entry.strengths && entry.strengths.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <h4 style={{ margin: '0 0 6px', fontSize: '0.9rem' }}>Strengths</h4>
                  <div className="chip-row">
                    {entry.strengths.map((s, i) => <span className="chip" key={i}>{s}</span>)}
                  </div>
                </div>
              )}

              {entry.improvementAreas && entry.improvementAreas.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <h4 style={{ margin: '0 0 6px', fontSize: '0.9rem' }}>Areas to Improve</h4>
                  <div className="chip-row">
                    {entry.improvementAreas.map((s, i) => <span className="chip" key={i}>{s}</span>)}
                  </div>
                </div>
              )}

              {entry.recommendedRoles && entry.recommendedRoles.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <h4 style={{ margin: '0 0 6px', fontSize: '0.9rem' }}>Recommended Roles</h4>
                  <div className="chip-row">
                    {entry.recommendedRoles.map((r, i) => <span className="chip" key={i}>{r}</span>)}
                  </div>
                </div>
              )}

              {entry.generalFeedback && (
                <div style={{ marginTop: 12, padding: 12, background: 'var(--bg)', borderRadius: 'var(--radius)', fontSize: '0.85rem', whiteSpace: 'pre-wrap' }}>
                  {entry.generalFeedback}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function ScoreBadge({ label, value }: { label: string; value: number }) {
  const color = value >= 70 ? 'var(--success)' : value >= 50 ? '#f59e0b' : 'var(--danger)'
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '1.5rem', fontWeight: 700, color }}>{value.toFixed(0)}%</div>
      <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>{label}</div>
    </div>
  )
}
