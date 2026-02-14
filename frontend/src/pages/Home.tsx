import { useNavigate } from 'react-router-dom'

export default function Home() {
  const navigate = useNavigate()

  return (
    <div className="home-container">
      <section style={{ textAlign: 'center', padding: '60px 0' }}>
        <h1 style={{ fontSize: '3rem', marginBottom: '1rem', background: 'linear-gradient(to right, #60a5fa, #a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          AI Job Screening & Coaching
        </h1>
        <p style={{ fontSize: '1.2rem', color: 'var(--muted)', maxWidth: '600px', margin: '0 auto 2rem auto' }}>
          Streamline your hiring process or boost your job search with our advanced AI-powered analysis tools.
        </p>
        <div style={{ display: 'flex', gap: '16px', justifyContent: 'center' }}>
          <button className="btn" style={{ fontSize: '1.1rem', padding: '12px 24px' }} onClick={() => navigate('/job-seeker')}>
            For Job Seekers
          </button>
          <button className="btn secondary" style={{ fontSize: '1.1rem', padding: '12px 24px' }} onClick={() => navigate('/recruiter')}>
            For Recruiters
          </button>
        </div>
      </section>

      <div className="grid">
        <div className="card">
          <h3>📄 Resume Analysis</h3>
          <p style={{ color: 'var(--muted)' }}>Upload your resume and get instant feedback compared to job descriptions to improve your match score.</p>
        </div>
        <div className="card">
          <h3>🎯 Mock Interviews</h3>
          <p style={{ color: 'var(--muted)' }}>Practice with AI-generated interview questions tailored to specific job roles and get feedback.</p>
        </div>
        <div className="card">
          <h3>📊 Recruitment Metrics</h3>
          <p style={{ color: 'var(--muted)' }}>For recruiters: Analyze candidate pools and visualize skills distribution effectively.</p>
        </div>
      </div>
    </div>
  )
}

