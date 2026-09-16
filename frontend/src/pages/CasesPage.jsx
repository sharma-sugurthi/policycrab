import { useCallback, useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useOrg } from '../contexts/OrgContext'
import { apiFetch, formatApiError, readApiResponse } from '../lib/api'
import {
  CLOSED_STATUSES, OPEN_STATUSES, PRIORITIES, PRIORITY_BADGE, PRIORITY_LABEL, STATUSES, STATUS_BADGE, STATUS_LABEL,
  dueLabel, dueTone, filterCases, money,
} from '../lib/cases'
import { IconAlertTriangle, IconBriefcase, IconCheckCircle, IconClock, IconTrash, IconUsers, IconX } from '../components/Icons'

const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }
const labelStyle = { display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '0.375rem' }
const TONE_COLOR = { danger: 'var(--danger)', warning: 'var(--warning)', muted: 'var(--text-tertiary)' }

async function call(endpoint, options, fallback) {
  const res = await apiFetch(endpoint, options)
  const data = await readApiResponse(res)
  if (!res.ok) {
    const err = new Error(formatApiError(data, fallback))
    err.status = res.status
    throw err
  }
  return data
}

function Notice({ status }) {
  if (!status) return null
  const ok = status.type === 'success'
  return (
    <div role={ok ? 'status' : 'alert'} style={{
      padding: '0.625rem 0.875rem', borderRadius: '0.5rem', fontSize: '0.8125rem', display: 'flex', alignItems: 'flex-start', gap: '0.5rem',
      background: ok ? 'var(--success-bg)' : 'var(--danger-bg)', color: ok ? 'var(--success)' : 'var(--danger)',
      border: `1px solid ${ok ? '#a7f3d0' : '#fecaca'}`, lineHeight: 1.5,
    }}>
      {ok ? <IconCheckCircle size={14} style={{ flexShrink: 0, marginTop: '2px' }} /> : <IconAlertTriangle size={14} style={{ flexShrink: 0, marginTop: '2px' }} />}
      <span>{status.message}</span>
    </div>
  )
}

