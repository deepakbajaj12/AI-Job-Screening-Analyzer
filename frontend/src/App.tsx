import { Routes, Route } from 'react-router-dom'
import React from 'react'
import Home from './pages/Home'
import JobSeeker from './pages/JobSeeker'
import Recruiter from './pages/Recruiter'
import Coaching from './pages/Coaching'
import MockInterview from './pages/MockInterview'
import NavBar from './components/NavBar'
import Footer from './components/Footer'

export default function App() {
  class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }> {
    constructor(props: any) {
      super(props)
      this.state = { hasError: false }
    }
    static getDerivedStateFromError() { return { hasError: true } }
    componentDidCatch(err: any) { console.error('UI error', err) }
    render() {
      if (this.state.hasError) {
        return <div className="card"><h3>Something went wrong</h3><p>Please refresh or try again.</p></div>
      }
      return this.props.children as any
    }
  }
  return (
      <div className="container">
      <NavBar />
      <main>
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/job-seeker" element={<JobSeeker />} />
              <Route path="/recruiter" element={<Recruiter />} />
              <Route path="/coaching" element={<Coaching />} />
              <Route path="/mock-interview" element={<MockInterview />} />
            </Routes>
          </ErrorBoundary>
      </main>
      <Footer />
    </div>
  )
}
