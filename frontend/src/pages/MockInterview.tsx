import { useState } from 'react'
import { mockInterview, analyzeMockInterview } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function MockInterview() {
  const { token } = useAuth()
  const [history, setHistory] = useState<any[]>([])
  const [message, setMessage] = useState('')
  const [jobContext, setJobContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<any>(null)

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!message.trim()) return
    
    const newHistory = [...history, { sender: 'user', text: message }]
    setHistory(newHistory)
    setMessage('')
    setLoading(true)
    
    try {
      const data = await mockInterview(token, { history: newHistory, message, jobContext })
      setHistory([...newHistory, { sender: 'ai', text: data.response }])
    } catch (err: any) {
      setError(err?.message || 'Failed to get response')
    } finally {
      setLoading(false)
    }
  }

  const handleEndInterview = async () => {
    if (history.length === 0) return
    setLoading(true)
    try {
      const data = await analyzeMockInterview(token, { history, jobContext })
      setFeedback(data)
    } catch (err: any) {
      setError(err?.message || 'Failed to analyze interview')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section>
      <h2>AI Mock Interviewer</h2>
      <div className="card">
        <label>Job Context (Role/Company)
          <input 
            type="text" 
            value={jobContext} 
            onChange={e => setJobContext(e.target.value)} 
            placeholder="e.g. Senior React Developer at TechCorp"
          />
        </label>
      </div>

      <div className="card" style={{ height: '400px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {history.length === 0 && <p style={{ color: '#666', textAlign: 'center' }}>Start the interview by saying hello!</p>}
        {history.map((msg, i) => (
          <div key={i} style={{ 
            alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
            background: msg.sender === 'user' ? '#007bff' : '#f0f0f0',
            color: msg.sender === 'user' ? 'white' : 'black',
            padding: '8px 12px',
            borderRadius: '12px',
            maxWidth: '70%'
          }}>
            <strong>{msg.sender === 'user' ? 'You' : 'Interviewer'}:</strong> {msg.text}
          </div>
        ))}
        {loading && <div style={{ alignSelf: 'flex-start', color: '#666' }}>Interviewer is typing...</div>}
      </div>

      <form onSubmit={handleSend} style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
        <input 
          type="text" 
          value={message} 
          onChange={e => setMessage(e.target.value)} 
          placeholder="Type your answer..." 
          style={{ flex: 1 }}
          disabled={loading}
        />
        <button className="btn" disabled={loading}>Send</button>
        <button type="button" className="btn" onClick={handleEndInterview} disabled={loading || history.length === 0} style={{ background: '#28a745' }}>End & Get Feedback</button>
      </form>
      {error && <div className="error">{error}</div>}

      {feedback && (
        <div className="card" style={{ marginTop: '20px' }}>
          <h3>Interview Feedback</h3>
          <div className="report">
            <h4>Score: {feedback.score}/100</h4>
            <p>{feedback.feedback}</p>
            <h4>Strengths</h4>
            <ul>
              {feedback.strengths?.map((s: string, i: number) => <li key={i}>{s}</li>)}
            </ul>
            <h4>Improvements</h4>
            <ul>
              {feedback.improvements?.map((s: string, i: number) => <li key={i}>{s}</li>)}
            </ul>
          </div>
        </div>
      )}
    </section>
  )
}
