import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '../contexts/AuthContext'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

export default function ChatAssistant({ policyProfile, costBreakdown }) {
  const { session } = useAuth()
  const [messages, setMessages] = useState([
    { role: 'ai', content: "Hi! I'm the PolicyCrab AI assistant. I can help you understand your insurance coverage, claims, denials, or appeal rights under US law. How can I help you today?" }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    try {
      const history = messages.filter(m => m.role === 'user').map(m => m.content)
      const res = await fetch('/api/chat/message', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session?.access_token}`
        },
        body: JSON.stringify({ message: userMsg, history, policy_profile: policyProfile, cost_breakdown: costBreakdown }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'ai', content: data.error ? `Error: ${data.error}` : data.response }])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', content: `Network error: ${err.message}` }])
    } finally { setLoading(false) }
  }

  const quickQuestions = [
    "What are my rights under the No Surprises Act?",
    "How long do I have to file an ERISA appeal?",
    "What's the difference between HMO and PPO?",
    "What does 'medical necessity' mean?",
    "Can an ER balance bill me if they're out-of-network?",
  ]

  return (
    <section className="section-white" style={{ paddingTop: '3rem', paddingBottom: '2rem' }}>
      <div className="main">
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }} style={{ marginBottom: '1.5rem' }}>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label">
            <span className="line" /> RAG-Powered Chat
          </motion.p>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.55 }} className="section-title">
            AI <span className="gradient-text">Assistant</span>
          </motion.h1>
        </motion.div>

        <div className="grid-2" style={{ gap: '1.5rem', alignItems: 'start' }}>
          {/* ── Left Panel ─────────────────── */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}
            style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

            {/* Context */}
            <div className="card card-zinc" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                <div className="feature-icon purple">🧠</div>
                <div>
                  <h3 style={{ fontWeight: 700, fontSize: '0.9375rem', color: '#09090b' }}>Active Context</h3>
                  <p style={{ fontSize: '0.75rem', color: '#a1a1aa' }}>Injected into the LLM prompt</p>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.8125rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#71717a', fontWeight: 500 }}>Policy Profile</span>
                  {policyProfile ? <span className="badge badge-success">Loaded</span> : <span className="badge badge-zinc">None</span>}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#71717a', fontWeight: 500 }}>Recent Claim</span>
                  {costBreakdown ? <span className="badge badge-success">Loaded</span> : <span className="badge badge-zinc">None</span>}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#71717a', fontWeight: 500 }}>RAG Search</span>
                  <span className="badge badge-info">Active · 46 chunks</span>
                </div>
              </div>
            </div>

            {/* Suggested Questions */}
            <div className="card" style={{ padding: '1.5rem' }}>
              <h3 style={{ fontWeight: 700, fontSize: '0.9375rem', color: '#09090b', marginBottom: '1rem' }}>Suggested Questions</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {quickQuestions.map((q, i) => (
                  <button key={i} className="btn btn-ghost"
                    style={{ textAlign: 'left', whiteSpace: 'normal', lineHeight: 1.4, height: 'auto', justifyContent: 'flex-start' }}
                    onClick={() => setInput(q)}>
                    <span style={{ color: '#dc2626', fontWeight: 700 }}>→</span> {q}
                  </button>
                ))}
              </div>
            </div>
          </motion.div>

          {/* ── Chat Panel ─────────────────── */}
          <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.55, delay: 0.15 }}>
            <div className="chat-panel" style={{ height: 'calc(100vh - 280px)' }}>
              <div className="chat-messages">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`chat-bubble ${msg.role}`}>
                    {msg.role === 'ai' ? (
                      <div dangerouslySetInnerHTML={{ __html: msg.content.replace(/\n/g, '<br/>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
                    ) : msg.content}
                  </div>
                ))}
                {loading && (
                  <div className="chat-bubble ai" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', width: 'fit-content' }}>
                    <span className="spinner" style={{ width: '14px', height: '14px' }} />
                    <em style={{ color: '#a1a1aa', fontSize: '0.875rem' }}>Thinking...</em>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <form onSubmit={handleSend} className="chat-input-bar">
                <input type="text" className="input" value={input} onChange={e => setInput(e.target.value)}
                  placeholder="Ask about regulations, appeals, or your policy..." disabled={loading} />
                <button type="submit" className="btn btn-red" disabled={!input.trim() || loading}
                  style={{ borderRadius: '9999px', padding: '0 1.5rem', flexShrink: 0 }}>
                  Send
                </button>
              </form>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
