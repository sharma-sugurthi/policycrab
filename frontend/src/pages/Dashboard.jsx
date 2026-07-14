import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import { jsPDF } from 'jspdf'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

// ── CSV Export ──────────────────────────────────────────────────
function exportCsv(claims) {
  const headers = [
    'Date', 'Status', 'Claim Description', 'CPT Code', 'Network Status',
    'Billed Amount', 'Patient Responsibility', 'Appeal Deadline', 'Days Remaining'
  ]
  const rows = claims.map(c => [
    new Date(c.created_at).toLocaleDateString(),
    c.route_decision || '',
    `"${(c.claim_description || '').replace(/"/g, '""')}"`,
    c.cost_breakdown?.cpt_code || '',
    c.cost_breakdown?.network_status || '',
    c.cost_breakdown?.billed_amount != null ? `$${c.cost_breakdown.billed_amount.toFixed(2)}` : '',
    c.cost_breakdown?.total_patient_responsibility != null
      ? `$${Number(c.cost_breakdown.total_patient_responsibility).toFixed(2)}` : '',
    c.appeal_output?.appeal_deadline
      ? new Date(c.appeal_output.appeal_deadline).toLocaleDateString() : '',
    c.appeal_output?.days_remaining != null ? c.appeal_output.days_remaining : '',
  ])
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `policycrab_claims_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
}

// ── PDF Export ──────────────────────────────────────────────────
function exportPdf(claims, policyProfile) {
  const doc = new jsPDF({ unit: 'pt', format: 'letter' })
  const W = doc.internal.pageSize.getWidth()
  const margin = 48
  const colW = W - margin * 2

  const addPage = () => doc.addPage()
  const heading = (text, y) => {
    doc.setFontSize(11).setFont(undefined, 'bold').setTextColor(220, 38, 38)
    doc.text(text, margin, y)
    doc.setTextColor(0, 0, 0)
    return y + 16
  }
  const body = (text, y, indent = 0) => {
    doc.setFontSize(9).setFont(undefined, 'normal').setTextColor(60, 60, 60)
    const lines = doc.splitTextToSize(text, colW - indent)
    doc.text(lines, margin + indent, y)
    return y + lines.length * 12
  }
  const rule = (y) => {
    doc.setDrawColor(228, 228, 231).setLineWidth(0.5)
    doc.line(margin, y, W - margin, y)
    return y + 10
  }

  // ── Cover page ────────────────────────────────────────────────
  doc.setFontSize(22).setFont(undefined, 'bold').setTextColor(220, 38, 38)
  doc.text('PolicyCrab', margin, 80)
  doc.setFontSize(14).setFont(undefined, 'normal').setTextColor(60, 60, 60)
  doc.text('Claim History Report', margin, 102)
  doc.setFontSize(9).setTextColor(150, 150, 150)
  doc.text(`Generated: ${new Date().toLocaleString()}`, margin, 118)

  let y = 150
  y = rule(y)
  if (policyProfile) {
    y = heading('Loaded Policy', y)
    y = body(`Plan: ${policyProfile.plan_name || 'N/A'}`, y)
    y = body(`Carrier: ${policyProfile.carrier_name || 'N/A'}`, y)
    y = body(`Type: ${policyProfile.plan_type || 'N/A'} | State: ${policyProfile.state || 'N/A'}`, y)
    y = body(`Deductible (Individual): $${policyProfile.in_network_deductible_individual?.toLocaleString() || 'N/A'}`, y)
    y = body(`OOP Max (Individual): $${policyProfile.in_network_oop_max_individual?.toLocaleString() || 'N/A'}`, y)
    y += 8
    y = rule(y)
  }
  y = heading(`Claims Summary (${claims.length} total)`, y)
  y = body(`${claims.filter(c => c.route_decision === 'denied').length} denied · ${claims.filter(c => c.route_decision !== 'denied').length} approved`, y)
  y += 16

  // ── Claim pages ───────────────────────────────────────────────
  claims.forEach((c, i) => {
    addPage()
    y = 56
    doc.setFontSize(12).setFont(undefined, 'bold').setTextColor(220, 38, 38)
    doc.text(`Claim ${i + 1} of ${claims.length}`, margin, y)
    y += 20

    const cb = c.cost_breakdown || {}
    const ao = c.appeal_output || {}
    const status = c.route_decision === 'denied' ? 'DENIED' : 'APPROVED'

    y = rule(y)
    y = heading('Overview', y)
    y = body(`Date: ${new Date(c.created_at).toLocaleDateString()}`, y)
    y = body(`Status: ${status}`, y)
    if (cb.cpt_code) y = body(`CPT: ${cb.cpt_code}${cb.cpt_description ? ' — ' + cb.cpt_description : ''}`, y)
    if (cb.network_status) y = body(`Network: ${cb.network_status}`, y)
    y += 8

    y = rule(y)
    y = heading('Claim Description', y)
    y = body(c.claim_description || 'N/A', y, 8)
    y += 8

    y = rule(y)
    y = heading('Cost Breakdown', y)
    if (cb.billed_amount != null) y = body(`Billed Amount: $${Number(cb.billed_amount).toLocaleString()}`, y)
    if (cb.deductible_applied != null) y = body(`Deductible Applied: $${Number(cb.deductible_applied).toLocaleString()}`, y)
    if (cb.coinsurance_amount != null) y = body(`Coinsurance: $${Number(cb.coinsurance_amount).toLocaleString()}`, y)
    if (cb.copay_amount != null) y = body(`Copay: $${Number(cb.copay_amount).toLocaleString()}`, y)
    if (cb.total_patient_responsibility != null)
      y = body(`Patient Responsibility: $${Number(cb.total_patient_responsibility).toLocaleString()}`, y)
    y += 8

    if (ao.appeal_deadline) {
      y = rule(y)
      y = heading('Appeal Information', y)
      y = body(`Framework: ${ao.appeal_framework || 'N/A'}`, y)
      y = body(`Deadline: ${new Date(ao.appeal_deadline).toLocaleDateString()} (${ao.days_remaining ?? 'N/A'} days remaining)`, y)
      if (ao.denial_reason) y = body(`Denial Reason: ${ao.denial_reason}`, y)
    }
  })

  // ── Footer on all pages ───────────────────────────────────────
  const pageCount = doc.getNumberOfPages()
  for (let p = 1; p <= pageCount; p++) {
    doc.setPage(p)
    doc.setFontSize(7).setFont(undefined, 'normal').setTextColor(180, 180, 180)
    doc.text(
      'PolicyCrab — Informational use only. Not legal or medical advice. Verify with your insurer.',
      margin, doc.internal.pageSize.getHeight() - 24
    )
    doc.text(`Page ${p} of ${pageCount}`, W - margin, doc.internal.pageSize.getHeight() - 24, { align: 'right' })
  }

  doc.save(`policycrab_report_${new Date().toISOString().slice(0,10)}.pdf`)
}

// ── Policy Compare Table ────────────────────────────────────────────
const COMPARE_ROWS = [
  { label: 'Plan Type', key: (p) => p.plan_type || 'N/A', type: 'text' },
  { label: 'Metal Tier', key: (p) => p.metal_tier || 'N/A', type: 'text' },
  { label: 'State', key: (p) => p.state || 'N/A', type: 'text' },
  { label: 'Deductible (Individual)', key: (p) => p.in_network_deductible_individual, type: 'dollar', best: 'low' },
  { label: 'Deductible (Family)', key: (p) => p.in_network_deductible_family, type: 'dollar', best: 'low' },
  { label: 'OOP Max (Individual)', key: (p) => p.in_network_oop_max_individual, type: 'dollar', best: 'low' },
  { label: 'OOP Max (Family)', key: (p) => p.in_network_oop_max_family, type: 'dollar', best: 'low' },
  { label: 'Coinsurance (You Pay)', key: (p) => p.in_network_coinsurance, type: 'pct', best: 'low' },
  { label: 'PCP Copay', key: (p) => p.copay_schedule?.primary_care, type: 'dollar', best: 'low' },
  { label: 'Specialist Copay', key: (p) => p.copay_schedule?.specialist, type: 'dollar', best: 'low' },
  { label: 'Urgent Care Copay', key: (p) => p.copay_schedule?.urgent_care, type: 'dollar', best: 'low' },
  { label: 'ER Copay', key: (p) => p.copay_schedule?.emergency_room, type: 'dollar', best: 'low' },
  { label: 'Generic Rx Copay', key: (p) => p.copay_schedule?.generic_rx, type: 'dollar', best: 'low' },
  { label: 'OON Deductible', key: (p) => p.out_of_network_deductible_individual, type: 'dollar', best: 'low' },
  { label: 'OON Coinsurance', key: (p) => p.out_of_network_coinsurance, type: 'pct', best: 'low' },
  { label: 'HSA Eligible', key: (p) => p.is_hsa_eligible ? 'Yes ✅' : 'No', type: 'text' },
  { label: 'Requires PCP Referral', key: (p) => p.requires_pcp_referral ? 'Yes' : 'No', type: 'text' },
  { label: 'ACA Essential Benefits', key: (p) => p.covered_essential_health_benefits ? 'Yes' : 'No', type: 'text' },
]

function fmt(value, type) {
  if (value == null) return <span style={{ color: '#d1d5db' }}>N/A</span>
  if (type === 'dollar') return `$${Number(value).toLocaleString()}`
  if (type === 'pct') return `${Math.round(value * 100)}%`
  return String(value)
}

function PolicyCompareTable({ profiles, onClose }) {
  if (profiles.length < 2) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      style={{ marginTop: '2.5rem' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.125rem', fontWeight: 800, color: '#09090b' }}>Plan Comparison</h2>
          <p style={{ fontSize: '0.8125rem', color: '#71717a', marginTop: '0.25rem' }}>
            <span style={{ display: 'inline-block', width: '10px', height: '10px', background: '#dcfce7', border: '1px solid #86efac', borderRadius: '2px', marginRight: '6px' }} />
            Best value in each row highlighted green.
          </p>
        </div>
        <button className="btn btn-ghost" style={{ fontSize: '0.75rem' }} onClick={onClose}>✕ Close</button>
      </div>

      <div style={{ overflowX: 'auto', borderRadius: '1rem', border: '1px solid #e4e4e7', boxShadow: '0 4px 20px rgba(0,0,0,0.05)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: `${280 + profiles.length * 160}px` }}>
          <thead>
            <tr style={{ background: '#fafafa' }}>
              <th style={{ padding: '0.875rem 1rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 700, color: '#71717a', textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: '1px solid #e4e4e7', width: '200px' }}>Field</th>
              {profiles.map((p, i) => (
                <th key={i} style={{ padding: '0.875rem 1rem', textAlign: 'center', borderBottom: '1px solid #e4e4e7', minWidth: '160px' }}>
                  <div style={{ fontSize: '0.875rem', fontWeight: 800, color: '#09090b' }}>{p.plan_name || `Plan ${i + 1}`}</div>
                  <div style={{ fontSize: '0.7rem', color: '#71717a', marginTop: '2px' }}>{p.carrier_name}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COMPARE_ROWS.map((row, ri) => {
              const values = profiles.map(p => row.key(p))
              // Find best (lowest numeric) index for rows where we care
              let bestIdx = null
              if (row.best === 'low') {
                const nums = values.map(v => (v != null && !isNaN(Number(v)) ? Number(v) : Infinity))
                const min = Math.min(...nums)
                if (min !== Infinity) bestIdx = nums.indexOf(min)
              }

              return (
                <tr key={ri} style={{ borderBottom: '1px solid #f4f4f5', transition: 'background 0.15s' }}
                  onMouseEnter={e => e.currentTarget.style.background = '#fafafa'}
                  onMouseLeave={e => e.currentTarget.style.background = ''}
                >
                  <td style={{ padding: '0.625rem 1rem', fontSize: '0.8125rem', fontWeight: 600, color: '#3f3f46' }}>{row.label}</td>
                  {values.map((val, vi) => {
                    const isBest = bestIdx === vi
                    return (
                      <td key={vi} style={{
                        padding: '0.625rem 1rem', textAlign: 'center',
                        fontSize: '0.875rem', fontWeight: isBest ? 700 : 400,
                        color: isBest ? '#15803d' : '#09090b',
                        background: isBest ? '#dcfce7' : undefined,
                      }}>
                        {fmt(val, row.type)}
                        {isBest && <span style={{ fontSize: '0.65rem', display: 'block', color: '#16a34a', marginTop: '1px' }}>Best</span>}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}

export default function Dashboard({ policyProfile, onPolicySelected }) {
  const { session } = useAuth()
  const navigate = useNavigate()
  const [policies, setPolicies] = useState([])
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(true)
  const [compareIds, setCompareIds] = useState(new Set())

  useEffect(() => {
    async function fetchData() {
      try {
        const [polRes, claimRes] = await Promise.all([
          apiFetch('/history/policies'),
          apiFetch('/history/claims')
        ])

        if (polRes.ok) setPolicies(await polRes.json())
        if (claimRes.ok) setClaims(await claimRes.json())
      } catch (err) {
        console.error('Failed to load history', err)
      } finally {
        setLoading(false)
      }
    }

    if (session) fetchData()
  }, [session])

  const hasPolicy = Boolean(policyProfile) || policies.length > 0
  const hasClaim = claims.length > 0
  const activePolicy = policyProfile || policies[0]?.policy_profile

  const handleUsePolicyForClaim = (profile) => {
    if (profile) onPolicySelected?.(profile)
    navigate('/claim')
  }

  const toggleCompare = (id) => {
    setCompareIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) { next.delete(id) }
      else if (next.size < 3) { next.add(id) }
      return next
    })
  }

  const compareProfiles = policies
    .filter(p => compareIds.has(p.id))
    .map(p => p.policy_profile)
    .filter(Boolean)

  const onboardingSteps = [
    {
      title: 'Load your policy',
      status: hasPolicy ? 'Done' : 'Start here',
      body: hasPolicy
        ? `${activePolicy?.plan_name || 'A policy'} is ready for claim evaluation.`
        : 'Upload an SBC or policy PDF so the app can read deductibles, copays, coinsurance, and network rules.',
      action: hasPolicy ? 'Upload another policy' : 'Upload policy',
      onClick: () => navigate('/policy'),
      tone: hasPolicy ? 'success' : 'danger',
    },
    {
      title: 'Evaluate a claim',
      status: hasClaim ? 'Done' : hasPolicy ? 'Next' : 'Locked',
      body: hasPolicy
        ? 'Use the loaded policy and describe the bill or denial. Add the EOB allowed amount when you have it.'
        : 'Claim evaluation needs a policy first so the math uses the right plan terms.',
      action: hasPolicy ? 'Evaluate claim' : 'Upload policy first',
      onClick: () => hasPolicy ? handleUsePolicyForClaim(activePolicy) : navigate('/policy'),
      tone: hasClaim ? 'success' : hasPolicy ? 'danger' : 'zinc',
    },
    {
      title: 'Use the appeal output',
      status: hasClaim ? 'Available' : 'Later',
      body: hasClaim
        ? 'Denied claims can produce a formal appeal letter with deadline tracking and export actions.'
        : 'If a claim routes as denied, PolicyCrab drafts an appeal letter you can copy or download.',
      action: hasClaim ? 'Review claim history' : 'Start with a claim',
      onClick: () => hasClaim ? window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }) : (hasPolicy ? handleUsePolicyForClaim(activePolicy) : navigate('/policy')),
      tone: hasClaim ? 'success' : 'zinc',
    },
  ]

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}><span className="spinner" /></div>
  }

  return (
    <section className="section-white section-pad">
      <div className="main">
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }} style={{ marginBottom: '2rem' }}>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.55 }} className="section-title">
            My <span className="gradient-text">Dashboard</span>
          </motion.h1>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-subtitle">
            Start with your policy, evaluate a bill or denial, then use the appeal output when it applies.
          </motion.p>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }} className="dashboard-guide">
          <div className="dashboard-guide-header">
            <div>
              <p className="section-label" style={{ marginBottom: '0.5rem' }}><span className="line" /> Start Here</p>
              <h2>Claim workflow</h2>
            </div>
            <span className={`badge ${hasClaim ? 'badge-success' : hasPolicy ? 'badge-warning' : 'badge-danger'}`}>
              {hasClaim ? 'Claim evaluated' : hasPolicy ? 'Policy ready' : 'Policy needed'}
            </span>
          </div>

          <div className="dashboard-steps">
            {onboardingSteps.map((step, index) => (
              <div className="dashboard-step" key={step.title}>
                <div className="dashboard-step-top">
                  <span className="dashboard-step-number">{String(index + 1).padStart(2, '0')}</span>
                  <span className={`badge badge-${step.tone}`}>{step.status}</span>
                </div>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
                <button className={step.tone === 'danger' ? 'btn btn-red' : 'btn btn-ghost'} onClick={step.onClick}>
                  {step.action}
                </button>
              </div>
            ))}
          </div>
        </motion.div>

        <div className="grid-2" style={{ alignItems: 'start' }}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}>
            <div className="dashboard-section-heading">
              <h2>Saved Policies</h2>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                {compareIds.size >= 2 && (
                  <span style={{ fontSize: '0.7rem', color: '#71717a' }}>{compareIds.size} selected</span>
                )}
                <button
                  className="btn btn-ghost"
                  style={{ fontSize: '0.75rem' }}
                  disabled={policies.length < 2}
                  title={policies.length < 2 ? 'Save 2+ policies to compare' : 'Select 2-3 plans below to compare'}
                  onClick={() => {
                    if (compareIds.size >= 2) {
                      // already have selections — scroll to table
                      document.getElementById('compare-table')?.scrollIntoView({ behavior: 'smooth' })
                    } else {
                      // seed first two
                      setCompareIds(new Set(policies.slice(0, 2).map(p => p.id)))
                    }
                  }}
                >
                  ⚖ Compare
                </button>
                <button className="btn btn-red" onClick={() => navigate('/policy')}>New Policy</button>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {policies.length === 0 ? (
                policyProfile ? (
                  <div className="card dashboard-history-card">
                    <div className="dashboard-card-header">
                      <h3>{policyProfile.plan_name || 'Loaded Policy'}</h3>
                      <span>Current session</span>
                    </div>
                    <p>{policyProfile.carrier_name || 'Unknown carrier'} - {policyProfile.plan_type || 'Plan type unknown'}</p>
                    <div className="dashboard-badge-row">
                      <span className="badge badge-zinc">Ded: ${policyProfile.in_network_deductible_individual?.toLocaleString?.() || policyProfile.in_network_deductible_individual || 'n/a'}</span>
                      <span className="badge badge-zinc">OOP: ${policyProfile.in_network_oop_max_individual?.toLocaleString?.() || policyProfile.in_network_oop_max_individual || 'n/a'}</span>
                    </div>
                    <button className="btn btn-ghost" onClick={() => handleUsePolicyForClaim(policyProfile)}>Use for Claim</button>
                  </div>
                ) : (
                  <div className="dashboard-empty">
                    <h3>No saved policies yet</h3>
                    <p>Upload your Summary of Benefits and Coverage or policy PDF to unlock claim evaluation.</p>
                    <button className="btn btn-red" onClick={() => navigate('/policy')}>Upload Policy</button>
                  </div>
                )
              ) : (
                policies.map(p => (
                  <div key={p.id} className="card dashboard-history-card" style={compareIds.has(p.id) ? { border: '1.5px solid #dc2626', boxShadow: '0 0 0 3px #fecaca' } : {}}>
                    <div className="dashboard-card-header">
                      <h3>{p.policy_profile?.plan_name || 'Unknown Plan'}</h3>
                      <span>{new Date(p.created_at).toLocaleDateString()}</span>
                    </div>
                    <p>{p.policy_profile?.carrier_name || 'Unknown carrier'} - {p.policy_profile?.plan_type || 'Plan type unknown'}</p>
                    <div className="dashboard-badge-row">
                      <span className="badge badge-zinc">Ded: ${p.policy_profile?.in_network_deductible_individual?.toLocaleString?.() || p.policy_profile?.in_network_deductible_individual || 'n/a'}</span>
                      <span className="badge badge-zinc">OOP: ${p.policy_profile?.in_network_oop_max_individual?.toLocaleString?.() || p.policy_profile?.in_network_oop_max_individual || 'n/a'}</span>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.75rem' }}>
                      <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => handleUsePolicyForClaim(p.policy_profile)}>Use for Claim</button>
                      {policies.length >= 2 && (
                        <button
                          className={`btn ${compareIds.has(p.id) ? 'btn-red' : 'btn-ghost'}`}
                          style={{ fontSize: '0.75rem' }}
                          onClick={() => toggleCompare(p.id)}
                        >
                          {compareIds.has(p.id) ? '✓ Selected' : '+ Compare'}
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
            <div className="dashboard-section-heading">
              <h2>Claim History</h2>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  className="btn btn-ghost"
                  style={{ fontSize: '0.75rem' }}
                  disabled={claims.length === 0}
                  onClick={() => exportCsv(claims)}
                  title="Download all claims as CSV"
                >
                  ⬇ CSV
                </button>
                <button
                  className="btn btn-ghost"
                  style={{ fontSize: '0.75rem' }}
                  disabled={claims.length === 0}
                  onClick={() => exportPdf(claims, policyProfile)}
                  title="Download full claim report as PDF"
                >
                  ⬇ PDF Report
                </button>
                <button className="btn btn-red" onClick={() => hasPolicy ? handleUsePolicyForClaim(activePolicy) : navigate('/policy')}>New Claim</button>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {claims.length === 0 ? (
                <div className="dashboard-empty">
                  <h3>No claims evaluated yet</h3>
                  <p>{hasPolicy ? 'Use your loaded policy to evaluate a medical bill, EOB, or denial.' : 'Upload a policy first, then come back to evaluate a claim.'}</p>
                  <button className="btn btn-red" onClick={() => hasPolicy ? handleUsePolicyForClaim(activePolicy) : navigate('/policy')}>
                    {hasPolicy ? 'Evaluate Claim' : 'Upload Policy'}
                  </button>
                </div>
              ) : (
                claims.map(c => {
                  // Compute deadline urgency
                  let urgencyClass = '', urgencyLabel = '', daysLeft = null
                  if (c.appeal_output?.appeal_deadline) {
                    const dl = new Date(c.appeal_output.appeal_deadline)
                    const today = new Date()
                    today.setHours(0,0,0,0); dl.setHours(0,0,0,0)
                    daysLeft = Math.ceil((dl - today) / 86400000)
                    if (daysLeft <= 0) { urgencyClass = 'expired'; urgencyLabel = `⚫ Expired ${Math.abs(daysLeft)}d ago` }
                    else if (daysLeft <= 7) { urgencyClass = 'critical'; urgencyLabel = `🔴 ${daysLeft}d — File NOW` }
                    else if (daysLeft <= 30) { urgencyClass = 'urgent'; urgencyLabel = `🟠 ${daysLeft}d remaining` }
                    else if (daysLeft <= 90) { urgencyClass = 'moderate'; urgencyLabel = `🟡 ${daysLeft}d remaining` }
                    else { urgencyClass = 'standard'; urgencyLabel = `🟢 ${daysLeft}d remaining` }
                  }

                  return (
                    <div key={c.id} className="card dashboard-history-card">
                      <div className="dashboard-card-header">
                        <span className={`badge ${c.route_decision === 'denied' ? 'badge-danger' : 'badge-success'}`}>
                          {c.route_decision === 'denied' ? 'Denied' : 'Approved'}
                        </span>
                        <span>{new Date(c.created_at).toLocaleDateString()}</span>
                      </div>
                      <p className="dashboard-claim-description">&quot;{c.claim_description}&quot;</p>
                      <div className="dashboard-cost-row">
                        <span>Patient responsibility</span>
                        <strong>${c.cost_breakdown?.total_patient_responsibility?.toLocaleString?.() || c.cost_breakdown?.total_patient_responsibility || 0}</strong>
                      </div>
                      {c.appeal_output?.appeal_deadline && (
                        <>
                          <div className="dashboard-cost-row">
                            <span>Appeal deadline</span>
                            <strong>{new Date(c.appeal_output.appeal_deadline).toLocaleDateString()}</strong>
                          </div>
                          <div className={`deadline-urgency ${urgencyClass}`}>{urgencyLabel}</div>
                        </>
                      )}
                    </div>
                  )
                })
              )}
            </div>
          </motion.div>
        </div>

        {/* ── Policy Comparison Table ─────────────────────────────── */}
        <div id="compare-table">
          {compareProfiles.length >= 2 && (
            <PolicyCompareTable
              profiles={compareProfiles}
              onClose={() => setCompareIds(new Set())}
            />
          )}
        </div>
      </div>
    </section>
  )
}
