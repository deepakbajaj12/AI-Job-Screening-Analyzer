import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { coachingProgress, coachingStudyPack, coachingInterviewQuestions, coachingDiff, coachingSaveVersion } from '../api/client'
import MetricsChart from '../components/MetricsChart'

export default function Coaching() {
  const { token, user } = useAuth()
  const [progress, setProgress] = useState<any>(null)
  const [study, setStudy] = useState<any>(null)
  const [pendingSearch, setPendingSearch] = useState('')
  const [search, setSearch] = useState('')
  const [copiedLink, setCopiedLink] = useState<string | null>(null)
  const [copyTimer, setCopyTimer] = useState<number | null>(null)
  const [questions, setQuestions] = useState<string[]>([])
  const [role, setRole] = useState('Software Engineer')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [jdText, setJdText] = useState<string>('')
  const [diffData, setDiffData] = useState<any>(null)

  useEffect(() => {
    if (!token) return
    setError(null)
    ;(async () => {
      try {
        const p = await coachingProgress(token)
        setProgress(p)
        try { const s = await coachingStudyPack(token); setStudy(s) } catch {}
      } catch (e: any) { setError(e?.message || 'Failed to load coaching') }
    })()
  }, [token])

  // Debounce search
  useEffect(() => {
    const h = window.setTimeout(() => setSearch(pendingSearch.toLowerCase().trim()), 250)
    return () => window.clearTimeout(h)
  }, [pendingSearch])

  const filteredStudyPack = useMemo(() => {
    if (!study?.studyPack) return []
    if (!search) return study.studyPack
    return study.studyPack.filter((item: any) => {
      const skill = (item.skill || '').toLowerCase()
      const tags = Array.isArray(item.tags) ? item.tags.join(' ').toLowerCase() : ''
      const hosts = (item.resources || []).map((r: string) => {
        try { return new URL(r).hostname.toLowerCase() } catch { return (r || '').toLowerCase() }
      }).join(' ')
      return skill.includes(search) || tags.includes(search) || hosts.includes(search)
    })
  }, [study, search])

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedLink(text)
      if (copyTimer) window.clearTimeout(copyTimer)
      const t = window.setTimeout(() => setCopiedLink(null), 1500)
      setCopyTimer(t)
    } catch (err) {
      console.error('Clipboard copy failed', err)
    }
  }

  const loadQuestions = async () => {
    if (!token) return
    setLoading(true); setError(null)
    try {
      const res = await coachingInterviewQuestions(token, role)
      setQuestions(res?.questions || [])
    } catch (e: any) { setError(e?.message || 'Failed to load questions') }
    finally { setLoading(false) }
  }

  const saveVersion = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token || !resumeFile) { setError('Select a resume file'); return }
    setLoading(true); setError(null)
    try {
      const res = await coachingSaveVersion(token, { resume: resumeFile, jobDescription: jdText })
      setProgress(await coachingProgress(token))
      setStudy(await coachingStudyPack(token))
    } catch (err: any) { setError(err?.message || 'Save version failed') }
    finally { setLoading(false) }
  }

  const computeDiff = async () => {
    if (!token || !progress?.versions || progress.versions.length < 2) { setError('Need at least 2 versions'); return }
    const prev = progress.versions.length - 1
    const curr = progress.versions.length
    try {
      const d = await coachingDiff(token, prev, curr)
      setDiffData(d)
    } catch (e: any) { setError(e?.message || 'Diff failed') }
  }

  return (
    <section>
      <h2>Coaching Dashboard</h2>
      {!user && <div className="error">Sign in to use coaching features.</div>}

      <div className="card">
        <h3>Save New Version</h3>
        <form onSubmit={saveVersion}>
          <label>Resume (PDF)
            <input type="file" accept="application/pdf" onChange={e => setResumeFile(e.target.files?.[0] || null)} />
          </label>
          <label>Job Description (optional text)
            <textarea rows={4} value={jdText} onChange={e => setJdText(e.target.value)} />
          </label>
          <button className="btn" disabled={loading || !token}>Save Version</button>
        </form>
      </div>

      {progress?.versions && progress.versions.length > 0 ? (
        <MetricsChart versions={progress.versions} />
      ) : (
        <div className="card"><h3>Progress</h3><div>Loading or no versions yet.</div></div>
      )}

      <div className="card">
        <h3>Study Pack</h3>
        {study ? (
          <div>
            <div className="study-actions">
              <input
                type="text"
                placeholder="Search resources by skill, host, tags"
                value={pendingSearch}
                onChange={e => setPendingSearch(e.target.value)}
              />
              {copiedLink && <span className="copy-toast">Link copied!</span>}
            </div>
            <p>Skill Gaps:</p>
            <div className="chip-row">
              {(study.skillGaps || []).map((g:string, i:number) => (
                <span key={i} className="chip">{g}</span>
              ))}
            </div>
            <p style={{ marginTop:12 }}>Resources:</p>
            <div className="grid">
              {filteredStudyPack.map((item:any, i:number) => (
                <div key={i} className="card resource">
                  <div className="resource-head">
                    <span className="chip">{item.skill}</span>
                  </div>
                  <div className="resource-links">
                    {(item.resources || []).map((r:string, j:number) => {
                      let host = ''
                      try { host = new URL(r).hostname } catch { host = r }
                      return (
                        <div key={j} className="link-row">
                          <a href={r} target="_blank" rel="noreferrer" className="link">
                            {host}
                          </a>
                          <button className="copy-btn" onClick={() => copyToClipboard(r)}>Copy</button>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div>Generate by saving a version with JD.</div>
        )}
      </div>

      <div className="card">
        <h3>Interview Questions</h3>
        <label>Target Role
          <input type="text" value={role} onChange={e => setRole(e.target.value)} />
        </label>
        <button className="btn" onClick={loadQuestions} disabled={loading || !token}>Load Questions</button>
        {questions.length > 0 && (
          <ul>
            {questions.map((q, i) => <li key={i}>• {q}</li>)}
          </ul>
        )}
      </div>

      <div className="card">
        <h3>Diff (Last Two Versions)</h3>
        <button className="btn" onClick={computeDiff} disabled={!progress || !token}>Compute Diff</button>
        {diffData && <pre>{JSON.stringify(diffData, null, 2)}</pre>}
      </div>

      {error && <div className="error">{error}</div>}
    </section>
  )
}
