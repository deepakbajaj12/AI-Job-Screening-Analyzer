// COACHING DASHBOARD: Version tracking with progress metrics, skill gap analysis, study pack resources with filtering, interview questions, version comparison
import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { coachingProgress, coachingStudyPack, coachingInterviewQuestions, coachingDiff, coachingSaveVersion, downloadCoachingReportPdf } from '../api/client'
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
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [jdText, setJdText] = useState<string>('')
  const [diffData, setDiffData] = useState<any>(null)
  const [saveNotice, setSaveNotice] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    setError(null)
    ;(async () => {
      try {
        const p = await coachingProgress(token)
        setProgress(p)
        try {
          const s = await coachingStudyPack(token)
          setStudy(s)
        } catch {
          setStudy(null)
        }
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
    setSaveNotice(null)
    setSaveError(null)
    if (!token) {
      setSaveError('Sign in first to save coaching versions.')
      return
    }
    if (!resumeFile) {
      setSaveError('Select a resume PDF before saving.')
      return
    }
    setLoading(true); setError(null)
    try {
      const saved = await coachingSaveVersion(token, { resume: resumeFile, jobDescription: jdText })
      setProgress(await coachingProgress(token))
      setStudy(await coachingStudyPack(token))
      const versionNumber = saved?.saved?.version
      setSaveNotice(versionNumber ? `Version v${versionNumber} saved successfully.` : 'Version saved successfully.')
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

  const handleDownloadProgressPdf = async () => {
    if (!progress) return
    setDownloadingPdf(true)
    try {
      await downloadCoachingReportPdf(token, progress, 'progress')
    } catch (err: any) {
      setError(err?.message || 'Failed to download PDF')
    } finally {
      setDownloadingPdf(false)
    }
  }

  const handleDownloadStudyPackPdf = async () => {
    if (!study) return
    setDownloadingPdf(true)
    try {
      await downloadCoachingReportPdf(token, study, 'study_pack')
    } catch (err: any) {
      setError(err?.message || 'Failed to download PDF')
    } finally {
      setDownloadingPdf(false)
    }
  }

  return (
    <section>
      <h2>Coaching Dashboard</h2>
      {!user && <div className="error">Sign in to use coaching features.</div>}

      <div className="card">
        <h3>Save New Version</h3>
        <p className="coaching-help-text">Upload your resume and a job description to generate a personalized study pack with skill gaps and learning resources.</p>
        <form onSubmit={saveVersion}>
          <label>Resume (PDF)
            <input type="file" accept="application/pdf" onChange={e => setResumeFile(e.target.files?.[0] || null)} />
          </label>
          <label>Job Description (paste JD with skills like Python, React, Docker, AWS)
            <textarea rows={4} value={jdText} onChange={e => setJdText(e.target.value)} placeholder="Paste job description here. Include skills and requirements." />
          </label>
          <button className="btn" disabled={loading || !token}>{loading ? 'Saving...' : 'Save Version'}</button>
          {saveError && <div className="error coaching-inline-message">{saveError}</div>}
          {saveNotice && <div className="coaching-success-message coaching-inline-message">{saveNotice}</div>}
          {!token && <div className="coaching-help-text">Sign in to enable save.</div>}
        </form>
      </div>

      {progress?.versions && progress.versions.length > 0 ? (
        <div>
          <div className="card" style={{ marginBottom: '15px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
              <h3>Progress</h3>
              <button className="btn" style={{ backgroundColor: '#007bff' }} onClick={handleDownloadProgressPdf} disabled={downloadingPdf}>📄 Download PDF</button>
            </div>
            <MetricsChart versions={progress.versions} />
          </div>
        </div>
      ) : (
        <div className="card"><h3>Progress</h3><div>Loading or no versions yet.</div></div>
      )}

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
          <h3>Study Pack</h3>
          {study && <button className="btn" style={{ backgroundColor: '#007bff' }} onClick={handleDownloadStudyPackPdf} disabled={downloadingPdf}>📄 Download PDF</button>}
        </div>
        {study ? (
          <div>
            {study.skillGaps?.length > 0 && <p className="coaching-help-text">Found {study.skillGaps.length} skill gaps.</p>}
            <div className="study-actions">
              <input
                type="text"
                placeholder="Filter resources by skill name"
                value={pendingSearch}
                onChange={e => setPendingSearch(e.target.value)}
              />
              {copiedLink && <span className="copy-toast">Link copied!</span>}
            </div>
            <p>Skill Gaps:</p>
            <div className="chip-row">
              {(study.skillGaps || []).length > 0 ? (
                (study.skillGaps || []).map((g:string, i:number) => (
                  <span key={i} className="chip">{g}</span>
                ))
              ) : (
                <p className="coaching-help-text">No gaps detected. Save a version with a detailed job description.</p>
              )}
            </div>
            <p className="study-resources-label">Resources:</p>
            {study.studyPack?.length === 0 ? (
              <div className="coaching-help-text">No study resources yet. Save a version with a detailed job description to generate skill gaps.</div>
            ) : filteredStudyPack.length === 0 ? (
              <div className="coaching-help-text">No resources match your current search.</div>
            ) : (
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
            )}
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
        {diffData && (
          <div className="diff-container">
            <div className="diff-section">
              <h4>📊 Version Comparison</h4>
              <p className="diff-meta">Version {diffData.prevVersion} → Version {diffData.currVersion}</p>
            </div>

            {/* Skills Changes */}
            {(diffData.addedSkills?.length > 0 || diffData.removedSkills?.length > 0) && (
              <div className="diff-section">
                <h4>🎯 Skills Changes</h4>
                {diffData.addedSkills?.length > 0 && (
                  <div className="skills-change added">
                    <strong>✅ Added Skills ({diffData.addedSkills.length})</strong>
                    <div className="skills-list">
                      {diffData.addedSkills.map((skill: string, i: number) => (
                        <span key={i} className="skill-tag-added">{skill}</span>
                      ))}
                    </div>
                  </div>
                )}
                {diffData.removedSkills?.length > 0 && (
                  <div className="skills-change removed">
                    <strong>❌ Removed Skills ({diffData.removedSkills.length})</strong>
                    <div className="skills-list">
                      {diffData.removedSkills.map((skill: string, i: number) => (
                        <span key={i} className="skill-tag-removed">{skill}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Metrics Changes */}
            {diffData.metricDeltas && (
              <div className="diff-section">
                <h4>📈 Metrics Comparison</h4>
                <table className="diff-table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Version {diffData.prevVersion}</th>
                      <th>Version {diffData.currVersion}</th>
                      <th>Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {diffData.currMetrics && (
                      <>
                        <tr>
                          <td>Word Count</td>
                          <td>{diffData.prevMetrics?.wordCount || 0}</td>
                          <td>{diffData.currMetrics.wordCount}</td>
                          <td className={diffData.metricDeltas.wordCount >= 0 ? 'positive' : 'negative'}>
                            {diffData.metricDeltas.wordCount > 0 ? '+' : ''}{diffData.metricDeltas.wordCount}
                          </td>
                        </tr>
                        <tr>
                          <td>Bullet Points</td>
                          <td>{diffData.prevMetrics?.bulletCount || 0}</td>
                          <td>{diffData.currMetrics.bulletCount}</td>
                          <td className={diffData.metricDeltas.bulletCount >= 0 ? 'positive' : 'negative'}>
                            {diffData.metricDeltas.bulletCount > 0 ? '+' : ''}{diffData.metricDeltas.bulletCount}
                          </td>
                        </tr>
                        <tr>
                          <td>Skills Found</td>
                          <td>{diffData.prevMetrics?.skillCount || 0}</td>
                          <td>{diffData.currMetrics.skillCount}</td>
                          <td className={diffData.metricDeltas.skillCount >= 0 ? 'positive' : 'negative'}>
                            {diffData.metricDeltas.skillCount > 0 ? '+' : ''}{diffData.metricDeltas.skillCount}
                          </td>
                        </tr>
                        <tr>
                          <td>Skill Coverage</td>
                          <td>{((diffData.prevMetrics?.skillCoverageRatio || 0) * 100).toFixed(1)}%</td>
                          <td>{(diffData.currMetrics.skillCoverageRatio * 100).toFixed(1)}%</td>
                          <td className={diffData.metricDeltas.skillCoverageRatio >= 0 ? 'positive' : 'negative'}>
                            {diffData.metricDeltas.skillCoverageRatio > 0 ? '+' : ''}{(diffData.metricDeltas.skillCoverageRatio * 100).toFixed(1)}%
                          </td>
                        </tr>
                        <tr>
                          <td>Avg Bullet Word Count</td>
                          <td>{diffData.prevMetrics?.avgBulletWordCount?.toFixed(2) || '0.00'}</td>
                          <td>{diffData.currMetrics.avgBulletWordCount.toFixed(2)}</td>
                          <td className={diffData.metricDeltas.avgBulletWordCount >= 0 ? 'positive' : 'negative'}>
                            {diffData.metricDeltas.avgBulletWordCount > 0 ? '+' : ''}{diffData.metricDeltas.avgBulletWordCount.toFixed(2)}
                          </td>
                        </tr>
                      </>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Summary */}
            <div className="diff-summary">
              <div className="summary-item">
                <span>Total Changes:</span>
                <strong>{(diffData.addedSkills?.length || 0) + (diffData.removedSkills?.length || 0) + Object.keys(diffData.metricDeltas || {}).length} updates</strong>
              </div>
            </div>
          </div>
        )}
      </div>

      {error && <div className="error">{error}</div>}
    </section>
  )
}
