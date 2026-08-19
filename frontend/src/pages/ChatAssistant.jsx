import { useState, useRef, useEffect, useCallback } from 'react'
import { apiFetch, readApiResponse, formatApiError } from '../lib/api'
import { useAuth } from '../contexts/AuthContext'
import { useTasks } from '../contexts/TaskContext'
import {
  IconPlus, IconTrash, IconMessageCircle, IconZap,
  IconBriefcase, IconActivity, IconSearch
} from '../components/Icons'

const CHAT_TIMEOUT_MS = 45000

function apiFetchWithTimeout(endpoint, options = {}, timeoutMs = CHAT_TIMEOUT_MS) {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)
  return apiFetch(endpoint, { ...options, signal: controller.signal })
    .finally(() => window.clearTimeout(timeoutId))
}

// Render markdown-lite: bold + line breaks
function renderContent(content) {
  const lines = content.split('\n')
  return lines.map((line, li) => {
    const parts = line.split(/(\*\*.*?\*\*)/g)
    return (
      <span key={li}>
        {parts.map((part, pi) =>
          part.startsWith('**') && part.endsWith('**')
            ? <strong key={pi}>{part.slice(2, -2)}</strong>
            : <span key={pi}>{part}</span>
        )}
        {li < lines.length - 1 ? <br /> : null}
      </span>
    )
  })
}

// Send icon (arrow up)
function IconArrowUp({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="19" x2="12" y2="5" />
      <polyline points="5 12 12 5 19 12" />
    </svg>
  )
}

const QUICK_QUESTIONS = [
  "What are my rights under the No Surprises Act?",
  "How long do I have to file an ERISA appeal?",
  "What does 'medical necessity' mean in my policy?",
  "Can an ER balance bill me if they're out-of-network?",
  "What's the difference between HMO and PPO?",
]

