/**
 * AILogViewer — Real-time terminal-style AI step log viewer.
 *
 * Connects to the backend SSE endpoint (/api/stream/ai-logs) and
 * streams step-by-step progress updates live to the user.
 *
 * Usage:
 *   <AILogViewer task="legal_writing" active={isRunning} />
 */

import { useEffect, useRef, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const TASK_LABELS = {
  extraction: 'Policy Extraction',
  tool_calling: 'Code Lookup',
  legal_writing: 'Appeal Drafting',
  explanation: 'Plain English',
  chat: 'AI Chat',
}

export default function AILogViewer({ task = 'legal_writing', active = false, onComplete = null }) {
  const [logs, setLogs] = useState([])
  const [status, setStatus] = useState('idle') // idle | streaming | done | error
  const [currentStep, setCurrentStep] = useState(0)
  const [totalSteps, setTotalSteps] = useState(0)
  const bodyRef = useRef(null)
  const esRef = useRef(null)

  // Auto-scroll to bottom as new logs arrive
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight
    }
  }, [logs])

  // Start/stop streaming when `active` prop changes
  useEffect(() => {
    if (active && status !== 'streaming') {
      startStream()
    }
    return () => {
      if (esRef.current) {
        esRef.current.close()
      }
    }
  }, [active, task]) // eslint-disable-line react-hooks/exhaustive-deps

  const startStream = () => {
    // Reset state
    setLogs([])
    setStatus('streaming')
    setCurrentStep(0)
    setTotalSteps(0)

    // Close any existing stream
    if (esRef.current) esRef.current.close()

    // Build authenticated SSE URL (Supabase token from localStorage)
    const token = (() => {
      try {
        const raw = localStorage.getItem('sb-' + (import.meta.env.VITE_SUPABASE_URL || '').replace(/^https?:\/\//, '').split('.')[0] + '-auth-token')
        if (raw) {
          const parsed = JSON.parse(raw)
          return parsed?.access_token || ''
        }
      } catch {}
      return ''
    })()

    const url = `${API_BASE}/api/stream/ai-logs?task=${task}`

    // Use fetch for SSE with auth header (EventSource doesn't support headers natively)
    const ctrl = new AbortController()
    esRef.current = { close: () => ctrl.abort() }

    fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: ctrl.signal,
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n\n')
          buffer = lines.pop() || ''

          for (const chunk of lines) {
            const line = chunk.replace(/^data: /, '').trim()
            if (!line) continue
            try {
              const event = JSON.parse(line)
              handleEvent(event)
            } catch {}
          }
        }
        setStatus('done')
        if (onComplete) onComplete()
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setStatus('error')
          setLogs(prev => [...prev, {
            type: 'error',
            timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
            message: `[Error] Could not connect to AI stream: ${err.message}`,
          }])
        }
      })
  }

  const handleEvent = (event) => {
    setLogs(prev => [...prev, event])
    if (event.type === 'step') {
      setCurrentStep(event.step_index + 1)
      setTotalSteps(event.total_steps)
    }
    if (event.type === 'done') {
      setStatus('done')
      if (onComplete) onComplete()
    }
  }

  const progress = totalSteps > 0 ? Math.round((currentStep / totalSteps) * 100) : 0

  return (
    <div className="ai-log-viewer" role="log" aria-label="AI execution log" aria-live="polite">
      {/* ── Terminal Header ─────────────────────────────────── */}
      <div className="ai-log-header">
        <div className="ai-log-header-left">
          <div className="ai-log-dots">
            <span />
            <span />
            <span />
          </div>
          <span className="ai-log-title">
            Coverage assistant — {TASK_LABELS[task] || task}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* Progress bar */}
          {status === 'streaming' && totalSteps > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{
                width: '80px', height: '4px',
                background: '#252a38',
                borderRadius: '9999px',
                overflow: 'hidden',
              }}>
                <div style={{
                  height: '100%',
                  width: `${progress}%`,
                  background: 'linear-gradient(90deg, #22c55e, #16a34a)',
                  borderRadius: '9999px',
                  transition: 'width 0.5s ease',
                }} />
              </div>
              <span style={{ color: '#22c55e', fontSize: '0.6875rem', fontWeight: 700 }}>
                {progress}%
              </span>
            </div>
          )}

          {/* Status badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.375rem',
            fontSize: '0.6875rem',
            fontWeight: 700,
            color: status === 'streaming' ? '#22c55e'
              : status === 'done' ? '#60a5fa'
              : status === 'error' ? '#ef4444'
              : '#4a526a',
          }}>
            {status === 'streaming' && (
              <span style={{
                width: '6px', height: '6px',
                borderRadius: '50%',
                background: '#22c55e',
                animation: 'pulseGreen 1.2s ease-in-out infinite',
                display: 'inline-block',
              }} />
            )}
            {status === 'streaming' ? 'LIVE'
              : status === 'done' ? 'COMPLETE'
              : status === 'error' ? 'ERROR'
              : 'IDLE'}
          </div>
        </div>
      </div>

      {/* ── Log Body ────────────────────────────────────────── */}
      <div className="ai-log-body" ref={bodyRef}>
        {logs.length === 0 && status === 'idle' && (
          <div style={{ color: '#4a526a', fontStyle: 'italic' }}>
            Waiting for the task to start...
          </div>
        )}

        {logs.map((log, i) => (
          <LogLine key={i} log={log} />
        ))}

        {status === 'streaming' && (
          <div className="ai-log-line">
            <span className="timestamp">{new Date().toLocaleTimeString('en-US', { hour12: false })}</span>
            <span style={{ color: '#4a526a' }}>▌</span>
          </div>
        )}
      </div>
    </div>
  )
}

function LogLine({ log }) {
  const isSuccess = log.message?.includes('✓') || log.type === 'done'
  const isError = log.type === 'error'
  const isSystem = log.type === 'start' || log.type === 'done'

  return (
    <div className="ai-log-line">
      <span className="timestamp">{log.timestamp}</span>
      {!isSystem && (
        <span className="provider">
          {log.message?.startsWith('[Gemini Pro]') ? 'gemini-pro' : 'gemini'}
        </span>
      )}
      <span className={`message ${isSuccess ? 'success' : ''} ${isError ? 'highlight' : ''}`}
        style={isSystem ? { color: '#6b7490', fontStyle: 'italic' } : {}}
      >
        {log.message}
      </span>
    </div>
  )
}
