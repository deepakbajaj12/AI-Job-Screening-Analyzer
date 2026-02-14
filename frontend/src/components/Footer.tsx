import React from 'react'

export default function Footer() {
  return (
    <footer className="footer" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
      <div>
        © {new Date().getFullYear()} AI Job Screening &bull; v1.0.0
      </div>
      <div style={{ display: 'flex', gap: '1rem' }}>
        <a href="#" className="link">Privacy</a>
        <a href="#" className="link">Terms</a>
        <span title="System Status: Operational">Status: 🟢</span>
      </div>
    </footer>
  )
}

