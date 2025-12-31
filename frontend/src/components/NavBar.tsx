import { Link, useLocation } from 'react-router-dom'
import HealthBadge from './HealthBadge'
import { useAuth } from '../context/AuthContext'

export default function NavBar() {
  const loc = useLocation()
  const { user, signIn, signOut } = useAuth()
  return (
    <header className="navbar">
      <div className="brand"><Link to="/">AI Job Screening</Link></div>
      <nav>
        <Link className={loc.pathname === '/job-seeker' ? 'active' : ''} to="/job-seeker">Job Seeker</Link>
        <Link className={loc.pathname === '/recruiter' ? 'active' : ''} to="/recruiter">Recruiter</Link>
        <Link className={loc.pathname === '/coaching' ? 'active' : ''} to="/coaching">Coaching</Link>
      </nav>
      <div className="right">
        <HealthBadge />
        {user ? (
          <button onClick={signOut} className="btn">Sign out</button>
        ) : (
          <button onClick={signIn} className="btn">Sign in</button>
        )}
      </div>
    </header>
  )
}
