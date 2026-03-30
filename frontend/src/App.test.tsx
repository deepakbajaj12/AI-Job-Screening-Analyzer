import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

type MockUser = { uid: string; email?: string | null } | null
let mockUser: MockUser = null

vi.mock('./context/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    token: mockUser ? 'test-token' : null,
    authMessage: null,
    signIn: vi.fn(),
    signInWithEmail: vi.fn(),
    sendPhoneOtp: vi.fn(),
    verifyPhoneOtp: vi.fn(),
    signOut: vi.fn()
  })
}))

describe('App', () => {
  beforeEach(() => {
    mockUser = null
  })

  it('renders landing screen when user is not authenticated', () => {
    mockUser = null
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )
    expect(screen.getByRole('heading', { name: /AI Job Screening & Coaching Platform/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Sign in with Google/i })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /Key Features/i })).toBeInTheDocument()
  })

  it('renders signed-in dashboard navigation when user is authenticated', () => {
    mockUser = { uid: 'user-1', email: 'user@example.com' }
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )

    expect(screen.getByRole('link', { name: /AI Job Screening/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Job Seeker/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Recruiter/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Sign out/i })).toBeInTheDocument()
  })
})
