import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { apiFetch, readApiResponse } from '../lib/api'
import { IconCpu, IconActivity, IconSearch, IconBriefcase, IconZap, IconPlus, IconTrash, IconMessageCircle } from '../components/Icons'

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
  const defaultGreeting = { role: 'ai', content: "Hi! I'm the PolicyCrab AI assistant. I can help you understand your insurance coverage, claims, denials, or appeal rights under US law. How can I help you today?" }

  const [messages, setMessages] = useState([defaultGreeting])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [chatSessions, setChatSessions] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)
  const messagesEndRef = useRef(null)

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  // Fetch list of all chat sessions
  const fetchSessions = async () => {
    try {
      const res = await apiFetch('/chat/sessions')
      if (res.ok) {
        const data = await readApiResponse(res)
        setChatSessions(data || [])
        // Auto-select most recent if none selected
        if (!activeChatId && data?.length > 0) {
          loadSession(data[0].id)
        }
      }
    } catch (err) {
      console.error('Failed to load chat sessions', err)
    }
  }

  useEffect(() => {
    fetchSessions()
  }, [])

  // Load a specific session
  const loadSession = async (chatId) => {
    if (chatId === activeChatId) return
    setActiveChatId(chatId)
    setLoading(true)
    try {
      const res = await apiFetch(`/chat/session?chat_id=${chatId}`)
      if (res.ok) {
        const data = await readApiResponse(res)
        if (data.messages?.length > 0) {
          setMessages(data.messages)
        } else {
          setMessages([defaultGreeting])
        }
      }
    } catch (err) {
      console.error('Failed to load session', err)
    } finally {
      setLoading(false)
    }
  }

  const handleNewChat = () => {
    setActiveChatId(null)
    setMessages([defaultGreeting])
  }

  const handleDeleteSession = async (e, chatId) => {
    e.stopPropagation()
    try {
      await apiFetch(`/chat/session/${chatId}`, { method: 'DELETE' })
      if (activeChatId === chatId) {
        handleNewChat()
      }
      fetchSessions()
    } catch (err) {
      console.error('Failed to delete session', err)
    }
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    try {
      const payload = { message: userMsg, policy_profile: policyProfile, cost_breakdown: costBreakdown }
      if (activeChatId) payload.chat_id = activeChatId

      const res = await apiFetch('/chat/message', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      const data = await readApiResponse(res)
      if (!data || typeof data === 'string') {
        console.error('Backend non-JSON response:', data || '')
        setMessages(prev => [...prev, { role: 'ai', content: 'The assistant is temporarily unavailable. Please try again in a few seconds.' }])
        return
      }
      if (data.messages?.length) setMessages(data.messages)
      else setMessages(prev => [...prev, { role: 'ai', content: data.error ? `Error: ${data.error}` : data.response }])

      if (data.chat_id && data.chat_id !== activeChatId) {
        setActiveChatId(data.chat_id)
        fetchSessions()
      }
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
          </div>
        </motion.div>

        <div className="grid-2" style={{ gap: '1.5rem', alignItems: 'start', gridTemplateColumns: '1fr 2fr' }}>
          {/* ── Left Panel (Sidebar) ─────────────────── */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}
            style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

            {/* Chat History List */}
            <div className="card" style={{ padding: '1.25rem', background: 'var(--bg-card)', border: '1px solid var(--border-secondary)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <button className="btn btn-red" onClick={handleNewChat} style={{ width: '100%', justifyContent: 'center' }}>
                <IconPlus size={16} /> New Chat
              </button>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', maxHeight: '250px', overflowY: 'auto', paddingRight: '0.5rem' }}>
                {chatSessions.length === 0 ? (
                  <p style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', textAlign: 'center', padding: '1rem 0' }}>No previous chats.</p>
                ) : (
                  chatSessions.map(session => (
                    <div key={session.id} 
                         onClick={() => loadSession(session.id)}
                         style={{ 
                           display: 'flex', alignItems: 'center', justifyContent: 'space-between', 
                           padding: '0.75rem', borderRadius: '8px', cursor: 'pointer',
                           background: activeChatId === session.id ? 'var(--bg-secondary)' : 'transparent',
                           border: `1px solid ${activeChatId === session.id ? 'var(--border-primary)' : 'transparent'}`
                         }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                        <IconMessageCircle size={14} style={{ color: 'var(--text-tertiary)', flexShrink: 0 }} />
                        <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {session.title || 'New Chat'}
                        </span>
                      </div>
                      <button onClick={(e) => handleDeleteSession(e, session.id)} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', padding: '0.25rem' }}>
                        <IconTrash size={14} />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

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
            <div className="chat-panel" style={{ height: 'calc(100vh - 220px)' }}>
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
