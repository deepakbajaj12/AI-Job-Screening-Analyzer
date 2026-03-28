import { useAuth } from '../context/AuthContext'
import { useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'

const featureCards = [
  {
    title: 'Resume Intelligence',
    description: 'Analyze resumes against job descriptions with lexical and semantic scoring to surface strengths and gaps instantly.'
  },
  {
    title: 'Interview Readiness',
    description: 'Generate role-focused mock interview questions and coaching plans that turn weak points into interview confidence.'
  },
  {
    title: 'Recruiter Toolkit',
    description: 'Create polished job descriptions, review candidate insights, and track analysis history from one unified workspace.'
  }
]

export default function Landing() {
  const { user, signIn, signInWithEmail, authMessage } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'google' | 'email'>('google')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (user) {
      navigate('/')
    }
  }, [user, navigate])

  const handleSignIn = async () => {
    setError(null)
    setLoading(true)
    try {
      await signIn()
    } catch (err: any) {
      setError(err?.message || 'Google sign-in failed')
    } finally {
      setLoading(false)
    }
  }

  const handleEmailLogin = async () => {
    setError(null)
    setLoading(true)
    try {
      await signInWithEmail(email, password)
    } catch (err: any) {
      setError(err?.message || 'Email sign-in failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="landing-shell">
      <div className="landing-atmosphere" aria-hidden="true" />
      <section className="landing-hero">
        <h1>AI Job Screening & Coaching Platform</h1>
        <p className="landing-tagline">Analyze Your Resume With AI</p>
        <p className="landing-copy">
          A professional end-to-end platform for job seekers and recruiters, combining resume diagnostics, interview prep,
          coaching workflows, and analytics in one intelligent dashboard.
        </p>

        <div className="landing-auth-card">
          <div className="landing-auth-tabs" aria-label="Login methods">
            <button className={`btn secondary ${mode === 'google' ? 'active' : ''}`} onClick={() => setMode('google')}>Google</button>
            <button className={`btn secondary ${mode === 'email' ? 'active' : ''}`} onClick={() => setMode('email')}>Email</button>
          </div>

          {mode === 'google' && (
            <button className="btn landing-cta" onClick={handleSignIn} disabled={loading}>
              {loading ? 'Signing in...' : 'Sign in with Google'}
            </button>
          )}

          {mode === 'email' && (
            <div className="landing-auth-form">
              <label>Email
                <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="recruiter@company.com" />
              </label>
              <label>Password
                <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter password" />
              </label>
              <button className="btn landing-cta" onClick={handleEmailLogin} disabled={loading || !email || !password}>
                {loading ? 'Signing in...' : 'Sign in with Email'}
              </button>
            </div>
          )}

          {authMessage && <p className="landing-auth-message">{authMessage}</p>}
          {error && <p className="landing-auth-error">{error}</p>}
        </div>
      </section>

      <section className="landing-features" aria-label="Key Features">
        {featureCards.map((card) => (
          <article className="landing-feature-card" key={card.title}>
            <h3>{card.title}</h3>
            <p>{card.description}</p>
          </article>
        ))}
      </section>
    </div>
  )
}
