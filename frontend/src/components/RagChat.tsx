// RAG CHAT COMPONENT: Grounded resume Q&A powered by LangChain + FAISS + HuggingFace
import { useState, useRef, useEffect } from 'react'
import { ragAnalyze, ragClear, ragStatus } from '../api/client'
import { useAuth } from '../context/AuthContext'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sourceChunks?: Array<{ content: string; source: string; relevance_score: number }>
  grounded?: boolean
  timestamp: Date
}

interface RagChatProps {
  chunksIndexed: number
  jobDescription?: string
}

const QUICK_QUESTIONS = [
  'What are my top technical skills?',
  'What projects have I built?',
  'Do I have leadership experience?',
  'What is my educational background?',
  'Am I a good fit for this role?',
]

export default function RagChat({ chunksIndexed, jobDescription = '' }: RagChatProps) {
  const { token } = useAuth()
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: chunksIndexed > 0
        ? `✅ Your resume is indexed (${chunksIndexed} chunks). Ask me anything about your resume — I'll answer using only what's actually in your document!`
        : '⚠️ No resume indexed yet. Upload a resume and click "Analyze Match" first, then come back here to chat with your resume!',
      timestamp: new Date()
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set())
  const [ragReady, setRagReady] = useState(chunksIndexed > 0)
  const [totalChunks, setTotalChunks] = useState(chunksIndexed)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    // Poll RAG status on mount
    ragStatus(token).then(s => {
      setRagReady(s.indexed)
      setTotalChunks(s.chunks_indexed || 0)
    }).catch(() => {})
  }, [token])

  const sendMessage = async (question: string) => {
    if (!question.trim() || loading) return

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const result = await ragAnalyze(token, {
        question,
        job_description: jobDescription
      })

      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: result.answer || result.error || 'No answer generated.',
        sourceChunks: result.source_chunks || [],
        grounded: result.grounded,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err: any) {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `❌ Error: ${err?.message || 'Failed to get answer. Please try again.'}`,
        timestamp: new Date()
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleClear = async () => {
    try {
      await ragClear(token)
      setMessages([{
        id: 'cleared',
        role: 'assistant',
        content: '🗑️ Vector store cleared. Upload a new resume and re-analyze to start a fresh session.',
        timestamp: new Date()
      }])
      setRagReady(false)
      setTotalChunks(0)
    } catch (err) {
      console.error('Clear failed:', err)
    }
  }

  const toggleSources = (msgId: string) => {
    setExpandedSources(prev => {
      const next = new Set(prev)
      next.has(msgId) ? next.delete(msgId) : next.add(msgId)
      return next
    })
  }

  return (
    <div className="rag-chat-container">
      {/* Status Bar */}
      <div className={`rag-status-bar ${ragReady ? 'rag-status-ready' : 'rag-status-empty'}`}>
        <div className="rag-status-left">
          <span className="rag-status-dot" />
          {ragReady
            ? <span>📄 Resume indexed — <strong>{totalChunks} chunks</strong> in FAISS vector store</span>
            : <span>⚠️ No document indexed — Upload &amp; analyze a resume first</span>
          }
        </div>
        <div className="rag-status-right">
          <span className="rag-model-badge">🧠 all-MiniLM-L6-v2 + FAISS</span>
          {ragReady && (
            <button className="rag-clear-btn" onClick={handleClear} title="Clear vector store">
              🗑️ Clear
            </button>
          )}
        </div>
      </div>

      {/* Quick Question Chips */}
      {ragReady && (
        <div className="rag-quick-questions">
          <span className="rag-quick-label">Quick ask:</span>
          {QUICK_QUESTIONS.map(q => (
            <button
              key={q}
              className="rag-quick-chip"
              onClick={() => sendMessage(q)}
              disabled={loading}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="rag-messages">
        {messages.map(msg => (
          <div key={msg.id} className={`rag-message rag-message-${msg.role}`}>
            <div className="rag-bubble">
              <div className="rag-bubble-header">
                <span className="rag-role-icon">{msg.role === 'user' ? '🧑' : '🤖'}</span>
                <span className="rag-role-label">{msg.role === 'user' ? 'You' : 'RAG Assistant'}</span>
                {msg.grounded && (
                  <span className="rag-grounded-badge" title="Answer grounded in your resume context">
                    ✅ Grounded
                  </span>
                )}
                <span className="rag-timestamp">
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>

              <div className="rag-bubble-content">{msg.content}</div>

              {/* Source Citations */}
              {msg.sourceChunks && msg.sourceChunks.length > 0 && (
                <div className="rag-sources">
                  <button
                    className="rag-sources-toggle"
                    onClick={() => toggleSources(msg.id)}
                  >
                    📎 {expandedSources.has(msg.id) ? 'Hide' : 'View'} Sources ({msg.sourceChunks.length} chunks)
                  </button>
                  {expandedSources.has(msg.id) && (
                    <div className="rag-sources-list">
                      {msg.sourceChunks.map((chunk, idx) => (
                        <div key={idx} className="rag-source-chunk">
                          <div className="rag-source-meta">
                            <span className="rag-source-label">📄 {chunk.source}</span>
                            <span className="rag-source-score">
                              {Math.round(chunk.relevance_score * 100)}% match
                            </span>
                          </div>
                          <p className="rag-source-content">{chunk.content}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {loading && (
          <div className="rag-message rag-message-assistant">
            <div className="rag-bubble">
              <div className="rag-typing">
                <span />
                <span />
                <span />
              </div>
              <span className="rag-typing-label">Retrieving from vector store...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="rag-input-area">
        <input
          className="rag-input"
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
          placeholder={ragReady ? 'Ask anything about your resume...' : 'Upload a resume first to enable RAG chat'}
          disabled={!ragReady || loading}
        />
        <button
          className="rag-send-btn"
          onClick={() => sendMessage(input)}
          disabled={!ragReady || loading || !input.trim()}
        >
          {loading ? '⏳' : '➤'}
        </button>
      </div>
      <p className="rag-disclaimer">
        🛡️ Answers are grounded strictly in your resume — no hallucinations. Powered by LangChain + FAISS + HuggingFace.
      </p>
    </div>
  )
}
