import { describe, expect, it } from 'vitest'
import { dueLabel, dueTone, filterCases, money } from './cases'

const cases = [
  { id: 'a', title: 'MRI denial', status: 'new', assignee_id: 'u1', assignee_email: 'ann@x.test', is_open: true, days_to_due: -3, due_date: '2026-09-10' },
  { id: 'b', title: 'ER balance bill', status: 'appeal_filed', assignee_id: null, is_open: true, days_to_due: 5, due_date: '2026-09-21' },
  { id: 'c', title: 'Old win', status: 'won', assignee_id: 'u2', is_open: false, days_to_due: -40, due_date: '2026-08-01', reference: 'CASE-7' },
]

describe('cases helpers', () => {
  it('formats money and due labels', () => {
    expect(money(1800.5)).toBe('$1,801')
    expect(money(null)).toBe('—')
    expect(dueLabel(cases[0])).toBe('Overdue by 3d')
    expect(dueLabel(cases[1])).toBe('Due in 5d')
    expect(dueLabel({ ...cases[1], days_to_due: 0 })).toBe('Due today')
    expect(dueLabel({})).toBe('No due date')
    expect(dueTone(cases[0])).toBe('danger')
    expect(dueTone(cases[1])).toBe('warning')
    expect(dueTone(cases[2])).toBe('muted')     // closed cases are never "overdue"
  })

  it('filters by status, assignee and text', () => {
    expect(filterCases(cases, { status: 'open' }).map(c => c.id)).toEqual(['a', 'b'])
    expect(filterCases(cases, { includeClosed: false }).map(c => c.id)).toEqual(['a', 'b'])
    expect(filterCases(cases, { status: 'won' }).map(c => c.id)).toEqual(['c'])
    expect(filterCases(cases, { assignee: 'me', me: 'u1' }).map(c => c.id)).toEqual(['a'])
    expect(filterCases(cases, { assignee: 'unassigned' }).map(c => c.id)).toEqual(['b'])
    expect(filterCases(cases, { assignee: 'u2' }).map(c => c.id)).toEqual(['c'])
    expect(filterCases(cases, { query: 'case-7' }).map(c => c.id)).toEqual(['c'])
    expect(filterCases(cases, { query: 'ann@' }).map(c => c.id)).toEqual(['a'])
    expect(filterCases(undefined)).toEqual([])
  })
})
