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
  const [isListening, setIsListening] = useState(false)

  const startListening = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Speech recognition is not supported in this browser. Try Chrome.')
      return
    }
    // @ts-expect-error - Vendor-prefixed SpeechRecognition exists in some browsers.
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = 'en-US'

    recognition.onstart = () => setIsListening(true)
    recognition.onend = () => setIsListening(false)
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript
      setMessage((prev) => prev + (prev ? ' ' : '') + transcript)
    }
    recognition.start()
  }

  const speak = (text: string) => {
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    window.speechSynthesis.speak(utterance)
  }

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

      <div className="card interview-chat-log">
        {history.length === 0 && <p className="interview-empty">Start the interview by saying hello!</p>}
        {history.map((msg, i) => (
          <div key={i} className={`interview-msg ${msg.sender === 'user' ? 'interview-msg-user' : 'interview-msg-ai'}`}>
            <div><strong>{msg.sender === 'user' ? 'You' : 'Interviewer'}:</strong> {msg.text}</div>
            {msg.sender === 'ai' && (
              <button 
                onClick={() => speak(msg.text)}
                className="interview-speak-btn"
                title="Read aloud"
              >
                🔊
              </button>
            )}
          </div>
        ))}
        {loading && <div className="interview-typing">Interviewer is typing...</div>}
      </div>

      <form onSubmit={handleSend} className="interview-form">
        <button 
          type="button" 
          onClick={startListening} 
          disabled={loading || isListening}
          className={`btn interview-mic-btn ${isListening ? 'listening' : ''}`}
          title="Speak answer"
        >
          {isListening ? '🛑' : '🎤'}
        </button>
        <input 
          type="text" 
          value={message} 
          onChange={e => setMessage(e.target.value)} 
          placeholder="Type your answer..." 
          className="interview-input"
          disabled={loading}
        />
        <button className="btn" disabled={loading}>Send</button>
        <button type="button" className="btn interview-end-btn" onClick={handleEndInterview} disabled={loading || history.length === 0}>End & Get Feedback</button>
      </form>
      {error && <div className="error">{error}</div>}

      {feedback && (
        <div className="card interview-feedback-card">
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
