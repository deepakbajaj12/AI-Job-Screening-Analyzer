import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

it('renders navigation links', () => {
  render(
    <BrowserRouter>
      <App />
    </BrowserRouter>
  )
  expect(screen.getByText(/AI Job Screening/i)).toBeInTheDocument()
  expect(screen.getByText(/Job Seeker/i)).toBeInTheDocument()
  expect(screen.getByText(/Recruiter/i)).toBeInTheDocument()
})
