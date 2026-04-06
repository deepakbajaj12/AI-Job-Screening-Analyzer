// RECRUITER PAGE: Candidate shortlist dashboard with decision (shortlist/review/hold), evidence reasoning, risk flags, email assistant, JD generator, Boolean search
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
  downloadAnalysisPdf,
  type RecruiterTemplate,
  type RecruiterTemplateSummary,
} from '../api/client'
import { useAuth } from '../context/AuthContext'

type GeneratedJDObject = {
  title?: string
  overview?: string
  responsibilities?: string[]
  skills_and_experience?: {
    required?: string[]
    preferred?: string[]
  }
  benefits?: string[]
}

type ShortlistEvidence = {
  type: string
  title: string
  detail: string
  confidence?: string
}

type ShortlistRiskFlag = {
  severity: 'high' | 'medium' | 'low'
  title: string
  detail: string
}

type ShortlistDashboard = {
  decision: 'shortlisted' | 'review' | 'hold'
  decisionReason: string
  confidenceScore: number
  skillCoveragePercentage?: number | null
  matchedSkills?: string[]
  missingSkills?: string[]
  evidence?: ShortlistEvidence[]
  riskFlags?: ShortlistRiskFlag[]
  interviewFocusAreas?: string[]
}

function isGeneratedJDObject(value: string | GeneratedJDObject): value is GeneratedJDObject {
  return typeof value !== 'string'
}

