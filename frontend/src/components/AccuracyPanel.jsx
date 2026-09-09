/**
 * Accuracy Core UI widgets — surface the deterministic QA the backend now runs
 * on every appeal so users treat its output as signal, not noise.
 *
 *  - QualityGateCard          : missing-information checklist (WARN / BLOCK)
 *  - CitationGroundingBadge   : how many cited statutes / policy quotes were verified
 *  - SuccessScoreBadge        : deterministic, factor-based success estimate
 *  - LetterWithVerifyMarkers  : renders the letter and highlights [VERIFY: ...] markers
 *
 * Pure presentational components. Inline styles + existing CSS variables/classes.
 */

import { useState } from 'react'

const VERIFY_MARKER_RE = /(\[VERIFY:[^\]]*\])/g
const PLACEHOLDER_RE = /(\[[A-Z][A-Z ]{2,40}\])/g

const SEVERITY_BADGE = {
  CRITICAL: 'badge-danger',
  IMPORTANT: 'badge-warning',
  NICE_TO_HAVE: 'badge-zinc',
}

const SEVERITY_ORDER = { CRITICAL: 0, IMPORTANT: 1, NICE_TO_HAVE: 2 }

export function QualityGateCard({ gate }) {
  const [open, setOpen] = useState(gate?.status === 'BLOCK')
  if (!gate || gate.status === 'PASS') return null
  const items = [...(gate.missing_information_checklist || [])]
    .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9))
  if (items.length === 0) return null

  const blocked = gate.status === 'BLOCK'
  const criticalCount = (gate.critical_missing || []).length

  return (
    <div
      role="region"
      aria-label="Missing information checklist"
      style={{
        border: `1px solid ${blocked ? 'var(--danger-border)' : 'var(--warning-border)'}`,
        background: blocked ? 'var(--danger-bg)' : 'var(--warning-bg)',
        borderRadius: 'var(--radius-lg)',
        padding: '1rem 1.25rem',
        marginBottom: '1.25rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', flexWrap: 'wrap' }}>
          <span className={`badge ${blocked ? 'badge-danger' : 'badge-warning'}`}>
            {blocked ? 'Drafting paused' : 'Data gaps found'}
          </span>
          <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            {blocked
              ? `${criticalCount} critical fact${criticalCount === 1 ? '' : 's'} missing - add them and re-run`
              : `${items.length} item${items.length === 1 ? '' : 's'} to confirm before you send this letter`}
          </span>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ padding: '0.25rem 0.625rem', fontSize: '0.75rem' }}
          onClick={() => setOpen(o => !o)}
          aria-expanded={open}
        >
          {open ? 'Hide checklist' : 'Show checklist'}
        </button>
      </div>

      {!blocked && (
        <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.5rem', lineHeight: 1.5 }}>
          The letter was drafted with bracketed placeholders (for example <code>[DENIAL DATE]</code>) instead of guessed
          values. Fill them in from the documents below before submission.
        </p>
      )}

      {open && (
        <ol style={{ margin: '0.875rem 0 0', paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
          {items.map((item) => (
            <li key={item.field} style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', lineHeight: 1.5 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                <strong style={{ textTransform: 'capitalize' }}>{String(item.field || '').replace(/_/g, ' ')}</strong>
                <span className={`badge ${SEVERITY_BADGE[item.severity] || 'badge-zinc'}`} style={{ fontSize: '0.625rem' }}>
                  {item.severity}
                </span>
                {item.confidence && (
                  <span className="badge badge-zinc" style={{ fontSize: '0.625rem' }}>reader confidence: {item.confidence}</span>
                )}
              </div>
              <div style={{ color: 'var(--text-secondary)' }}>{item.why_it_matters}</div>
              <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>Where to find it: {item.where_to_find_it}</div>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export function CitationGroundingBadge({ verification, compact = false }) {
  if (!verification || !verification.status || verification.status === 'SKIPPED') return null
  const { status, verified_count = 0, total_count = 0, grounding_score = 0, unverified = [], unverified_policy_clauses = [] } = verification
  const cls = status === 'VERIFIED' ? 'badge-success'
    : status === 'PARTIAL' ? 'badge-warning'
      : status === 'FAILED' ? 'badge-danger'
        : 'badge-zinc'
  const label = status === 'N/A'
    ? 'No legal citations (billing correction)'
    : `Citations verified: ${verified_count}/${total_count} (${Math.round(grounding_score * 100)}%)`
  const problems = [
    ...unverified.map(u => `${u.statute} - ${u.reason.replace(/_/g, ' ').toLowerCase()}`),
    ...unverified_policy_clauses.map(c => `Page ${c.page_number ?? '?'} quote - ${c.reason.replace(/_/g, ' ').toLowerCase()}${c.best_match_page != null ? ` (closest match: page ${c.best_match_page})` : ''}`),
  ]
  const title = problems.length
    ? `Needs review:\n${problems.join('\n')}`
    : 'Every cited statute and quoted policy clause was matched against verified sources.'

  return (
    <span className={`badge ${cls}`} title={title} style={compact ? { fontSize: '0.6875rem' } : undefined}>
      {label}{problems.length ? ` - ${problems.length} to review` : ''}
    </span>
  )
}

export function SuccessScoreBadge({ appeal }) {
  const [open, setOpen] = useState(false)
  if (!appeal || appeal.success_score == null) return null
  const band = appeal.success_score_band || 'LOW'
  const cls = band === 'HIGH' ? 'badge-success' : band === 'MEDIUM' ? 'badge-info' : band === 'LOW' ? 'badge-warning' : 'badge-danger'
  const factors = appeal.success_score_factors || []
  return (
    <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', gap: '0.375rem' }}>
      <button
        type="button"
        className={`badge ${cls}`}
        onClick={() => setOpen(o => !o)}
        style={{ cursor: 'pointer', border: '1px solid transparent' }}
        aria-expanded={open}
        title="Deterministic estimate built from case facts. Click for the factor breakdown."
      >
        Case strength: {band} ({Math.round(appeal.success_score * 100)}%)
      </button>
      {open && (
        <div
          style={{
            position: 'absolute', top: '100%', right: 0, zIndex: 40, marginTop: '0.375rem', minWidth: '320px', maxWidth: '420px',
            background: 'var(--bg-card)', border: '1px solid var(--border-secondary)', borderRadius: '0.75rem',
            padding: '0.75rem 0.875rem', boxShadow: '0 10px 25px -5px rgba(0,0,0,0.12)', textAlign: 'left',
          }}
        >
          <p style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.5rem' }}>
            How this was scored
          </p>
          <ul style={{ margin: 0, paddingLeft: '1rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            {factors.map((f, i) => (
              <li key={i} style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                <strong style={{ color: f.delta >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                  {f.delta >= 0 ? '+' : ''}{Math.round(f.delta * 100)}
                </strong>{' '}{f.note}
              </li>
            ))}
          </ul>
          <p style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)', marginTop: '0.5rem', lineHeight: 1.4 }}>
            Heuristic v1 - not yet calibrated against recorded outcomes. Record your appeal results on the Dashboard to
            improve it. The AI model&apos;s own estimate was {Math.round((appeal.estimated_success_probability ?? 0) * 100)}%.
          </p>
        </div>
      )}
    </span>
  )
}

export function LetterWithVerifyMarkers({ text }) {
  if (!text) return null
  const parts = String(text).split(VERIFY_MARKER_RE)
  return (
    <>
      {parts.map((part, i) => {
        if (VERIFY_MARKER_RE.test(part)) {
          VERIFY_MARKER_RE.lastIndex = 0
          return (
            <mark
              key={i}
              title="This citation could not be matched to PolicyCrab's verified legal sources. Confirm it before sending."
              style={{ background: 'var(--warning-bg)', color: 'var(--warning)', border: '1px solid var(--warning-border)', borderRadius: '0.25rem', padding: '0 0.25rem', fontFamily: 'inherit', fontWeight: 700 }}
            >
              {part}
            </mark>
          )
        }
        VERIFY_MARKER_RE.lastIndex = 0
        // Highlight bracketed placeholders like [DENIAL DATE] emitted for known data gaps.
        const sub = part.split(PLACEHOLDER_RE)
        return sub.map((s, j) => (
          PLACEHOLDER_RE.test(s)
            ? (PLACEHOLDER_RE.lastIndex = 0, <mark key={`${i}-${j}`} title="Fill this in before sending." style={{ background: 'var(--info-bg)', color: 'var(--info)', border: '1px dashed var(--info-border)', borderRadius: '0.25rem', padding: '0 0.25rem', fontFamily: 'inherit' }}>{s}</mark>)
            : (PLACEHOLDER_RE.lastIndex = 0, <span key={`${i}-${j}`}>{s}</span>)
        ))
      })}
    </>
  )
}

export function AccuracySummaryRow({ appeal }) {
  if (!appeal) return null
  const hasAny = appeal.citation_verification || appeal.success_score != null
  if (!hasAny) return null
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
      <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Accuracy check
      </span>
      <CitationGroundingBadge verification={appeal.citation_verification} />
      <SuccessScoreBadge appeal={appeal} />
      {appeal.citation_verification?.flags?.includes('ALLOWLIST_NEEDS_HUMAN_VERIFICATION') && (
        <span className="badge badge-zinc" style={{ fontSize: '0.6875rem' }} title="The statute reference list has not yet been human-verified by the PolicyCrab team.">
          reference list pending review
        </span>
      )}
    </div>
  )
}
