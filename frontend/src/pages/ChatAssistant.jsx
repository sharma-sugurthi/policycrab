import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { apiFetch, readApiResponse } from '../lib/api'
import { IconCpu, IconActivity, IconSearch, IconBriefcase, IconAlertTriangle, IconZap } from '../components/Icons'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

function renderMessageContent(content) {
  const lines = content.split('\n')
  return lines.map((line, lineIndex) => {
    const parts = line.split(/(\*\*.*?\*\*)/g)
    return (
      <span key={lineIndex}>
        {parts.map((part, partIndex) => {
          if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={partIndex} style={{ fontWeight: 800 }}>{part.slice(2, -2)}</strong>
          }
          return <span key={partIndex}>{part}</span>
        })}
        {lineIndex < lines.length - 1 ? <br /> : null}
      </span>
    )
  })
}


export default function ChatAssistant({ policyProfile, costBreakdown }) {
  const [messages, setMessages] = useState([
    { role: 'ai', content: "Hi! I'm the PolicyCrab AI assistant. I can help you understand your insurance coverage, claims, denials, or appeal rights under US law. How can I help you today?" }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  useEffect(() => {
    let cancelled = false

    async function loadChatSession() {
      try {
        const res = await apiFetch('/chat/session')
        if (!res.ok) return
        const data = await readApiResponse(res)
        if (!cancelled && data.messages?.length > 0) setMessages(data.messages)
      } catch (err) {
        console.error('Failed to load chat session', err)
      }
    }

    loadChatSession()
    return () => { cancelled = true }
  }, [])

  const handleClearChat = async () => {
    try {
      await apiFetch('/chat/session', { method: 'DELETE' })
    } catch (err) {
      console.error('Failed to clear chat session', err)
    }
    setMessages([
      { role: 'ai', content: "Hi! I'm the PolicyCrab AI assistant. I can help you understand your insurance coverage, claims, denials, or appeal rights under US law. How can I help you today?" }
    ])
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    try {
      const res = await apiFetch('/chat/message', {
        method: 'POST',
        body: JSON.stringify({ message: userMsg, policy_profile: policyProfile, cost_breakdown: costBreakdown }),
      })
      const data = await readApiResponse(res)
      if (!data || typeof data === 'string') {
        console.error('Backend non-JSON response:', data || '')
        setMessages(prev => [...prev, { role: 'ai', content: 'The assistant is temporarily unavailable. Please try again in a few seconds.' }])
        return
      }
      if (data.messages?.length) setMessages(data.messages)
      else setMessages(prev => [...prev, { role: 'ai', content: data.error ? `Error: ${data.error}` : data.response }])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', content: 'Connection error — please check your internet and try again.' }])
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
            <span className="line" /> Coverage Help
          </motion.p>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
            <motion.h1 variants={fadeUp} transition={{ duration: 0.55 }} className="section-title">
              AI <span className="gradient-text">Assistant</span>
            </motion.h1>
            <button type="button" className="btn btn-outline" style={{ fontSize: '0.8125rem', padding: '0.5rem 1rem' }} onClick={handleClearChat}>Clear Chat</button>
          </div>
        </motion.div>

        <div className="grid-2" style={{ gap: '1.5rem', alignItems: 'start' }}>
          {/* ── Left Panel ─────────────────── */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}
            style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

            {/* Context */}
            <div className="card" style={{ padding: '1.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-secondary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                <div className="feature-icon" style={{ background: 'var(--accent-subtle)', color: 'var(--accent)' }}><IconCpu size={20} /></div>
                <div>
                  <h3 style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--text-primary)' }}>Conversation context</h3>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>Used to personalize your answer</p>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.875rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0', borderBottom: '1px solid var(--border-primary)' }}>
                  <span style={{ color: 'var(--text-secondary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}><IconBriefcase size={16} style={{ color: 'var(--text-tertiary)' }} /> Policy Profile</span>
                  {policyProfile ? <span className="badge badge-success">Loaded</span> : <span className="badge badge-zinc">None</span>}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0', borderBottom: '1px solid var(--border-primary)' }}>
                  <span style={{ color: 'var(--text-secondary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}><IconActivity size={16} style={{ color: 'var(--text-tertiary)' }} /> Recent Claim</span>
                  {costBreakdown ? <span className="badge badge-success">Loaded</span> : <span className="badge badge-zinc">None</span>}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0' }}>
                  <span style={{ color: 'var(--text-secondary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}><IconSearch size={16} style={{ color: 'var(--text-tertiary)' }} /> Reference search</span>
                  <span className="badge badge-info">Active</span>
                </div>
              </div>
            </div>

            {/* Suggested Questions */}
            <div className="card" style={{ padding: '1.5rem', background: 'var(--bg-card)', border: '1px solid var(--border-secondary)', boxShadow: 'var(--shadow-sm)' }}>
              <h3 style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '1.25rem' }}>Suggested Questions</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                {quickQuestions.map((q, i) => (
                  <button key={i} className="btn btn-outline"
                    style={{ textAlign: 'left', whiteSpace: 'normal', lineHeight: 1.5, height: 'auto', justifyContent: 'flex-start', padding: '0.875rem 1rem', fontSize: '0.875rem', fontWeight: 500, color: 'var(--text-secondary)' }}
                    onClick={() => setInput(q)}>
                    <span style={{ color: 'var(--accent)', fontWeight: 800, marginRight: '0.5rem' }}>→</span> {q}
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
                    {msg.role === 'ai' ? renderMessageContent(msg.content) : msg.content}
                  </div>
                ))}
                {loading && (
                  <div className="chat-bubble ai" style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', width: 'fit-content' }}>
                    <span className="spinner" style={{ width: '16px', height: '16px', borderWidth: '2px' }} />
                    <em style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem', fontWeight: 500 }}>Thinking...</em>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <form onSubmit={handleSend} className="chat-input-bar">
                <input type="text" className="input" value={input} onChange={e => setInput(e.target.value)}
                  placeholder="Ask about regulations, appeals, or your policy..." disabled={loading} />
                <button type="submit" className="btn btn-red" disabled={!input.trim() || loading}
                  style={{ borderRadius: '9999px', padding: '0 1.5rem', flexShrink: 0 }}>
                  <IconZap size={16} /> Send
                </button>
              </form>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
