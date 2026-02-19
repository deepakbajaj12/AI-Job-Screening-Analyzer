import { useState } from 'react'
import { analyzeRecruiter, generateEmail, generateJobDescription, generateBooleanSearch } from '../api/client'
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

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null); setResult(null)
    if (!resume || !jd || !email) { setError('Provide resume, JD PDF and recruiter email'); return }
    setLoading(true)
    try {
      const data = await analyzeRecruiter(token, { resume, jobDescription: jd, recruiterEmail: email })
      setResult(data)
    } catch (err: any) {
      setError(err?.message || 'Analyze failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateEmail = async () => {
    setLoading(true)
    try {
      const data = await generateEmail(token, { type: emailType, candidateName, jobTitle })
      setGeneratedEmail(data.email)
    } catch (err: any) {
      setError(err?.message || 'Email generation failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateJD = async () => {
    setLoading(true)
    try {
      const data = await generateJobDescription(token, { title: jdTitle, skills: jdSkills, experience: jdExperience })
      setGeneratedJD(data.job_description)
    } catch (err: any) {
      setError(err?.message || 'JD generation failed')
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
      setError(err?.message || 'Search generation failed')
    } finally {
      setLoading(false)
    }
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
          <button className='btn' disabled={loading}>{loading ? 'Analyzing' : 'Analyze'}</button>
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
          <button className='btn' onClick={handleGenerateSearch} disabled={loading}>Generate Boolean String</button>
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
          <button className='btn' onClick={handleGenerateEmail} disabled={loading}>Generate Email</button>
        </div>
        {generatedEmail && (
          <div style={{ marginTop: '10px' }}>
            <h4>Generated Email:</h4>
            <pre className='report' style={{ whiteSpace: 'pre-wrap' }}>
              {typeof generatedEmail === 'string' ? generatedEmail : JSON.stringify(generatedEmail, null, 2)}
            </pre>
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
          <button className='btn' onClick={handleGenerateJD} disabled={loading}>Generate JD</button>
        </div>
        {generatedJD && (
          <div style={{ marginTop: '10px' }}>
            <h4>Generated Job Description:</h4>
            <pre className='report' style={{ whiteSpace: 'pre-wrap' }}>{generatedJD}</pre>
          </div>
        )}
      </div>

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
