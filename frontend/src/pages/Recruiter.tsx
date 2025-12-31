import { useState } from 'react'
import { analyzeRecruiter, generateEmail } from '../api/client'
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
            <pre className='report' style={{ whiteSpace: 'pre-wrap' }}>{generatedEmail}</pre>
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
