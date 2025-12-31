import { useState } from 'react'
import { analyzeJobSeeker, generateCoverLetter, generateInterviewQuestions, analyzeSkills, generateLinkedInProfile, estimateSalary, tailorResume } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Link } from 'react-router-dom'

export default function JobSeeker() {
  const { token } = useAuth()
  const [resume, setResume] = useState<File | null>(null)
  const [jobDescription, setJobDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'analyze' | 'coverLetter' | 'questions' | 'skills' | 'linkedin' | 'salary' | 'tailor'>('analyze')

  const handleAction = async (action: 'analyze' | 'coverLetter' | 'questions' | 'skills' | 'linkedin' | 'salary' | 'tailor') => {
    setError(null); setResult(null); setActiveTab(action)
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
      }
      setResult(data)
    } catch (err: any) {
      setError(err?.message || 'Action failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <h2>Job Seeker Tools</h2>
      <div className="card">
        <label>Resume (PDF)
          <input type="file" accept="application/pdf" onChange={e => setResume(e.target.files?.[0] || null)} />
        </label>
        <label>Job Description (optional)
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
          <Link to="/mock-interview" className="btn" style={{ textDecoration: 'none', textAlign: 'center' }}>Mock Interview</Link>
        </div>
      </div>

      {loading && <div className="loading">Processing...</div>}
      {error && <div className="error">{error}</div>}
      
      {result && (
        <div className="card">
          <h3>Result: {activeTab === 'analyze' ? 'Analysis' : activeTab === 'coverLetter' ? 'Cover Letter' : activeTab === 'questions' ? 'Interview Questions' : activeTab === 'linkedin' ? 'LinkedIn Profile' : activeTab === 'salary' ? 'Salary Estimation' : activeTab === 'tailor' ? 'Tailored Resume' : 'Skill Gap'}</h3>
          
          {activeTab === 'analyze' && (
            result.formattedReport ? <pre className="report">{result.formattedReport}</pre> : <pre>{JSON.stringify(result, null, 2)}</pre>
          )}

          {activeTab === 'coverLetter' && (
            <div className="report" style={{ whiteSpace: 'pre-wrap' }}>{result.coverLetter}</div>
          )}

          {activeTab === 'questions' && (
            <div className="report" style={{ whiteSpace: 'pre-wrap' }}>{result.questions}</div>
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
    </section>
  )
}

