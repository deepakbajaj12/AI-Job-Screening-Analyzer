import { useState } from 'react'
import { analyzeJobSeeker, generateCoverLetter, generateInterviewQuestions, analyzeSkills, generateLinkedInProfile, estimateSalary, tailorResume, generateCareerPath, resumeHealthCheck, generateNetworkingMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Link } from 'react-router-dom'
import DragAndDropUpload from '../components/DragAndDropUpload'

export default function JobSeeker() {
  const { token } = useAuth()
  const [resume, setResume] = useState<File | null>(null)
  const [jobDescription, setJobDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'analyze' | 'coverLetter' | 'questions' | 'skills' | 'linkedin' | 'salary' | 'tailor' | 'career' | 'health' | 'networking'>('analyze')

  // Networking State
  const [netRole, setNetRole] = useState('')
  const [netCompany, setNetCompany] = useState('')
  const [netRecipient, setNetRecipient] = useState('')
  const [netType, setNetType] = useState('linkedin_connect')

  const handleAction = async (action: 'analyze' | 'coverLetter' | 'questions' | 'skills' | 'linkedin' | 'salary' | 'tailor' | 'career' | 'health' | 'networking') => {
    setError(null); setResult(null); setActiveTab(action)
    
    if (action === 'networking') {
      // No resume needed for networking, but we need form inputs
      return
    }

    if (!resume) { setError('Please select a resume PDF'); return }
    setLoading(true)
    try {
      let data;
      if (action === 'analyze') {
        data = await analyzeJobSeeker(token, { resume, jobDescription })
      } else if (action === 'coverLetter') {
        data = await generateCoverLetter(token, { resume, jobDescription })
      } else if (action === 'questions') {
        data = await generateInterviewQuestions(token, { resume, jobDescription })
      } else if (action === 'skills') {
        data = await analyzeSkills(token, { resume, jobDescription })
      } else if (action === 'linkedin') {
        data = await generateLinkedInProfile(token, { resume })
      } else if (action === 'salary') {
        data = await estimateSalary(token, { resume, jobDescription })
      } else if (action === 'tailor') {
        data = await tailorResume(token, { resume, jobDescription })
      } else if (action === 'career') {
        data = await generateCareerPath(token, { resume })
      } else if (action === 'health') {
        data = await resumeHealthCheck(token, { resume })
      }
      setResult(data)
    } catch (err: any) {
      setError(err?.message || 'Action failed')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = () => {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `job-seeker-report-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleNetworkingSubmit = async () => {
    if (!netRole || !netCompany) { setError('Please provide target role and company'); return }
    setLoading(true)
    try {
      const data = await generateNetworkingMessage(token, { targetRole: netRole, company: netCompany, recipientName: netRecipient, messageType: netType })
      setResult(data)
    } catch (err: any) {
      setError(err?.message || 'Networking message generation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <h2>Job Seeker Tools</h2>
      <div className="card">
        <label style={{ marginBottom: '1rem' }}>Resume (PDF)</label>
        <DragAndDropUpload onFileSelect={setResume} />

        <label style={{ marginTop: '1.5rem' }}>Job Description (optional)
          <textarea rows={6} value={jobDescription} onChange={e => setJobDescription(e.target.value)} placeholder="Paste job description text" />
        </label>
        
        <div className="actions" style={{ display: 'flex', gap: '10px', marginTop: '10px', flexWrap: 'wrap' }}>
          <button className="btn" onClick={() => handleAction('analyze')} disabled={loading}>Analyze Match</button>
          <button className="btn" onClick={() => handleAction('coverLetter')} disabled={loading}>Generate Cover Letter</button>
          <button className="btn" onClick={() => handleAction('questions')} disabled={loading}>Interview Questions</button>
          <button className="btn" onClick={() => handleAction('skills')} disabled={loading}>Skill Gap Analysis</button>
          <button className="btn" onClick={() => handleAction('linkedin')} disabled={loading}>LinkedIn Profile</button>
          <button className="btn" onClick={() => handleAction('salary')} disabled={loading}>Salary Estimator</button>
          <button className="btn" onClick={() => handleAction('tailor')} disabled={loading}>Tailor Resume</button>
          <button className="btn" onClick={() => handleAction('career')} disabled={loading}>Career Path</button>
          <button className="btn" onClick={() => handleAction('health')} disabled={loading}>Resume Health Check</button>
          <button className="btn" onClick={() => handleAction('networking')} disabled={loading}>Networking Assistant</button>
          <Link to="/mock-interview" className="btn" style={{ textDecoration: 'none', textAlign: 'center' }}>Mock Interview</Link>
        </div>
      </div>

      {activeTab === 'networking' && (
        <div className="card">
          <h3>Networking Message Generator</h3>
          <div style={{ display: 'flex', gap: '10px', flexDirection: 'column' }}>
            <label>Target Role
              <input type="text" value={netRole} onChange={e => setNetRole(e.target.value)} placeholder="e.g. Product Manager" />
            </label>
            <label>Target Company
              <input type="text" value={netCompany} onChange={e => setNetCompany(e.target.value)} placeholder="e.g. Google" />
            </label>
            <label>Recipient Name (Optional)
              <input type="text" value={netRecipient} onChange={e => setNetRecipient(e.target.value)} placeholder="e.g. Jane Doe" />
            </label>
            <label>Message Type
              <select value={netType} onChange={e => setNetType(e.target.value)}>
                <option value="linkedin_connect">LinkedIn Connection Request</option>
                <option value="cold_email">Cold Email</option>
                <option value="alumni_reachout">Alumni Reachout</option>
              </select>
            </label>
            <button className="btn" onClick={handleNetworkingSubmit} disabled={loading}>Generate Message</button>
          </div>
        </div>
      )}

      {loading && <div className="loading">Processing...</div>}
      {error && <div className="error">{error}</div>}
      
      {result && activeTab !== 'networking' && (
        <div className="card">
          <h3>Result: {activeTab === 'analyze' ? 'Analysis' : activeTab === 'coverLetter' ? 'Cover Letter' : activeTab === 'questions' ? 'Interview Questions' : activeTab === 'linkedin' ? 'LinkedIn Profile' : activeTab === 'salary' ? 'Salary Estimation' : activeTab === 'tailor' ? 'Tailored Resume' : activeTab === 'career' ? 'Career Roadmap' : activeTab === 'health' ? 'Resume Health Check' : 'Skill Gap'}</h3>
          
          <button className="btn" style={{ marginBottom: '15px', backgroundColor: '#28a745' }} onClick={handleDownload}>Download Report</button>
          
          {activeTab === 'analyze' && (
            result.formattedReport ? <pre className="report">{result.formattedReport}</pre> : <pre>{JSON.stringify(result, null, 2)}</pre>
          )}

          {activeTab === 'coverLetter' && (
            <div className="report" style={{ whiteSpace: 'pre-wrap' }}>{typeof result.coverLetter === 'string' ? result.coverLetter : JSON.stringify(result.coverLetter, null, 2)}</div>
          )}

          {activeTab === 'questions' && (
            <div className="report" style={{ whiteSpace: 'pre-wrap' }}>{typeof result.questions === 'string' ? result.questions : JSON.stringify(result.questions, null, 2)}</div>
          )}

          {activeTab === 'linkedin' && (
            <div className="report">
              <h4>Headline</h4>
              <p>{result.headline}</p>
              <h4>About</h4>
              <p>{result.about}</p>
              <h4>Experience Highlights</h4>
              <ul>
                {result.experience_highlights?.map((h: string, i: number) => <li key={i}>{h}</li>)}
              </ul>
            </div>
          )}

          {activeTab === 'salary' && (
            <div className="report">
              <h4>Estimated Salary Range</h4>
              <p style={{ fontSize: '1.2em', fontWeight: 'bold', color: '#28a745' }}>{result.estimated_salary_range}</p>
              <h4>Market Trends</h4>
              <p>{result.market_trends}</p>
              <h4>Negotiation Tips</h4>
              <ul>
                {result.negotiation_tips?.map((tip: string, i: number) => <li key={i}>{tip}</li>)}
              </ul>
            </div>
          )}

          {activeTab === 'tailor' && (
            <div className="report">
              <h4>Rewritten Summary</h4>
              <p style={{ background: '#f0f8ff', padding: '10px', borderRadius: '5px' }}>{result.rewritten_summary}</p>
              <h4>Tailored Bullet Points</h4>
              {result.tailored_bullets?.map((item: any, i: number) => (
                <div key={i} style={{ marginBottom: '15px', borderBottom: '1px solid #eee', paddingBottom: '10px' }}>
                  <p><strong>Original:</strong> <span style={{ color: '#666' }}>{item.original}</span></p>
                  <p><strong>Rewritten:</strong> <span style={{ color: '#007bff' }}>{item.rewritten}</span></p>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'career' && (
            <div className="report">
              <h4>Current Level: {result.current_level}</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', marginTop: '15px' }}>
                {result.career_roadmap?.map((step: any, i: number) => (
                  <div key={i} style={{ borderLeft: '3px solid #007bff', paddingLeft: '15px' }}>
                    <h5 style={{ margin: '0 0 5px 0' }}>{step.role}</h5>
                    <p style={{ margin: 0, color: '#666', fontSize: '0.9em' }}>Timeline: {step.timeline}</p>
                    <p style={{ margin: '5px 0 0 0' }}><strong>Skills Needed:</strong> {step.skills_needed}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'health' && (
            <div className="report">
              <div style={{ display: 'flex', alignItems: 'center', gap: '20px', marginBottom: '20px' }}>
                <div style={{ 
                  width: '80px', height: '80px', borderRadius: '50%', 
                  background: result.score >= 80 ? '#28a745' : result.score >= 60 ? '#ffc107' : '#dc3545',
                  color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '2em', fontWeight: 'bold'
                }}>
                  {result.score}
                </div>
                <div>
                  <h4>Overall Health</h4>
                  <p>{typeof result.summary === 'string' ? result.summary : JSON.stringify(result.summary)}</p>
                </div>
              </div>
              
              <h4>Detailed Checks</h4>
              <div style={{ display: 'grid', gap: '10px' }}>
                {result.checks?.map((check: any, i: number) => (
                  <div key={i} style={{ 
                    padding: '10px', border: '1px solid #eee', borderRadius: '5px',
                    borderLeft: `5px solid ${check.status === 'pass' ? '#28a745' : check.status === 'warning' ? '#ffc107' : '#dc3545'}`
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <strong>{check.category}</strong>
                      <span style={{ 
                        textTransform: 'uppercase', fontSize: '0.8em', fontWeight: 'bold',
                        color: check.status === 'pass' ? '#28a745' : check.status === 'warning' ? '#ffc107' : '#dc3545'
                      }}>{check.status}</span>
                    </div>
                    <p style={{ margin: '5px 0 0 0', fontSize: '0.9em' }}>{check.feedback}</p>
                  </div>
                ))}
              </div>

              <h4>Actionable Improvements</h4>
              <ul>
                {result.improvements?.map((imp: string, i: number) => <li key={i}>{imp}</li>)}
              </ul>
            </div>
          )}

          {activeTab === 'skills' && (
            <div>
              {result.missingSkills ? (
                <div>
                  <h4>Missing Skills</h4>
                  <ul>
                    {result.missingSkills.map((item: any, i: number) => (
                      <li key={i}>
                        <strong>{item.skill}</strong> ({item.importance})
                        <ul>
                          {item.resources.map((res: string, j: number) => <li key={j}>{res}</li>)}
                        </ul>
                      </li>
                    ))}
                  </ul>
                  <h4>Advice</h4>
                  <p>{result.advice}</p>
                </div>
              ) : (
                <pre>{JSON.stringify(result, null, 2)}</pre>
              )}
            </div>
          )}
        </div>
      )}
      {result && activeTab === 'networking' && (
        <div className="card">
          <h3>Generated Message</h3>
          {result.subject && <p><strong>Subject:</strong> {result.subject}</p>}
          <div className="report" style={{ whiteSpace: 'pre-wrap', background: '#f8f9fa', padding: '15px', borderRadius: '5px', border: '1px solid #ddd' }}>
            {result.message}
          </div>
          <button 
            className="btn" 
            style={{ marginTop: '10px', background: '#6c757d' }}
            onClick={() => navigator.clipboard.writeText(result.message)}
          >
            Copy to Clipboard
          </button>
          
          {result.tips && (
            <div style={{ marginTop: '20px', background: '#e9ecef', padding: '10px', borderRadius: '5px' }}>
              <strong>💡 Tips:</strong> {result.tips}
            </div>
          )}
        </div>
      )}
    </section>
  )
}