function Tile({ label, value, tone }) {
  return (
    <div className="card-zinc" style={{ padding: '0.875rem 1rem', minWidth: 0 }}>
      <p style={{ fontSize: '0.6875rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>{label}</p>
      <p style={{ fontSize: '1.375rem', fontWeight: 800, color: tone ? TONE_COLOR[tone] : 'var(--text-primary)', margin: '0.25rem 0 0', lineHeight: 1.1 }}>{value}</p>
    </div>
  )
}

export default function CasesPage() {
  const { user } = useAuth()
  const { activeOrg, enabled: orgsEnabled } = useOrg()
  const navigate = useNavigate()

  const [cases, setCases] = useState([])
  const [scope, setScope] = useState(null)
  const [summary, setSummary] = useState(null)
  const [members, setMembers] = useState([])
  const [loading, setLoading] = useState(true)
  const [disabled, setDisabled] = useState(false)
  const [status, setStatus] = useState(null)
  const [filters, setFilters] = useState({ status: 'open', assignee: 'all', query: '', includeClosed: true })
  const [selectedId, setSelectedId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setStatus(null)
    try {
      const [list, sum] = await Promise.all([
        call('/cases?include_closed=true&limit=500', undefined, 'Could not load cases.'),
        call('/cases/summary', undefined, 'Could not load the pipeline summary.'),
      ])
      setCases(list.cases || [])
      setScope(list.scope || null)
      setSummary(sum)
      setDisabled(false)
      if (activeOrg) {
        const m = await apiFetch(`/orgs/${activeOrg.id}/members`).then(readApiResponse).catch(() => [])
        setMembers(Array.isArray(m) ? m : [])
      } else {
        setMembers([])
      }
    } catch (err) {
      if (err.status === 404 && /not enabled/i.test(err.message)) setDisabled(true)
      else setStatus({ type: 'error', message: err.message })
    } finally {
      setLoading(false)
    }
  }, [activeOrg])

  useEffect(() => { load() }, [load])

  const canWrite = scope ? ['owner', 'admin', 'member'].includes(scope.role) : false
  const isAdmin = scope ? ['owner', 'admin'].includes(scope.role) : false
  const visible = useMemo(() => filterCases(cases, { ...filters, me: user?.id }), [cases, filters, user])
  const selected = cases.find(c => c.id === selectedId) || null
  const assignable = members.filter(m => ['owner', 'admin', 'member'].includes(m.role))

  const applyUpdated = (updated) => setCases(prev => prev.map(c => (c.id === updated.id ? updated : c)))

  return (
    <section className="section-white section-pad">
      <div className="main">
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }} style={{ marginBottom: '1.5rem' }}>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label"><span className="line" /> Case Management</motion.p>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.55 }} className="section-title">
            {activeOrg ? <>{activeOrg.name} <span className="gradient-text">Cases</span></> : <>My <span className="gradient-text">Cases</span></>}
          </motion.h1>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-subtitle">
            {activeOrg
              ? 'Every appeal your team is working, who owns it, and what is due. Open a case from any claim on the Dashboard.'
              : 'Track your own appeals from denial to decision. Select a workspace on Team Workspaces to see your team\'s pipeline.'}
          </motion.p>
        </motion.div>

        {disabled && (
          <div className="card" style={{ padding: '2rem' }}>
            <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Case management is not enabled here</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              An administrator can turn it on by applying database migration 013 and setting <code>CASES_ENABLED=true</code> on the backend.
            </p>
          </div>
        )}

        {!disabled && (
          <>
            {status && <div style={{ marginBottom: '1rem' }}><Notice status={status} /></div>}

            {summary && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
                <Tile label="Open" value={summary.open} />
                <Tile label="Overdue" value={summary.overdue} tone={summary.overdue ? 'danger' : undefined} />
                <Tile label={`Due ≤ ${summary.due_soon_days}d`} value={summary.due_soon} tone={summary.due_soon ? 'warning' : undefined} />
                <Tile label="Unassigned" value={summary.unassigned} />
                <Tile label="At stake (open)" value={money(summary.amount_at_stake_open)} />
                <Tile label="Recovered" value={money(summary.amount_recovered)} />
                <Tile label="Overturn rate" value={summary.overturn_rate == null ? '—' : `${Math.round(summary.overturn_rate * 100)}%`} />
                <Tile label="Avg days to close" value={summary.avg_days_to_close ?? '—'} />
              </div>
            )}

            <div className="card" style={{ padding: '1.25rem 1.5rem' }}>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: '1rem' }}>
                <div style={{ flex: '1 1 200px' }}>
                  <label style={labelStyle} htmlFor="case-search">Search</label>
                  <input id="case-search" className="input" placeholder="Title, reference, assignee…" value={filters.query} onChange={e => setFilters({ ...filters, query: e.target.value })} />
                </div>
                <div style={{ flex: '0 1 180px' }}>
                  <label style={labelStyle} htmlFor="case-status">Status</label>
                  <select id="case-status" className="input" value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}>
                    <option value="open">All open</option>
                    <option value="all">All (incl. closed)</option>
                    <optgroup label="Open">{OPEN_STATUSES.map(s => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}</optgroup>
                    <optgroup label="Closed">{CLOSED_STATUSES.map(s => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}</optgroup>
                  </select>
                </div>
                <div style={{ flex: '0 1 200px' }}>
                  <label style={labelStyle} htmlFor="case-assignee">Assignee</label>
                  <select id="case-assignee" className="input" value={filters.assignee} onChange={e => setFilters({ ...filters, assignee: e.target.value })}>
                    <option value="all">Anyone</option>
                    <option value="me">Me</option>
                    <option value="unassigned">Unassigned</option>
                    {assignable.map(m => <option key={m.user_id} value={m.user_id}>{m.email}</option>)}
                  </select>
                </div>
                <button type="button" className="btn btn-ghost" onClick={load} disabled={loading} style={{ padding: '0.5rem 0.875rem', fontSize: '0.8125rem' }}>Refresh</button>
              </div>

              {loading ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}><span className="spinner" /></div>
              ) : visible.length === 0 ? (
                <div className="dashboard-empty" style={{ padding: '2rem 1rem' }}>
                  <IconBriefcase size={28} />
                  <h3 style={{ marginTop: '0.5rem' }}>{cases.length === 0 ? 'No cases yet' : 'No cases match these filters'}</h3>
                  <p>{cases.length === 0 ? 'Open a case from any evaluated claim on the Dashboard to start tracking it here.' : 'Try widening the status or assignee filter.'}</p>
                  {cases.length === 0 && <button type="button" className="btn btn-red" onClick={() => navigate('/dashboard')}>Go to Dashboard</button>}
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
                    <thead>
                      <tr style={{ textAlign: 'left', color: 'var(--text-tertiary)', fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        <th style={{ padding: '0.5rem 0.5rem 0.5rem 0' }}>Case</th>
                        <th style={{ padding: '0.5rem' }}>Status</th>
                        <th style={{ padding: '0.5rem' }}>Priority</th>
                        <th style={{ padding: '0.5rem' }}>Assignee</th>
                        <th style={{ padding: '0.5rem' }}>Due</th>
                        <th style={{ padding: '0.5rem', textAlign: 'right' }}>At stake</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visible.map(c => (
                        <tr key={c.id} onClick={() => setSelectedId(c.id)} style={{ borderTop: '1px solid var(--border-secondary)', cursor: 'pointer', opacity: c.is_open ? 1 : 0.7 }}>
                          <td style={{ padding: '0.75rem 0.5rem 0.75rem 0', minWidth: '220px' }}>
                            <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{c.title}</div>
                            <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                              {c.reference && <span>#{c.reference}</span>}
                              {c.claim?.success_score_band && <span>Case strength: {c.claim.success_score_band}</span>}
                              {c.claim?.appeal_recommendation && <span>{c.claim.appeal_recommendation.replace(/_/g, ' ').toLowerCase()}</span>}
                            </div>
                          </td>
                          <td style={{ padding: '0.75rem 0.5rem' }}><span className={`badge ${STATUS_BADGE[c.status] || 'badge-zinc'}`} style={{ fontSize: '0.6875rem' }}>{STATUS_LABEL[c.status] || c.status}</span></td>
                          <td style={{ padding: '0.75rem 0.5rem' }}><span className={`badge ${PRIORITY_BADGE[c.priority] || 'badge-zinc'}`} style={{ fontSize: '0.6875rem' }}>{PRIORITY_LABEL[c.priority] || c.priority}</span></td>
                          <td style={{ padding: '0.75rem 0.5rem', color: c.assignee_id ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>{c.assignee_email || (c.assignee_id ? 'Assigned' : 'Unassigned')}</td>
                          <td style={{ padding: '0.75rem 0.5rem', color: TONE_COLOR[dueTone(c)], fontWeight: dueTone(c) === 'muted' ? 500 : 700, whiteSpace: 'nowrap' }}>{dueLabel(c)}</td>
                          <td style={{ padding: '0.75rem 0.5rem', textAlign: 'right', fontWeight: 700, color: 'var(--text-primary)' }}>{money(c.amount_at_stake)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {orgsEnabled && !activeOrg && cases.length === 0 && !loading && (
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)', marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <IconUsers size={14} /> Working with a team? Pick an active workspace on <a href="/orgs" onClick={e => { e.preventDefault(); navigate('/orgs') }}>Team Workspaces</a> to see shared cases.
              </p>
            )}
          </>
        )}
      </div>

      {selected && (
        <CaseDrawer
          key={selected.id}
          caseItem={selected}
          canWrite={canWrite}
          canDelete={isAdmin || selected.created_by === user?.id}
          assignable={assignable}
          personal={!activeOrg}
          onClose={() => setSelectedId(null)}
          onUpdated={(u) => { applyUpdated(u); load() }}
          onDeleted={() => { setSelectedId(null); load() }}
        />
      )}
    </section>
  )
}

function CaseDrawer({ caseItem, canWrite, canDelete, assignable, personal, onClose, onUpdated, onDeleted }) {
  const [events, setEvents] = useState([])
  const [loadingEvents, setLoadingEvents] = useState(true)
  const [notes, setNotes] = useState(caseItem.notes || '')
  const [reference, setReference] = useState(caseItem.reference || '')
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState(null)

  const loadEvents = useCallback(async () => {
    setLoadingEvents(true)
    try {
      const data = await call(`/cases/${caseItem.id}/events?limit=100`, undefined, 'Could not load activity.')
      setEvents(data.events || [])
    } catch (err) {
      setStatus({ type: 'error', message: err.message })
    } finally {
      setLoadingEvents(false)
    }
  }, [caseItem.id])

  useEffect(() => { loadEvents() }, [loadEvents])

  const patch = async (changes, successMessage) => {
    setBusy(true)
    setStatus(null)
    try {
      const updated = await call(`/cases/${caseItem.id}`, { method: 'PATCH', body: JSON.stringify(changes) }, 'Could not update the case.')
      onUpdated(updated)
      if (successMessage) setStatus({ type: 'success', message: successMessage })
      await loadEvents()
    } catch (err) {
      setStatus({ type: 'error', message: err.message })
    } finally {
      setBusy(false)
    }
  }

  const addComment = async (e) => {
    e.preventDefault()
    if (!comment.trim()) return
    setBusy(true)
    try {
      await call(`/cases/${caseItem.id}/comments`, { method: 'POST', body: JSON.stringify({ message: comment }) }, 'Could not add the comment.')
      setComment('')
      await loadEvents()
    } catch (err) {
      setStatus({ type: 'error', message: err.message })
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!window.confirm(`Delete case "${caseItem.title}"? The claim itself is kept.`)) return
    setBusy(true)
    try {
      await call(`/cases/${caseItem.id}`, { method: 'DELETE' }, 'Could not delete the case.')
      onDeleted()
    } catch (err) {
      setStatus({ type: 'error', message: err.message })
      setBusy(false)
    }
  }

  const describe = (e) => {
    const d = e.data || {}
    switch (e.event_type) {
      case 'created': return 'opened the case'
      case 'status_changed': return `moved ${STATUS_LABEL[d.from] || d.from || '—'} → ${STATUS_LABEL[d.to] || d.to}`
      case 'assigned': return d.to ? 'assigned the case' : 'cleared the assignee'
      case 'priority_changed': return `set priority ${PRIORITY_LABEL[d.to] || d.to}`
      case 'due_date_changed': return d.to ? `set due date ${new Date(d.to).toLocaleDateString()}` : 'cleared the due date'
      case 'notes_updated': return 'updated the notes'
      case 'comment': return 'commented'
      case 'outcome_recorded': return `recorded outcome: ${d.outcome}`
      default: return e.event_type
    }
  }

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(9,9,11,0.35)', zIndex: 60 }} aria-hidden="true" />
      <aside role="dialog" aria-modal="true" aria-label={`Case ${caseItem.title}`} style={{
        position: 'fixed', top: 0, right: 0, height: '100vh', width: 'min(560px, 100vw)', background: 'var(--bg-card)',
        borderLeft: '1px solid var(--border-secondary)', boxShadow: '-12px 0 32px rgba(0,0,0,0.12)', zIndex: 61, overflowY: 'auto', padding: '1.5rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.75rem', marginBottom: '1rem' }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap', marginBottom: '0.375rem' }}>
              <span className={`badge ${STATUS_BADGE[caseItem.status]}`} style={{ fontSize: '0.6875rem' }}>{STATUS_LABEL[caseItem.status]}</span>
              <span className={`badge ${PRIORITY_BADGE[caseItem.priority]}`} style={{ fontSize: '0.6875rem' }}>{PRIORITY_LABEL[caseItem.priority]}</span>
              <span style={{ fontSize: '0.75rem', color: TONE_COLOR[dueTone(caseItem)], fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}><IconClock size={12} /> {dueLabel(caseItem)}</span>
            </div>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--text-primary)', margin: 0, lineHeight: 1.3 }}>{caseItem.title}</h2>
            {caseItem.claim?.description_preview && <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', margin: '0.375rem 0 0', lineHeight: 1.5 }}>{caseItem.claim.description_preview}</p>}
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose} aria-label="Close" style={{ padding: '0.375rem' }}><IconX size={18} /></button>
        </div>

        {status && <div style={{ marginBottom: '0.875rem' }}><Notice status={status} /></div>}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
          <div>
            <label style={labelStyle}>Status</label>
            <select className="input" value={caseItem.status} disabled={!canWrite || busy} onChange={e => patch({ status: e.target.value }, `Status set to ${STATUS_LABEL[e.target.value]}.`)}>
              {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Priority</label>
            <select className="input" value={caseItem.priority} disabled={!canWrite || busy} onChange={e => patch({ priority: e.target.value })}>
              {PRIORITIES.map(p => <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Assignee</label>
            {personal ? (
              <div className="input" style={{ background: 'var(--bg-secondary)', color: 'var(--text-tertiary)' }}>You</div>
            ) : (
              <select className="input" value={caseItem.assignee_id || ''} disabled={!canWrite || busy}
                onChange={e => patch(e.target.value ? { assignee_id: e.target.value } : { clear_assignee: true })}>
                <option value="">Unassigned</option>
                {assignable.map(m => <option key={m.user_id} value={m.user_id}>{m.email}</option>)}
              </select>
            )}
          </div>
          <div>
            <label style={labelStyle}>Due date</label>
            <input type="date" className="input" value={caseItem.due_date || ''} disabled={!canWrite || busy}
              onChange={e => patch(e.target.value ? { due_date: e.target.value } : { clear_due_date: true })} />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1rem', fontSize: '0.8125rem' }}>
          <div className="card-zinc" style={{ padding: '0.75rem' }}>
            <p style={{ ...labelStyle, marginBottom: '0.125rem' }}>At stake</p>
            <strong style={{ color: 'var(--text-primary)' }}>{money(caseItem.amount_at_stake)}</strong>
          </div>
          <div className="card-zinc" style={{ padding: '0.75rem' }}>
            <p style={{ ...labelStyle, marginBottom: '0.125rem' }}>Claim</p>
            <span style={{ color: 'var(--text-secondary)' }}>
              {caseItem.claim ? `${caseItem.claim.route_decision || ''}${caseItem.claim.success_score_band ? ` · strength ${caseItem.claim.success_score_band}` : ''}` : '—'}
              {caseItem.claim?.appeal_deadline && <><br />Appeal deadline {new Date(caseItem.claim.appeal_deadline).toLocaleDateString()}</>}
            </span>
          </div>
        </div>

        {canWrite && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.25rem' }}>
            <div>
              <label style={labelStyle} htmlFor="case-ref">Reference</label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input id="case-ref" className="input" value={reference} onChange={e => setReference(e.target.value)} maxLength={60} placeholder="Internal case number (no PHI)" />
                <button type="button" className="btn btn-outline" disabled={busy || reference === (caseItem.reference || '')} onClick={() => patch({ reference }, 'Reference saved.')}>Save</button>
              </div>
            </div>
            <div>
              <label style={labelStyle} htmlFor="case-notes">Notes <span style={{ fontWeight: 400 }}>— scrubbed for PHI before saving</span></label>
              <textarea id="case-notes" className="input" value={notes} onChange={e => setNotes(e.target.value)} maxLength={4000} style={{ minHeight: '90px' }} />
              <button type="button" className="btn btn-outline" style={{ marginTop: '0.5rem' }} disabled={busy || notes === (caseItem.notes || '')} onClick={() => patch({ notes }, 'Notes saved.')}>Save notes</button>
            </div>
          </div>
        )}
        {!canWrite && caseItem.notes && (
          <div style={{ marginBottom: '1.25rem' }}>
            <p style={labelStyle}>Notes</p>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>{caseItem.notes}</p>
          </div>
        )}

        <h3 style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.625rem' }}>Activity</h3>
        {canWrite && (
          <form onSubmit={addComment} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <input className="input" value={comment} onChange={e => setComment(e.target.value)} placeholder="Add a comment (PHI is scrubbed)" maxLength={4000} />
            <button type="submit" className="btn btn-red" disabled={busy || !comment.trim()}>Post</button>
          </form>
        )}
        {loadingEvents ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '1rem' }}><span className="spinner" /></div>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
            {events.map(e => (
              <li key={e.id} style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.5, borderLeft: `2px solid ${e.event_type === 'comment' ? 'var(--accent)' : 'var(--border-secondary)'}`, paddingLeft: '0.75rem' }}>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>
                  {e.created_at ? new Date(e.created_at).toLocaleString() : ''} · <strong style={{ color: 'var(--text-primary)' }}>{e.actor_email || 'system'}</strong> {describe(e)}
                </div>
                {e.message && <div style={{ color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>{e.message}</div>}
              </li>
            ))}
            {events.length === 0 && <li style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>No activity yet.</li>}
          </ul>
        )}

        {canDelete && (
          <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border-secondary)' }}>
            <button type="button" className="btn btn-ghost" style={{ color: 'var(--danger)', fontSize: '0.8125rem' }} onClick={remove} disabled={busy}><IconTrash size={14} /> Delete case</button>
          </div>
        )}
      </aside>
    </>
  )
}
