import { useEffect, useMemo, useState } from 'react'
import {
  analyzeRecruiter,
  ApiError,
  generateBooleanSearch,
  generateEmail,
  generateJobDescription,
  getRecruiterTemplate,
  listRecruiterTemplates,
  saveRecruiterTemplate,
  type RecruiterTemplate,
  type RecruiterTemplateSummary,
} from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Recruiter() {
  const { token } = useAuth()
  const [resume, setResume] = useState<File | null>(null)
  const [jd, setJd] = useState<File | null>(null)
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  
  // Email Assistant State
  const [candidateName, setCandidateName] = useState('')
  const [jobTitle, setJobTitle] = useState('')
  const [emailType, setEmailType] = useState('interview_invite')
  const [generatedEmail, setGeneratedEmail] = useState('')

  // JD Generator State
  const [jdTitle, setJdTitle] = useState('')
  const [jdSkills, setJdSkills] = useState('')
  const [jdExperience, setJdExperience] = useState('')
  const [generatedJD, setGeneratedJD] = useState('')

  // Boolean Search State
  const [searchJD, setSearchJD] = useState('')
  const [generatedSearch, setGeneratedSearch] = useState<any>(null)

  // Rate-limit UX
  const [rateLimitRemaining, setRateLimitRemaining] = useState(0)
  const [rateLimitUntil, setRateLimitUntil] = useState<number | null>(null)

  // Template state
  const [templates, setTemplates] = useState<RecruiterTemplateSummary[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<RecruiterTemplate | null>(null)
  const [templateFilter, setTemplateFilter] = useState<'all' | 'email' | 'job_description'>('all')
  const [emailTemplateTitle, setEmailTemplateTitle] = useState('')
  const [jdTemplateTitle, setJdTemplateTitle] = useState('')
  const [emailTemplateId, setEmailTemplateId] = useState<string | undefined>(undefined)
  const [jdTemplateId, setJdTemplateId] = useState<string | undefined>(undefined)
  const [copyMessage, setCopyMessage] = useState<string | null>(null)

  const actionsBlocked = loading || rateLimitRemaining > 0

  const generatedJdForSave = useMemo(() => {
    if (!generatedJD) return ''
    return typeof generatedJD === 'string' ? generatedJD : JSON.stringify(generatedJD, null, 2)
  }, [generatedJD])

  useEffect(() => {
    if (!token) {
      setTemplates([])
      return
    }
    void refreshTemplates()
  }, [token, templateFilter])

  useEffect(() => {
    if (!rateLimitUntil) return
    const timer = setInterval(() => {
      const seconds = Math.max(0, Math.ceil((rateLimitUntil - Date.now()) / 1000))
      setRateLimitRemaining(seconds)
      if (seconds === 0) {
        setRateLimitUntil(null)
      }
    }, 250)
    return () => clearInterval(timer)
  }, [rateLimitUntil])

  useEffect(() => {
    if (!copyMessage) return
    const timer = setTimeout(() => setCopyMessage(null), 1800)
    return () => clearTimeout(timer)
  }, [copyMessage])

  const refreshTemplates = async () => {
    try {
      const kind = templateFilter === 'all' ? undefined : templateFilter
      const data = await listRecruiterTemplates(token, kind)
      setTemplates(data.templates || [])
    } catch {
      // Template list is non-blocking for recruiter workflows.
    }
  }

  const handleApiError = (err: any, fallbackMessage: string) => {
    if (err instanceof ApiError && err.status === 429) {
      const retryAfter = Math.max(1, Math.ceil(err.retryAfterSeconds || 30))
      setRateLimitUntil(Date.now() + retryAfter * 1000)
      setRateLimitRemaining(retryAfter)
      setError(`You are sending requests too quickly. Please retry in ${retryAfter} seconds.`)
      return
    }
    setError(err?.message || fallbackMessage)
  }

  const handleCopy = async (value: string, label: string) => {
    if (!value) return
    try {
      await navigator.clipboard.writeText(value)
      setCopyMessage(`${label} copied`)
    } catch {
      setCopyMessage('Copy failed')
    }
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null); setResult(null)
    if (!resume || !jd || !email) { setError('Provide resume, JD PDF and recruiter email'); return }
    setLoading(true)
    try {
      const data = await analyzeRecruiter(token, { resume, jobDescription: jd, recruiterEmail: email })
      setResult(data)
    } catch (err: any) {
      handleApiError(err, 'Analyze failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateEmail = async () => {
    setLoading(true)
    try {
      const data = await generateEmail(token, { type: emailType, candidateName, jobTitle })
      setGeneratedEmail(data.email)
      setEmailTemplateTitle((prev) => prev || `${candidateName || 'Candidate'} - ${jobTitle || 'Role'} - ${emailType}`)
    } catch (err: any) {
      handleApiError(err, 'Email generation failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateJD = async () => {
    setLoading(true)
    try {
      const data = await generateJobDescription(token, { title: jdTitle, skills: jdSkills, experience: jdExperience })
      setGeneratedJD(data.job_description)
      setJdTemplateTitle((prev) => prev || `${jdTitle || 'Job Description'} Template`)
    } catch (err: any) {
      handleApiError(err, 'JD generation failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateSearch = async () => {
    if (!searchJD.trim()) return
    setLoading(true)
    try {
      const data = await generateBooleanSearch(token, { jobDescription: searchJD })
      setGeneratedSearch(data)
    } catch (err: any) {
      handleApiError(err, 'Search generation failed')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveEmailTemplate = async () => {
    if (!generatedEmail) return
    setLoading(true)
    setError(null)
    try {
      const payload = {
        kind: 'email' as const,
        title: emailTemplateTitle.trim() || `Email - ${emailType}`,
        content: generatedEmail,
        metadata: { candidateName, jobTitle, emailType },
        templateId: emailTemplateId,
      }
      const data = await saveRecruiterTemplate(token, payload)
      setEmailTemplateId(data.template.id)
      setEmailTemplateTitle(data.template.title)
      await refreshTemplates()
      setCopyMessage('Email template saved')
    } catch (err: any) {
      handleApiError(err, 'Failed to save email template')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveJdTemplate = async () => {
    if (!generatedJdForSave) return
    setLoading(true)
    setError(null)
    try {
      const payload = {
        kind: 'job_description' as const,
        title: jdTemplateTitle.trim() || `JD - ${jdTitle || 'Role'}`,
        content: generatedJdForSave,
        metadata: { title: jdTitle, skills: jdSkills, experience: jdExperience },
        templateId: jdTemplateId,
      }
      const data = await saveRecruiterTemplate(token, payload)
      setJdTemplateId(data.template.id)
      setJdTemplateTitle(data.template.title)
      await refreshTemplates()
      setCopyMessage('JD template saved')
    } catch (err: any) {
      handleApiError(err, 'Failed to save JD template')
    } finally {
      setLoading(false)
    }
  }

  const openTemplate = async (templateId: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getRecruiterTemplate(token, templateId)
      setSelectedTemplate(data.template)
    } catch (err: any) {
      handleApiError(err, 'Failed to load template details')
    } finally {
      setLoading(false)
    }
  }

  const applyTemplateVersion = (template: RecruiterTemplate, version: number) => {
    const v = template.versions.find((item) => item.version === version)
    if (!v) return
    if (template.kind === 'email') {
      setGeneratedEmail(String(v.content || ''))
      setEmailTemplateId(template.id)
      setEmailTemplateTitle(template.title)
    } else {
      setGeneratedJD(String(v.content || ''))
      setJdTemplateId(template.id)
      setJdTemplateTitle(template.title)
    }
    setCopyMessage(`Loaded ${template.title} v${version}`)
  }

  return (
    <section>
      <h2>Recruiter Tools</h2>
      
      <div className='card'>
        <h3>Candidate Analysis</h3>
        <form onSubmit={onSubmit}>
          <label>Resume (PDF)
            <input type='file' accept='application/pdf' onChange={e => setResume(e.target.files?.[0] || null)} />
          </label>
          <label>Job Description (PDF)
            <input type='file' accept='application/pdf' onChange={e => setJd(e.target.files?.[0] || null)} />
          </label>
          <label>Recruiter Email
            <input type='email' value={email} onChange={e => setEmail(e.target.value)} placeholder='name@company.com' />
          </label>
          <button className='btn' disabled={actionsBlocked}>{loading ? 'Analyzing' : 'Analyze'}</button>
        </form>
      </div>

      <div className='card'>
        <h3>Smart Boolean Search Generator</h3>
        <div style={{ display: 'flex', gap: '10px', flexDirection: 'column' }}>
          <label>Job Description / Requirements
            <textarea 
              rows={4} 
              value={searchJD} 
              onChange={e => setSearchJD(e.target.value)} 
              placeholder="Paste job description or key requirements here..." 
            />
          </label>
          <button className='btn' onClick={handleGenerateSearch} disabled={actionsBlocked}>Generate Boolean String</button>
        </div>
        {generatedSearch && (
          <div style={{ marginTop: '10px' }}>
            <h4>Boolean String:</h4>
            <div style={{ background: '#f8f9fa', padding: '10px', borderRadius: '5px', fontFamily: 'monospace', border: '1px solid #ddd' }}>
              {typeof generatedSearch.boolean_string === 'string' 
                ? generatedSearch.boolean_string 
                : JSON.stringify(generatedSearch.boolean_string || generatedSearch.raw_response || generatedSearch)
              }
            </div>
            <p style={{ marginTop: '10px', fontSize: '0.9em', color: '#666' }}>
              <strong>Strategy:</strong> {typeof generatedSearch.explanation === 'string' 
                ? generatedSearch.explanation 
                : (JSON.stringify(generatedSearch.explanation) || '')}
            </p>
          </div>
        )}
      </div>

      <div className='card'>
        <h3>Email Assistant</h3>
        <div style={{ display: 'flex', gap: '10px', flexDirection: 'column' }}>
          <label>Candidate Name
            <input type='text' value={candidateName} onChange={e => setCandidateName(e.target.value)} />
          </label>
          <label>Job Title
            <input type='text' value={jobTitle} onChange={e => setJobTitle(e.target.value)} />
          </label>
          <label>Email Type
            <select value={emailType} onChange={e => setEmailType(e.target.value)}>
              <option value='interview_invite'>Interview Invite</option>
              <option value='rejection'>Rejection</option>
              <option value='offer'>Offer</option>
            </select>
          </label>
          <button className='btn' onClick={handleGenerateEmail} disabled={actionsBlocked}>Generate Email</button>
        </div>
        {generatedEmail && (
          <div style={{ marginTop: '10px' }}>
            <h4>Generated Email:</h4>
            <pre className='report' style={{ whiteSpace: 'pre-wrap' }}>
              {typeof generatedEmail === 'string' ? generatedEmail : JSON.stringify(generatedEmail, null, 2)}
            </pre>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <input
                type='text'
                value={emailTemplateTitle}
                onChange={e => setEmailTemplateTitle(e.target.value)}
                placeholder='Template title'
              />
              <button className='btn secondary' onClick={() => handleCopy(generatedEmail, 'Email')} disabled={actionsBlocked}>Copy Email</button>
              <button className='btn secondary' onClick={handleSaveEmailTemplate} disabled={actionsBlocked}>Save as Template</button>
            </div>
          </div>
        )}
      </div>

      <div className='card'>
        <h3>Job Description Generator</h3>
        <div style={{ display: 'flex', gap: '10px', flexDirection: 'column' }}>
          <label>Job Title
            <input type='text' value={jdTitle} onChange={e => setJdTitle(e.target.value)} placeholder="e.g. Senior React Developer" />
          </label>
          <label>Required Skills
            <input type='text' value={jdSkills} onChange={e => setJdSkills(e.target.value)} placeholder="e.g. React, TypeScript, Node.js" />
          </label>
          <label>Experience Level
            <input type='text' value={jdExperience} onChange={e => setJdExperience(e.target.value)} placeholder="e.g. 5+ years" />
          </label>
          <button className='btn' onClick={handleGenerateJD} disabled={actionsBlocked}>Generate JD</button>
        </div>
        {generatedJD && (
          <div style={{ marginTop: '10px' }}>
            <h4>Generated Job Description:</h4>
            {typeof generatedJD === 'string' ? (
              <pre className='report' style={{ whiteSpace: 'pre-wrap' }}>{generatedJD}</pre>
            ) : (
              <div className='report' style={{ padding: '20px', lineHeight: '1.6', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
                <h2 style={{ marginTop: 0, color: 'var(--accent)', borderBottom: '2px solid var(--accent)', paddingBottom: '10px' }}>{generatedJD.title}</h2>
                
                <section style={{ marginBottom: '20px' }}>
                  <h3 style={{ color: 'var(--fg)' }}>Overview</h3>
                  <p style={{ color: 'var(--muted)' }}>{generatedJD.overview}</p>
                </section>

                <section style={{ marginBottom: '20px' }}>
                  <h3 style={{ color: 'var(--fg)' }}>Key Responsibilities</h3>
                  <ul style={{ paddingLeft: '20px' }}>
                    {generatedJD.responsibilities?.map((item: string, i: number) => (
                      <li key={i} style={{ marginBottom: '8px', color: 'var(--muted)' }}>{item}</li>
                    ))}
                  </ul>
                </section>

                <section style={{ marginBottom: '20px' }}>
                  <h3 style={{ color: 'var(--fg)' }}>Required Skills & Experience</h3>
                  <ul style={{ paddingLeft: '20px' }}>
                    {generatedJD.skills_and_experience?.required?.map((item: string, i: number) => (
                      <li key={i} style={{ marginBottom: '8px', color: 'var(--muted)' }}>{item}</li>
                    ))}
                  </ul>
                </section>

                {generatedJD.skills_and_experience?.preferred && generatedJD.skills_and_experience.preferred.length > 0 && (
                  <section style={{ marginBottom: '20px' }}>
                    <h3 style={{ color: 'var(--fg)' }}>Preferred Qualifications</h3>
                    <ul style={{ paddingLeft: '20px' }}>
                      {generatedJD.skills_and_experience.preferred.map((item: string, i: number) => (
                        <li key={i} style={{ marginBottom: '8px', color: 'var(--muted)' }}>{item}</li>
                      ))}
                    </ul>
                  </section>
                )}

                {generatedJD.benefits && generatedJD.benefits.length > 0 && (
                  <section style={{ marginBottom: '20px' }}>
                    <h3 style={{ color: 'var(--fg)' }}>What We Offer</h3>
                    <ul style={{ paddingLeft: '20px' }}>
                      {generatedJD.benefits.map((item: string, i: number) => (
                        <li key={i} style={{ marginBottom: '8px', color: 'var(--muted)' }}>{item}</li>
                      ))}
                    </ul>
                  </section>
                )}
              </div>
            )}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px' }}>
              <input
                type='text'
                value={jdTemplateTitle}
                onChange={e => setJdTemplateTitle(e.target.value)}
                placeholder='Template title'
              />
              <button className='btn secondary' onClick={() => handleCopy(generatedJdForSave, 'Job description')} disabled={actionsBlocked}>Copy JD</button>
              <button className='btn secondary' onClick={handleSaveJdTemplate} disabled={actionsBlocked}>Save as Template</button>
            </div>
          </div>
        )}
      </div>

      <div className='card'>
        <h3>Reusable Templates</h3>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '12px' }}>
          <label style={{ marginBottom: 0 }}>Filter</label>
          <select value={templateFilter} onChange={e => setTemplateFilter(e.target.value as 'all' | 'email' | 'job_description')}>
            <option value='all'>All</option>
            <option value='email'>Email</option>
            <option value='job_description'>Job Description</option>
          </select>
          <button className='btn secondary' onClick={refreshTemplates} disabled={actionsBlocked}>Refresh</button>
        </div>

        {templates.length === 0 ? (
          <p style={{ color: 'var(--muted)' }}>No templates saved yet.</p>
        ) : (
          <div className='grid'>
            {templates.map((item) => (
              <div key={item.id} className='card' style={{ marginBottom: 0 }}>
                <h4>{item.title}</h4>
                <p style={{ color: 'var(--muted)' }}>Type: {item.kind === 'email' ? 'Email' : 'Job Description'}</p>
                <p style={{ color: 'var(--muted)' }}>Latest version: v{item.latestVersion}</p>
                <p>{item.preview}</p>
                <button className='btn secondary' onClick={() => openTemplate(item.id)} disabled={actionsBlocked}>View Versions</button>
              </div>
            ))}
          </div>
        )}

        {selectedTemplate && (
          <div style={{ marginTop: '14px' }}>
            <h4>{selectedTemplate.title} - Version History</h4>
            <div className='grid'>
              {[...selectedTemplate.versions].reverse().map((v) => (
                <div key={v.version} className='card' style={{ marginBottom: 0 }}>
                  <p><strong>v{v.version}</strong> - {new Date(v.createdAt).toLocaleString()}</p>
                  <button className='btn secondary' onClick={() => applyTemplateVersion(selectedTemplate, v.version)} disabled={actionsBlocked}>Use this version</button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {rateLimitRemaining > 0 && (
        <div className='error'>
          Rate limit reached. Please wait {rateLimitRemaining}s before trying again.
        </div>
      )}
      {copyMessage && <div className='toast'>{copyMessage}</div>}
      {error && <div className='error'>{error}</div>}
      {result && (
        <div className='card'>
          <h3>Analysis Result</h3>
          {result.formattedReport ? (
            <pre className='report'>{result.formattedReport}</pre>
          ) : (
            <pre>{JSON.stringify(result, null, 2)}</pre>
          )}
        </div>
      )}
    </section>
  )
}
