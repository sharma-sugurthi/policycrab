/**
 * TaskContext — Global Background Task Manager
 *
 * Keeps long-running AI operations (bill audit, policy upload, claim eval, chat)
 * alive across React page navigation. When a page unmounts, the fetch() request
 * keeps running; the result lands here and is restored when the user returns.
 *
 * Tasks auto-expire after 10 minutes (no extra AI cost — just clears cached results).
 */

import { createContext, useContext, useReducer, useCallback, useRef } from 'react'

const TASK_TTL_MS = 10 * 60 * 1000 // 10 minutes

const TaskContext = createContext(null)

// ── Action Types ──────────────────────────────────────────────────────
const ADD    = 'ADD'
const DONE   = 'DONE'
const ERROR  = 'ERROR'
const REMOVE = 'REMOVE'
const PURGE  = 'PURGE'   // remove all expired tasks

function reducer(state, action) {
  switch (action.type) {
    case ADD:
      return [...state, action.task]
    case DONE:
      return state.map(t =>
        t.id === action.id
          ? { ...t, status: 'done', result: action.result, completedAt: Date.now() }
          : t
      )
    case ERROR:
      return state.map(t =>
        t.id === action.id
          ? { ...t, status: 'error', error: action.error, completedAt: Date.now() }
          : t
      )
    case REMOVE:
      return state.filter(t => t.id !== action.id)
    case PURGE:
      return state.filter(t => !t.completedAt || Date.now() - t.completedAt < TASK_TTL_MS)
    default:
      return state
  }
}

let _idCounter = 0
function nextId() { return `task_${++_idCounter}_${Date.now()}` }

// ── Provider ──────────────────────────────────────────────────────────
export function TaskProvider({ children }) {
  const [tasks, dispatch] = useReducer(reducer, [])
  const tasksRef = useRef(tasks)
  tasksRef.current = tasks

  /**
   * Register a new background task.
   * @param {string} type   — identifies which page owns this task (e.g. 'bill_audit')
   * @param {string} label  — human-readable description shown in the status bar
   * @param {() => Promise<any>} fn — async function that performs the work
   * @returns {string} taskId
   */
  const addTask = useCallback((type, label, fn) => {
    // Purge stale completed tasks before adding a new one
    dispatch({ type: PURGE })

    const id = nextId()
    dispatch({
      type: ADD,
      task: { id, type, label, status: 'running', result: null, error: null, startedAt: Date.now(), completedAt: null },
    })

    // Execute the async function; results land in context regardless of which page is mounted.
    // Returns a Promise so callers can optionally chain .then/.catch.
    const promise = Promise.resolve()
      .then(() => fn())
      .then(result => { dispatch({ type: DONE, id, result }); return result })
      .catch(err  => { dispatch({ type: ERROR, id, error: err?.message || String(err) }); throw err })

    return promise
  }, [])

  const removeTask = useCallback((id) => dispatch({ type: REMOVE, id }), [])

  /**
   * Get the most recent task of a given type.
   * Pages call this on mount to restore a result if they navigated away.
   */
  const getLatestTask = useCallback((type) => {
    const matching = tasksRef.current
      .filter(t => t.type === type)
      .sort((a, b) => b.startedAt - a.startedAt)
    return matching[0] || null
  }, [])

  return (
    <TaskContext.Provider value={{ tasks, addTask, removeTask, getLatestTask }}>
      {children}
    </TaskContext.Provider>
  )
}

// ── Hooks ─────────────────────────────────────────────────────────────
export function useTasks() {
  const ctx = useContext(TaskContext)
  if (!ctx) throw new Error('useTasks must be used inside <TaskProvider>')
  return ctx
}

/** Convenience hook: returns the latest task for a specific page type */
export function usePageTask(type) {
  const { getLatestTask, removeTask } = useTasks()
  return { task: getLatestTask(type), removeTask }
}
