/** Case-management helpers shared by the Cases page and the Dashboard. Pure. */

export const OPEN_STATUSES = ['new', 'in_review', 'appeal_filed', 'awaiting_decision']
export const CLOSED_STATUSES = ['won', 'partial', 'lost', 'withdrawn']
export const STATUSES = [...OPEN_STATUSES, ...CLOSED_STATUSES]

export const STATUS_LABEL = {
  new: 'New', in_review: 'In review', appeal_filed: 'Appeal filed', awaiting_decision: 'Awaiting decision',
  won: 'Won', partial: 'Partial win', lost: 'Lost', withdrawn: 'Withdrawn',
}
export const STATUS_BADGE = {
  new: 'badge-info', in_review: 'badge-info', appeal_filed: 'badge-purple', awaiting_decision: 'badge-warning',
  won: 'badge-success', partial: 'badge-success', lost: 'badge-danger', withdrawn: 'badge-zinc',
}
export const PRIORITIES = ['low', 'normal', 'high', 'urgent']
export const PRIORITY_LABEL = { low: 'Low', normal: 'Normal', high: 'High', urgent: 'Urgent' }
export const PRIORITY_BADGE = { low: 'badge-zinc', normal: 'badge-zinc', high: 'badge-warning', urgent: 'badge-danger' }

export function money(value) {
  if (value == null || value === '') return '—'
  const n = Number(value)
  if (Number.isNaN(n)) return '—'
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

export function dueLabel(c) {
  if (!c?.due_date) return 'No due date'
  const formatted = new Date(c.due_date).toLocaleDateString()
  if (!c.is_open) return `Due ${formatted}`
  const d = c.days_to_due
  if (d == null) return `Due ${formatted}`
  if (d < 0) return `Overdue by ${-d}d`
  if (d === 0) return 'Due today'
  if (d <= 7) return `Due in ${d}d`
  return `Due ${formatted}`
}

export function dueTone(c) {
  if (!c?.is_open || c.days_to_due == null) return 'muted'
  if (c.days_to_due < 0) return 'danger'
  if (c.days_to_due <= 7) return 'warning'
  return 'muted'
}

/**
 * Client-side filtering of an already-scoped case list.
 * assignee: 'all' | 'me' | 'unassigned' | <user_id>
 */
export function filterCases(cases, { status = 'all', assignee = 'all', query = '', includeClosed = true, me = null } = {}) {
  const q = query.trim().toLowerCase()
  return (cases || []).filter(c => {
    if (!includeClosed && !OPEN_STATUSES.includes(c.status)) return false
    if (status === 'open' && !OPEN_STATUSES.includes(c.status)) return false
    if (status !== 'all' && status !== 'open' && c.status !== status) return false
    if (assignee === 'me' && c.assignee_id !== me) return false
    if (assignee === 'unassigned' && c.assignee_id) return false
    if (!['all', 'me', 'unassigned'].includes(assignee) && c.assignee_id !== assignee) return false
    if (q) {
      const hay = `${c.title || ''} ${c.reference || ''} ${c.assignee_email || ''} ${c.claim?.description_preview || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
}
