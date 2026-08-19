/**
 * TaskStatusBar - Floating global task status bar.
 *
 * Appears at the bottom of the screen (like a browser download bar) when any
 * background task is running or recently completed. Shows per-task status with
 * a dismiss (X) button. Clicking a "done" task navigates back to that page.
 */

import { useNavigate } from 'react-router-dom'
import { useTasks } from '../contexts/TaskContext'

// Maps task type → route to navigate to on click
const TASK_ROUTES = {
  bill_audit:    '/audit',
  policy_upload: '/policy',
  claim_eval:    '/claim',
  chat_message:  '/chat',
  appeal_draft:  '/routing',
}

// Maps task type → friendly page name
const TASK_LABELS = {
  bill_audit:    'Bill Auditor',
  policy_upload: 'Policy Upload',
  claim_eval:    'Claim Evaluator',
  chat_message:  'Chat',
  appeal_draft:  'Appeal Studio',
}

function SpinnerIcon() {
  return (
    <span style={{
      display: 'inline-block',
      width: '14px', height: '14px',
      border: '2px solid rgba(255,255,255,0.3)',
      borderTopColor: '#fff',
      borderRadius: '50%',
      animation: 'spin 0.7s linear infinite',
      flexShrink: 0,
    }} />
  )
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function ErrorIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  )
}

export default function TaskStatusBar() {
  const { tasks, removeTask } = useTasks()
  const navigate = useNavigate()

  // Only show tasks that are running or completed within the last 10 minutes
  // Filter out internal snapshot tasks (chat_session used only for state restore)
  const visible = tasks.filter(t =>
    t.label !== '_session_snapshot_' &&
    (t.status === 'running' ||
    (t.completedAt && Date.now() - t.completedAt < 10 * 60 * 1000))
  )

  if (visible.length === 0) return null

  return (
    <>
      {/* Inject keyframe for spinner */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <div style={{
        position: 'fixed',
        bottom: '1.25rem',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 9998,
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        alignItems: 'center',
        pointerEvents: 'none',   // allow clicks to pass through the container
      }}>
        {visible.map(task => {
          const isRunning = task.status === 'running'
          const isDone    = task.status === 'done'
          const isError   = task.status === 'error'
          const route     = TASK_ROUTES[task.type]
          const pageName  = TASK_LABELS[task.type] || task.type

          const bg    = isRunning ? '#1e293b' : isDone ? '#14532d' : '#7f1d1d'
          const color = '#fff'

          return (
            <div
              key={task.id}
              style={{
                pointerEvents: 'auto',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.625rem 1rem',
                background: bg,
                color,
                borderRadius: '999px',
                boxShadow: '0 4px 24px rgba(0,0,0,0.25)',
                fontSize: '0.8125rem',
                fontWeight: 600,
                fontFamily: "'Inter', system-ui, sans-serif",
                cursor: isDone && route ? 'pointer' : 'default',
                transition: 'opacity 0.3s',
                maxWidth: '420px',
                whiteSpace: 'nowrap',
              }}
              onClick={() => {
                if (isDone && route) {
                  navigate(route)
                }
              }}
              title={isDone && route ? `Go to ${pageName}` : undefined}
            >
              {/* Status icon */}
              {isRunning && <SpinnerIcon />}
              {isDone    && <CheckIcon />}
              {isError   && <ErrorIcon />}

              {/* Label */}
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {isRunning && task.label}
                {isDone    && `${pageName} complete - click to view`}
                {isError   && `${pageName} failed: ${task.error?.slice(0, 60) || 'Unknown error'}`}
              </span>

              {/* Dismiss button */}
              {!isRunning && (
                <button
                  onClick={e => { e.stopPropagation(); removeTask(task.id) }}
                  title="Dismiss"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'rgba(255,255,255,0.6)',
                    cursor: 'pointer',
                    padding: '0.125rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: '50%',
                    flexShrink: 0,
                  }}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              )}
            </div>
          )
        })}
      </div>
    </>
  )
}
