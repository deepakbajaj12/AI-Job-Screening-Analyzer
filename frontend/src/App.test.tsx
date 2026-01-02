import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

describe('App', () => {
  it('renders navigation links', () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )
    expect(screen.getByRole('link', { name: /AI Job Screening/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Job Seeker/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Recruiter/i })).toBeInTheDocument()
  })
})
