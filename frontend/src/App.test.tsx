import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

vi.mock('./context/AuthContext', () => ({
  useAuth: () => ({ user: null })
}))

describe('App', () => {
  it('renders landing screen when user is not authenticated', () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )
    expect(screen.getByRole('heading', { name: /AI Job Screening & Coaching Platform/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Sign in with Google/i })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /Key Features/i })).toBeInTheDocument()
  })
})