export default function Recruiter() {
  const { token } = useAuth()
  const [resume, setResume] = useState<File | null>(null)
  const [jd, setJd] = useState<File | null>(null)
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  
  // Email Assistant State
  const [candidateName, setCandidateName] = useState('')
  const [jobTitle, setJobTitle] = useState('')
  const [emailType, setEmailType] = useState('interview_invite')
  const [generatedEmail, setGeneratedEmail] = useState('')

  // JD Generator State
  const [jdTitle, setJdTitle] = useState('')
  const [jdSkills, setJdSkills] = useState('')
  const [jdExperience, setJdExperience] = useState('')
  const [generatedJD, setGeneratedJD] = useState<string | GeneratedJDObject>('')

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
  const [templatesLoaded, setTemplatesLoaded] = useState(false)
  const [templatesApiUnavailable, setTemplatesApiUnavailable] = useState(false)

  const actionsBlocked = loading || rateLimitRemaining > 0

  const shortlist = (result?.shortlistDashboard || null) as ShortlistDashboard | null

  const generatedJdForSave = useMemo(() => {
    if (!generatedJD) return ''
    return typeof generatedJD === 'string' ? generatedJD : JSON.stringify(generatedJD, null, 2)
  }, [generatedJD])

  useEffect(() => {
    if (!token) {
      setTemplates([])
      setSelectedTemplate(null)
      setTemplatesLoaded(false)
      setTemplatesApiUnavailable(false)
      return
    }
  }, [token])

  useEffect(() => {
    if (!token || !templatesLoaded || templatesApiUnavailable) return
    void refreshTemplates()
  }, [token, templateFilter, templatesLoaded, templatesApiUnavailable])

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
    if (!token || templatesApiUnavailable) return
    try {
      const kind = templateFilter === 'all' ? undefined : templateFilter
      const data = await listRecruiterTemplates(token, kind)
      setTemplates(data.templates || [])
      setTemplatesLoaded(true)
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 404) {
        setTemplatesApiUnavailable(true)
        setTemplates([])
        setSelectedTemplate(null)
        setTemplatesLoaded(false)
        setCopyMessage('Templates are unavailable on this backend deployment')
        return
      }
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
    if (!token) { setError('Please log in to use Recruiter Tools'); return }
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

  const handleDownloadAnalysisPdf = async () => {
    if (!token) { setError('Please log in to download PDF'); return }
    if (!result) return
    setDownloadingPdf(true)
    try {
      await downloadAnalysisPdf(token, result, 'recruiter', candidateName || 'Candidate')
    } catch (err: any) {
      setError(err?.message || 'Failed to download PDF')
    } finally {
      setDownloadingPdf(false)
    }
  }

  const handleGenerateEmail = async () => {
    if (!token) { setError('Please log in to generate emails'); return }
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
    if (!token) { setError('Please log in to generate job descriptions'); return }
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
    if (!token) { setError('Please log in to generate searches'); return }
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
    if (!token) { setError('Please log in to save templates'); return }
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
    if (!token) { setError('Please log in to save templates'); return }
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
    if (templatesApiUnavailable) return
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
        <div className='recruiter-stack'>
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
          <div className='recruiter-section-gap'>
            <h4>Boolean String:</h4>
            <div className='recruiter-mono-box'>
              {typeof generatedSearch.boolean_string === 'string' 
                ? generatedSearch.boolean_string 
                : JSON.stringify(generatedSearch.boolean_string || generatedSearch.raw_response || generatedSearch)
              }
            </div>
            <p className='recruiter-strategy-text'>
              <strong>Strategy:</strong> {typeof generatedSearch.explanation === 'string' 
                ? generatedSearch.explanation 
                : (JSON.stringify(generatedSearch.explanation) || '')}
            </p>
          </div>
        )}
      </div>

      <div className='card'>
        <h3>Email Assistant</h3>
        <div className='recruiter-stack'>
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
          <div className='recruiter-section-gap'>
            <h4>Generated Email:</h4>
            <pre className='report recruiter-pre-wrap'>
              {typeof generatedEmail === 'string' ? generatedEmail : JSON.stringify(generatedEmail, null, 2)}
            </pre>
            <div className='recruiter-actions-row'>
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
        <div className='recruiter-stack'>
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
          <div className='recruiter-section-gap'>
            <h4>Generated Job Description:</h4>
            {typeof generatedJD === 'string' ? (
              <pre className='report recruiter-pre-wrap'>{generatedJD}</pre>
            ) : isGeneratedJDObject(generatedJD) ? (
              <div className='report recruiter-jd-card'>
                <h2 className='recruiter-jd-title'>{generatedJD.title}</h2>
                
                <section className='recruiter-jd-section'>
                  <h3 className='recruiter-jd-subtitle'>Overview</h3>
                  <p className='recruiter-muted-text'>{generatedJD.overview}</p>
                </section>

                <section className='recruiter-jd-section'>
                  <h3 className='recruiter-jd-subtitle'>Key Responsibilities</h3>
                  <ul className='recruiter-list'>
                    {generatedJD.responsibilities?.map((item: string, i: number) => (
                      <li key={i} className='recruiter-list-item'>{item}</li>
                    ))}
                  </ul>
                </section>

                <section className='recruiter-jd-section'>
                  <h3 className='recruiter-jd-subtitle'>Required Skills & Experience</h3>
                  <ul className='recruiter-list'>
                    {generatedJD.skills_and_experience?.required?.map((item: string, i: number) => (
                      <li key={i} className='recruiter-list-item'>{item}</li>
                    ))}
                  </ul>
                </section>

                {generatedJD.skills_and_experience?.preferred && generatedJD.skills_and_experience.preferred.length > 0 && (
                  <section className='recruiter-jd-section'>
                    <h3 className='recruiter-jd-subtitle'>Preferred Qualifications</h3>
                    <ul className='recruiter-list'>
                      {generatedJD.skills_and_experience.preferred.map((item: string, i: number) => (
                        <li key={i} className='recruiter-list-item'>{item}</li>
                      ))}
                    </ul>
                  </section>
                )}

                {generatedJD.benefits && generatedJD.benefits.length > 0 && (
                  <section className='recruiter-jd-section'>
                    <h3 className='recruiter-jd-subtitle'>What We Offer</h3>
                    <ul className='recruiter-list'>
                      {generatedJD.benefits.map((item: string, i: number) => (
                        <li key={i} className='recruiter-list-item'>{item}</li>
                      ))}
                    </ul>
                  </section>
                )}
              </div>
            ) : null
            }
            <div className='recruiter-actions-row recruiter-actions-top'>
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
        {templatesApiUnavailable ? (
          <p className='recruiter-muted-text'>Templates are not available on your current backend deployment.</p>
        ) : (
          <div className='recruiter-toolbar'>
            <label htmlFor='template-filter' className='recruiter-label-inline'>Filter</label>
            <select id='template-filter' aria-label='Template Filter' value={templateFilter} onChange={e => setTemplateFilter(e.target.value as 'all' | 'email' | 'job_description')}>
              <option value='all'>All</option>
              <option value='email'>Email</option>
              <option value='job_description'>Job Description</option>
            </select>
            <button className='btn secondary' onClick={refreshTemplates} disabled={actionsBlocked}>{templatesLoaded ? 'Refresh' : 'Load Templates'}</button>
          </div>
        )}

        {!templatesApiUnavailable && templatesLoaded && templates.length === 0 ? (
          <p className='recruiter-muted-text'>No templates saved yet.</p>
        ) : !templatesApiUnavailable && templates.length > 0 ? (
          <div className='grid'>
            {templates.map((item) => (
              <div key={item.id} className='card recruiter-card-flat'>
                <h4>{item.title}</h4>
                <p className='recruiter-muted-text'>Type: {item.kind === 'email' ? 'Email' : 'Job Description'}</p>
                <p className='recruiter-muted-text'>Latest version: v{item.latestVersion}</p>
                <p>{item.preview}</p>
                <button className='btn secondary' onClick={() => openTemplate(item.id)} disabled={actionsBlocked}>View Versions</button>
              </div>
            ))}
          </div>
        ) : null}

        {!templatesApiUnavailable && selectedTemplate && (
          <div className='recruiter-selected-template'>
            <h4>{selectedTemplate.title} - Version History</h4>
            <div className='grid'>
              {[...selectedTemplate.versions].reverse().map((v) => (
                <div key={v.version} className='card recruiter-card-flat'>
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
          <div style={{ marginBottom: '15px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <button className="btn" style={{ backgroundColor: '#007bff' }} onClick={handleDownloadAnalysisPdf} disabled={downloadingPdf}>📄 Download PDF Report</button>
          </div>
          {shortlist && (
            <div className='recruiter-shortlist-dashboard'>
              <div className='recruiter-shortlist-header'>
                <div>
                  <h4>Shortlist Decision: <span className={`recruiter-decision-pill ${shortlist.decision}`}>{shortlist.decision.toUpperCase()}</span></h4>
                  <p className='recruiter-muted-text'>{shortlist.decisionReason}</p>
                </div>
                <div className='recruiter-score-box'>
                  <strong>{shortlist.confidenceScore}%</strong>
                  <span>Confidence</span>
                </div>
              </div>

              <div className='recruiter-shortlist-grid'>
                <div className='recruiter-shortlist-panel'>
                  <h5>Why Shortlisted</h5>
                  {(shortlist.evidence || []).length === 0 ? (
                    <p className='recruiter-muted-text'>No shortlist evidence available.</p>
                  ) : (
                    <ul className='recruiter-list'>
                      {(shortlist.evidence || []).map((item, idx) => (
                        <li key={`${item.type}-${idx}`} className='recruiter-list-item'>
                          <strong>{item.title}:</strong> {item.detail}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className='recruiter-shortlist-panel'>
                  <h5>Risk Flags</h5>
                  {(shortlist.riskFlags || []).length === 0 ? (
                    <p className='recruiter-muted-text'>No active risk flags detected.</p>
                  ) : (
                    <ul className='recruiter-list'>
                      {(shortlist.riskFlags || []).map((risk, idx) => (
                        <li key={`${risk.title}-${idx}`} className='recruiter-list-item'>
                          <span className={`recruiter-risk-chip ${risk.severity}`}>{risk.severity.toUpperCase()}</span>
                          <strong>{risk.title}:</strong> {risk.detail}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              <div className='chip-row'>
                {typeof shortlist.skillCoveragePercentage === 'number' && (
                  <span className='chip'>Skill coverage: {shortlist.skillCoveragePercentage}%</span>
                )}
                <span className='chip'>Matched: {(shortlist.matchedSkills || []).length}</span>
                <span className='chip'>Missing: {(shortlist.missingSkills || []).length}</span>
              </div>
            </div>
          )}
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
