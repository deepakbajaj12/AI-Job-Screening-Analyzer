import { useAuth } from '../context/AuthContext'
import { useNavigate } from 'react-router-dom'

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
  const { signIn } = useAuth()
  const navigate = useNavigate()

  const handleSignIn = async () => {
    await signIn()
    navigate('/')
  }

  return (
    <div className="landing-shell">
      <div className="landing-atmosphere" aria-hidden="true" />
      <section className="landing-hero">
        <p className="landing-kicker">Final Year Major Project</p>
        <h1>AI Job Screening & Coaching Platform</h1>
        <p className="landing-tagline">Analyze Your Resume With AI</p>
        <p className="landing-copy">
          A professional end-to-end platform for job seekers and recruiters, combining resume diagnostics, interview prep,
          coaching workflows, and analytics in one intelligent dashboard.
        </p>
        <button className="btn landing-cta" onClick={handleSignIn}>Sign in with Google</button>
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