export default function ChatAssistant({ policyProfile, costBreakdown }) {
  const { user } = useAuth()
  const { addTask, getLatestTask } = useTasks()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [chatSessions, setChatSessions] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)

  const feedRef = useRef(null)
  const inputRef = useRef(null)

  const isNewChat = messages.length === 0

  // Auto-scroll feed to bottom whenever messages change
  const scrollToBottom = useCallback(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading, scrollToBottom])

  // Fetch chat session list
  const fetchSessions = useCallback(async () => {
    try {
      const res = await apiFetchWithTimeout('/chat/sessions')
      if (res.ok) {
        const data = await readApiResponse(res)
        setChatSessions(data || [])
      }
    } catch (err) {
      console.error('Failed to load chat sessions', err)
    }
  }, [])

  useEffect(() => {
    if (user) {
      fetchSessions()
    }
  }, [fetchSessions, user])

  // Restore last active chat session when user navigates back to Chat
  useEffect(() => {
    const task = getLatestTask('chat_session')
    if (task?.status === 'done' && task.result) {
      const { chatId, msgs } = task.result
      if (chatId && msgs?.length) {
        setActiveChatId(chatId)
        setMessages(msgs)
        return
      }
    }
    // If a message was in-flight, show it as pending in the thread
    const pending = getLatestTask('chat_message')
    if (pending?.status === 'running' && pending.result?.pendingMessages) {
      setMessages(pending.result.pendingMessages)
      setLoading(true)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadSession = async (chatId) => {
    if (chatId === activeChatId) return
    setActiveChatId(chatId)
    setLoading(true)
    try {
      const res = await apiFetchWithTimeout(`/chat/session?chat_id=${chatId}`)
      if (res.ok) {
        const data = await readApiResponse(res)
        setMessages(data.messages?.length ? data.messages : [])
      }
    } catch (err) {
      console.error('Failed to load session', err)
    } finally {
      setLoading(false)
    }
  }

  const handleNewChat = () => {
    setActiveChatId(null)
    setMessages([])
    inputRef.current?.focus()
  }

  const handleDeleteSession = async (e, chatId) => {
    e.stopPropagation()
    try {
      await apiFetchWithTimeout(`/chat/session/${chatId}`, { method: 'DELETE' })
      if (activeChatId === chatId) handleNewChat()
      fetchSessions()
    } catch (err) {
      console.error('Failed to delete session', err)
    }
  }

  const handleSend = async (text) => {
    const userMsg = (text || input).trim()
    if (!userMsg || loading) return
    setInput('')
    const newMessages = [...messages, { role: 'user', content: userMsg }]
    setMessages(newMessages)
    setLoading(true)

    const capturedChatId = activeChatId
    const capturedMessages = newMessages

    addTask('chat_message', 'Chat response loading…', async () => {
      const payload = { message: userMsg, policy_profile: policyProfile, cost_breakdown: costBreakdown }
      if (capturedChatId) payload.chat_id = capturedChatId

      const res = await apiFetchWithTimeout('/chat/message', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      const data = await readApiResponse(res)

      let finalMessages
      if (!res.ok) {
        finalMessages = [...capturedMessages, { role: 'ai', content: formatApiError(data, 'The assistant could not complete that request. Please try again.') }]
      } else if (!data || typeof data === 'string') {
        finalMessages = [...capturedMessages, { role: 'ai', content: 'The assistant is temporarily unavailable. Please try again.' }]
      } else if (data.messages?.length) {
        finalMessages = data.messages
      } else {
        finalMessages = [...capturedMessages, { role: 'ai', content: data.error ? `Error: ${data.error}` : data.response }]
      }

      const finalChatId = data?.chat_id || capturedChatId
      setMessages(finalMessages)
      setLoading(false)
      if (data?.chat_id && data.chat_id !== capturedChatId) {
        setActiveChatId(data.chat_id)
        fetchSessions()
      }

      // Persist session state into TaskContext so returning to Chat restores it
      return { chatId: finalChatId, msgs: finalMessages }
    }).then(sessionData => {
      // Store the session under its own type key so the restore-on-mount check finds it
      if (sessionData?.chatId) {
        addTask('chat_session', '_session_snapshot_', async () => sessionData)
      }
    }).catch(err => {
      const msg = err?.name === 'AbortError'
        ? 'The assistant took too long to respond. Please try again with a shorter question.'
        : 'Connection error - please check your connection and try again.'
      setMessages(prev => [...prev, { role: 'ai', content: msg }])
      setLoading(false)
    })
  }


  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Derive user initials for avatar
  const userInitials = user?.user_metadata?.full_name
    ? user.user_metadata.full_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
    : (user?.email?.[0] ?? 'U').toUpperCase()

  // Context pill labels
  const hasPolicyCtx = Boolean(policyProfile)
  const hasClaimCtx = Boolean(costBreakdown)

  return (
    <div className="chat-page-shell">
      {/* ── Sidebar ───────────────────────────────────── */}
      <aside className="chat-sidebar">
        <div className="chat-sidebar-header">
          <button
            className="btn btn-red"
            onClick={handleNewChat}
            style={{ width: '100%', justifyContent: 'center', padding: '0.625rem 1rem', fontSize: '0.875rem' }}
          >
            <IconPlus size={15} /> New Chat
          </button>
        </div>

        <div className="chat-sidebar-sessions">
          {chatSessions.length === 0 ? (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', padding: '1.25rem 0.5rem' }}>
              No previous chats
            </p>
          ) : (
            chatSessions.map(session => (
              <div
                key={session.id}
                className={`chat-session-item${activeChatId === session.id ? ' active' : ''}`}
                onClick={() => loadSession(session.id)}
              >
                <IconMessageCircle size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                <span className="chat-session-title">{session.title || 'New Chat'}</span>
                <button
                  className="chat-session-delete"
                  onClick={(e) => handleDeleteSession(e, session.id)}
                  title="Delete"
                >
                  <IconTrash size={13} />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Context status */}
        <div className="chat-sidebar-footer">
          <p style={{ fontSize: '0.6875rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Context</p>
          <div className="chat-context-status">
            <div className="chat-context-row">
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <IconBriefcase size={12} /> Policy
              </span>
              <span className={`badge ${hasPolicyCtx ? 'badge-success' : 'badge-zinc'}`} style={{ fontSize: '0.65rem', padding: '0.125rem 0.5rem' }}>
                {hasPolicyCtx ? 'Loaded' : 'None'}
              </span>
            </div>
            <div className="chat-context-row">
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <IconActivity size={12} /> Claim
              </span>
              <span className={`badge ${hasClaimCtx ? 'badge-success' : 'badge-zinc'}`} style={{ fontSize: '0.65rem', padding: '0.125rem 0.5rem' }}>
                {hasClaimCtx ? 'Loaded' : 'None'}
              </span>
            </div>
            <div className="chat-context-row">
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <IconSearch size={12} /> Knowledge
              </span>
              <span className="badge badge-info" style={{ fontSize: '0.65rem', padding: '0.125rem 0.5rem' }}>Active</span>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main Chat Column ──────────────────────────── */}
      <main className="chat-main">
        {/* Message Feed */}
        <div className="chat-feed" ref={feedRef}>
          {isNewChat ? (
            /* Welcome / empty state - suggestions only appear here */
            <div className="chat-welcome">
              <div className="chat-welcome-icon">
                <IconZap size={26} />
              </div>
              <div>
                <h2 className="chat-welcome-title">How can I help you today?</h2>
                <p className="chat-welcome-sub">
                  Ask me about your insurance coverage, claims, denials, appeal rights, or any US health insurance question.
                </p>
              </div>
              <div className="chat-suggestion-chips">
                {QUICK_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    className="chat-suggestion-chip"
                    onClick={() => handleSend(q)}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-feed-inner">
              {messages.map((msg, idx) => (
                <div key={idx} className={`chat-message-row ${msg.role}`}>
                  <div className={`chat-avatar ${msg.role === 'ai' ? 'ai-avatar' : 'user-avatar'}`}>
                    {msg.role === 'ai' ? 'AI' : userInitials}
                  </div>
                  <div className="chat-message-content">
                    {msg.role === 'ai' ? renderContent(msg.content) : msg.content}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="chat-message-row ai">
                  <div className="chat-avatar ai-avatar">AI</div>
                  <div className="chat-typing">
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Anchored Input Bar */}
        <div className="chat-input-dock">
          <div className="chat-input-dock-inner">
            <textarea
              ref={inputRef}
              className="chat-input-field"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your coverage, appeals, or policy rights..."
              disabled={loading}
              rows={1}
            />
            <button
              className="chat-send-btn"
              onClick={() => handleSend()}
              disabled={!input.trim() || loading}
              title="Send (Enter)"
            >
              <IconArrowUp size={16} />
            </button>
          </div>
          <p className="chat-input-hint">Press Enter to send · Shift+Enter for new line</p>
        </div>
      </main>
    </div>
  )
}
