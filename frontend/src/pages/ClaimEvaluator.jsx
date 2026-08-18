import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import AILogViewer from '../components/AILogViewer'
import { apiFetch, formatApiError, readApiResponse } from '../lib/api'
import { useTasks } from '../contexts/TaskContext'
import { jsPDF } from 'jspdf'
import { CPT_CODES } from '../data/cpt_codes'
import { IconSearch, IconFileText, IconUpload, IconCheckCircle, IconX, IconChevronDown, IconChevronUp, IconAlertTriangle, IconActivity, IconBriefcase, IconZap, IconMapPin, IconStethoscope, IconShield, IconCpu, IconServer, IconScale, IconEdit, IconDownload, IconCopy, IconMap, IconWand, IconArrowRight } from '../components/Icons'

// ── CPT Lookup widget ─────────────────────────────────────────────
function CptLookup({ onSelect, disabled }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [results, setResults] = useState([])
  const ref = useRef(null)

  useEffect(() => {
    const q = query.trim().toLowerCase()
    if (q.length < 2) { setResults([]); setOpen(false); return }
    const filtered = CPT_CODES.filter(
      ([code, desc]) => code.startsWith(q) || desc.toLowerCase().includes(q)
    ).slice(0, 12)
    setResults(filtered)
    setOpen(filtered.length > 0)
  }, [query])

  // Close on outside click
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSelect = ([code, desc, cat]) => {
    setQuery(`${code} — ${desc}`)
    setOpen(false)
    onSelect({ code, desc, cat })
  }

  return (
    <div ref={ref} style={{ position: 'relative', marginBottom: '1rem' }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
        <IconSearch size={16} style={{ color: 'var(--text-tertiary)' }} />
        CPT Code Lookup
        <span style={{ fontWeight: 500, color: 'var(--text-tertiary)' }}>— search by code or procedure name</span>
      </label>
      <input
        className="input"
        value={query}
        onChange={e => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder="e.g. 99213 or 'knee replacement'"
        disabled={disabled}
        autoComplete="off"
      />
      {open && (
        <ul style={{
          position: 'absolute', zIndex: 200, top: 'calc(100% + 4px)', left: 0, right: 0,
          background: 'var(--bg-card)', border: '1px solid var(--border-primary)', borderRadius: '0.75rem',
          boxShadow: 'var(--shadow-md)', maxHeight: '260px', overflowY: 'auto',
          listStyle: 'none', padding: '0.375rem', margin: 0,
        }}>
          {results.map(([code, desc, cat]) => (
            <li
              key={code}
              onMouseDown={() => handleSelect([code, desc, cat])}
              style={{
                padding: '0.625rem 0.75rem', borderRadius: '0.5rem', cursor: 'pointer',
                display: 'flex', gap: '0.75rem', alignItems: 'flex-start',
                transition: 'background var(--transition-fast)'
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-secondary)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: '0.875rem', color: 'var(--accent)', flexShrink: 0, minWidth: '52px' }}>{code}</span>
              <span style={{ flex: 1 }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', fontWeight: 500 }}>{desc}</span>
                <span style={{ display: 'block', fontSize: '0.65rem', color: 'var(--text-tertiary)', marginTop: '0.1rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{cat}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const PROGRESS_STEPS = [
  { label: 'Normalizing claim', icon: <IconFileText size={16} /> },
  { label: 'Running cost engine', icon: <IconActivity size={16} /> },
  { label: 'Routing framework', icon: <IconBriefcase size={16} /> },
  { label: 'Drafting appeal', icon: <IconEdit size={16} /> },
]

const DENIAL_REASONS = [
  ['', '— Select denial reason —'],
  ['MEDICAL_NECESSITY', 'Medical Necessity (CO-50)'],
  ['PRIOR_AUTH_MISSING', 'Prior Auth Missing (PR-243)'],
  ['TIMELY_FILING', 'Timely Filing (CO-29)'],
  ['NOT_COVERED', 'Not Covered (Exclusion)'],
  ['OUT_OF_NETWORK_DENIAL', 'Out-of-Network Denial'],
  ['NSA_BALANCE_BILLING', 'Balance Billing (NSA)'],
  ['OTHER', 'Other'],
]

const APPEAL_LEVELS = [
  { title: 'Internal Appeal', desc: 'First-level appeal directly to your insurer. Deadline varies by framework.' },
  { title: 'External Review (IRO)', desc: 'Independent Review Organization reviews the denial. Required for ACA/state-regulated plans.' },
  { title: 'State DOI Complaint', desc: 'File a formal complaint with your State Department of Insurance.' },
  { title: 'Federal Court / ERISA Lawsuit', desc: 'Last resort for ERISA plans after exhausting administrative remedies.' },
]

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

export default function ClaimEvaluator({ policyProfile, policySession, onResult }) {
  const navigate = useNavigate()
  const { addTask, getLatestTask } = useTasks()
  const [claimText, setClaimText] = useState('')
  const [allowedAmount, setAllowedAmount] = useState('')
  const [loading, setLoading] = useState(false)
  const [progressStep, setProgressStep] = useState(0)
  const progressTimer = useRef(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [providerSearch, setProviderSearch] = useState({ city: '', state: '', last_name: '', taxonomy_description: '', is_facility: false })
  const [providerResults, setProviderResults] = useState([])
  const [providerLoading, setProviderLoading] = useState(false)
  const [networkChecks, setNetworkChecks] = useState({})
  const [providerError, setProviderError] = useState(null)
  const [letterActionStatus, setLetterActionStatus] = useState('')
  const [guidedOpen, setGuidedOpen] = useState(false)
  const [guided, setGuided] = useState({ date_of_service: '', provider_name: '', denial_date: '', denial_reason: '', carc_code: '' })
  const [eobFile, setEobFile] = useState(null)
  const [eobLoading, setEobLoading] = useState(false)
  const [eobResult, setEobResult] = useState(null)
  const [eobError, setEobError] = useState(null)
  const [escalatedLevel, setEscalatedLevel] = useState(null)   // 2 or 3
  const [escalatedResult, setEscalatedResult] = useState(null)
  const [escalatedLoading, setEscalatedLoading] = useState(false)
  const [escalatedError, setEscalatedError] = useState(null)
  const [networkStatus, setNetworkStatus] = useState('')

  // Restore completed claim evaluation if user navigated away
  useEffect(() => {
    const task = getLatestTask('claim_eval')
    if (task?.status === 'done' && task.result && !result) {
      const { data } = task.result
      if (data?.success && data.cost_breakdown) {
        setResult(data)
        onResult(data.cost_breakdown)
      }
    } else if (task?.status === 'running' && !loading) {
      setLoading(true)
      const poll = setInterval(() => {
        const t = getLatestTask('claim_eval')
        if (!t || t.status !== 'running') {
          clearInterval(poll)
          setLoading(false)
          if (t?.status === 'done' && t.result) {
            setResult(t.result.data)
            onResult(t.result.data.cost_breakdown)
          } else if (t?.status === 'error') {
            setError(t.error || 'Evaluation failed.')
          }
        }
      }, 800)
      return () => clearInterval(poll)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    let raw = null
    try {
      raw = sessionStorage.getItem('policycrab_eob_prefill')
      if (raw) sessionStorage.removeItem('policycrab_eob_prefill')
    } catch {}
    if (!raw) return

    try {
      const eob = JSON.parse(raw)
      prefillFromEob({
        date_of_service: eob.date_of_service,
        provider_name: eob.provider_name,
        facility_name: eob.facility_name,
        cpt_code: eob.cpt_code,
        cpt_description: eob.cpt_description,
        icd_10_code: eob.icd_10_code,
        billed_amount: eob.billed_amount ? Number(eob.billed_amount) : null,
        allowed_amount: eob.allowed_amount ? Number(eob.allowed_amount) : null,
        denial_reason_text: eob.denial_reason_text,
        denial_carc_code: eob.denial_carc_code,
        denial_date: eob.denial_date,
      })
    } catch {
      setError('Could not load the document prefill. Please enter claim details manually.')
    }
  }, [])

  const handleDraftEscalated = async (level) => {
    if (!result?.claim_case || !policyProfile) return
    setEscalatedLevel(level); setEscalatedLoading(true); setEscalatedResult(null); setEscalatedError(null)
    try {
      const res = await apiFetch('/claim/draft-appeal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          level,
          policy_profile: policyProfile,
          claim_case: result.claim_case,
          level1_denial_summary: result.appeal_output?.appeal_letter?.slice(0, 600) || null,
        }),
      })
      const data = await readApiResponse(res)
      if (data.success) {
        setEscalatedResult(data)
      } else {
        setEscalatedError(formatApiError(data, 'Draft failed.'))
      }
    } catch (err) {
      setEscalatedError(`Network error: ${err.message}`)
    } finally {
      setEscalatedLoading(false)
    }
  }

  const handleEobUpload = async () => {
    if (!eobFile) return
    setEobLoading(true); setEobResult(null); setEobError(null)
    try {
      const formData = new FormData()
      formData.append('file', eobFile)
      const res = await apiFetch('/eob/parse', { method: 'POST', body: formData })
      const data = await readApiResponse(res)
      if (data.success && data.extracted) {
        setEobResult(data.extracted)
        prefillFromEob(data.extracted)
      } else {
        setEobError(formatApiError(data, 'EOB extraction failed.'))
      }
    } catch (err) {
      setEobError(`Network error: ${err.message}`)
    } finally {
      setEobLoading(false)
    }
  }

  const prefillFromEob = (eob) => {
    const parts = []
    if (eob.date_of_service) parts.push(`Date of service: ${eob.date_of_service}.`)
    if (eob.provider_name) parts.push(`Provider: ${eob.provider_name}.`)
    if (eob.facility_name) parts.push(`Facility: ${eob.facility_name}.`)
    if (eob.cpt_code) parts.push(`CPT code: ${eob.cpt_code}${eob.cpt_description ? ` (${eob.cpt_description})` : ''}.`)
    if (eob.icd_10_code) parts.push(`ICD-10: ${eob.icd_10_code}${eob.icd_10_description ? ` (${eob.icd_10_description})` : ''}.`)
    if (eob.billed_amount) parts.push(`Billed amount: $${eob.billed_amount.toLocaleString()}.`)
    if (eob.allowed_amount) parts.push(`Allowed amount (per EOB): $${eob.allowed_amount.toLocaleString()}.`)
    if (eob.denial_reason_text) parts.push(`Denial reason: ${eob.denial_reason_text}.`)
    if (eob.denial_carc_code) parts.push(`CARC code: ${eob.denial_carc_code}.`)
    if (eob.denial_date) parts.push(`Denial date: ${eob.denial_date}.`)
    setClaimText(parts.join(' '))
    if (eob.allowed_amount) setAllowedAmount(String(eob.allowed_amount))
    if (eob.date_of_service) setGuided(p => ({ ...p, date_of_service: eob.date_of_service || '' }))
    if (eob.provider_name) setGuided(p => ({ ...p, provider_name: eob.provider_name || '' }))
    if (eob.denial_date) setGuided(p => ({ ...p, denial_date: eob.denial_date || '' }))
    if (eob.denial_carc_code) setGuided(p => ({ ...p, carc_code: eob.denial_carc_code || '' }))
  }

  // Progress step auto-advance during loading
  useEffect(() => {
    if (loading) {
      setProgressStep(0)
      let step = 0
      progressTimer.current = setInterval(() => {
        step += 1
        if (step < PROGRESS_STEPS.length) setProgressStep(step)
        else clearInterval(progressTimer.current)
      }, 3000)
    } else {
      clearInterval(progressTimer.current)
      setProgressStep(0)
    }
    return () => clearInterval(progressTimer.current)
  }, [loading])

  const buildFromGuided = () => {
    const parts = []
    if (guided.date_of_service) parts.push(`Date of service: ${guided.date_of_service}.`)
    if (guided.provider_name) parts.push(`Provider: ${guided.provider_name}.`)
    if (guided.denial_reason) parts.push(`Denial reason: ${DENIAL_REASONS.find(d => d[0] === guided.denial_reason)?.[1] || guided.denial_reason}.`)
    if (guided.carc_code) parts.push(`CARC/RARC code: ${guided.carc_code}.`)
    if (guided.denial_date) parts.push(`Denial date: ${guided.denial_date}.`)
    if (parts.length) setClaimText(prev => (prev ? prev + '\n\n' : '') + parts.join(' '))
    setGuidedOpen(false)
  }

  const buildAppealLetterExport = () => {
    if (!result?.appeal_output?.appeal_letter) return ''

    const appeal = result.appeal_output
    const deadline = appeal.appeal_deadline
      ? new Date(appeal.appeal_deadline).toLocaleDateString()
      : 'Not available'

    return [
      'PolicyCrab Appeal Letter',
      '',
      `Framework: ${appeal.appeal_framework || 'Not available'}`,
      `Appeal deadline: ${deadline}${appeal.days_remaining != null ? ` (${appeal.days_remaining} days remaining)` : ''}`,
      '',
      appeal.appeal_letter,
    ].join('\n')
  }

  const handleCopyAppealLetter = async () => {
    const text = buildAppealLetterExport()
    if (!text) return

    try {
      await navigator.clipboard.writeText(text)
      setLetterActionStatus('Copied appeal letter')
    } catch {
      setLetterActionStatus('Copy failed. Select the letter text manually.')
    }
  }

  const handleDownloadAppealLetter = () => {
    const text = buildAppealLetterExport()
    if (!text) return

    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const date = new Date().toISOString().slice(0, 10)
    link.href = url
    link.download = `policycrab-appeal-letter-${date}.txt`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    setLetterActionStatus('Downloaded appeal letter')
  }

  const handleDownloadPDF = () => {
    if (!result?.appeal_output?.appeal_letter) return
    const appeal = result.appeal_output
    const doc = new jsPDF({ unit: 'pt', format: 'letter' })
    const margin = 60
    const pageW = doc.internal.pageSize.getWidth()
    const maxW = pageW - margin * 2
    let y = margin

    // Header
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(16)
    doc.setTextColor(220, 38, 38)
    doc.text('PolicyCrab — Appeal Letter', margin, y)
    y += 24
    doc.setDrawColor(220, 38, 38)
    doc.setLineWidth(1.5)
    doc.line(margin, y, pageW - margin, y)
    y += 20

    // Meta
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.setTextColor(100)
    doc.text(`Framework: ${appeal.appeal_framework || 'N/A'}`, margin, y)
    y += 14
    const dl = appeal.appeal_deadline ? new Date(appeal.appeal_deadline).toLocaleDateString() : 'N/A'
    doc.text(`Appeal Deadline: ${dl}${appeal.days_remaining != null ? ` (${appeal.days_remaining} days remaining)` : ''}`, margin, y)
    y += 14
    doc.text(`Generated: ${new Date().toLocaleDateString()}`, margin, y)
    y += 24

    // Body
    doc.setFont('times', 'normal')
    doc.setFontSize(11)
    doc.setTextColor(30)
    const lines = doc.splitTextToSize(appeal.appeal_letter, maxW)
    const pageH = doc.internal.pageSize.getHeight()
    for (const line of lines) {
      if (y > pageH - 80) { doc.addPage(); y = margin }
      doc.text(line, margin, y)
      y += 15
    }

    // Signature placeholder
    y += 30
    if (y > pageH - 100) { doc.addPage(); y = margin }
    doc.setDrawColor(180)
    doc.setLineWidth(0.5)
    doc.line(margin, y, margin + 200, y)
    y += 14
    doc.setFont('helvetica', 'italic')
    doc.setFontSize(9)
    doc.setTextColor(100)
    doc.text('Patient Signature / Date', margin, y)
    y += 30

    // Footer disclaimer
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7)
    doc.setTextColor(150)
    doc.text('DISCLAIMER: This letter was generated by PolicyCrab for informational purposes only. Not legal or medical advice.', margin, pageH - 30)

    const date = new Date().toISOString().slice(0, 10)
    doc.save(`policycrab-appeal-letter-${date}.pdf`)
    setLetterActionStatus('Downloaded PDF')
  }

  const handleEvaluate = () => {
    if (!policyProfile) { setError('Upload a policy first.'); return }
    if (claimText.trim().length < 20) { setError('Please describe the claim in more detail.'); return }
    const normalizedAllowedAmount = allowedAmount === '' ? null : Number(allowedAmount)
    if (normalizedAllowedAmount != null && (!Number.isFinite(normalizedAllowedAmount) || normalizedAllowedAmount <= 0)) {
      setError('Allowed amount must be greater than $0, or leave it blank for an estimate.')
      return
    }
    setLoading(true); setError(null); setResult(null); setLetterActionStatus(''); setProgressStep(0)

    const capturedText   = claimText
    const capturedStatus = networkStatus
    const capturedAmount = normalizedAllowedAmount

    addTask('claim_eval', 'Evaluating your claim…', async () => {
      const res = await apiFetch('/claim/evaluate', {
        method: 'POST',
        body: JSON.stringify({
          claim_description: capturedText + (capturedStatus ? `\n\nNetwork Status: ${capturedStatus}` : ''),
          policy_profile: policyProfile,
          allowed_amount: capturedAmount,
          session_id: policySession?.session_id || null,
          policy_indexed: Boolean(policySession?.policy_indexed),
        })
      })
      const data = await readApiResponse(res)
      if (data.success && data.cost_breakdown) {
        setResult(data)
        onResult(data.cost_breakdown)
        setLoading(false)
        return { data }
      } else {
        throw new Error(formatApiError(data, 'Evaluation failed'))
      }
    }).catch(err => {
      setError(err.message || 'Network error during evaluation.')
      setLoading(false)
    })
  }

  const handleProviderSearch = async () => {
    if (!providerSearch.city && !providerSearch.state && !providerSearch.last_name && !providerSearch.taxonomy_description) {
      setProviderError('Enter a provider name, specialty, city, or state.')
      return
    }

    setProviderLoading(true)
    setProviderError(null)
    setProviderResults([])

    try {
      const res = await apiFetch('/providers/search', {
        method: 'POST',
        body: JSON.stringify({ ...providerSearch, limit: 5 }),
      })
      const data = await readApiResponse(res)
      if (!res.ok) throw new Error(formatApiError(data, 'Provider search failed'))
      setProviderResults(data.results || [])
    } catch (err) {
      setProviderError(err.message)
    } finally {
      setProviderLoading(false)
    }
  }

  const handleNetworkCheck = async (provider) => {
    if (!policyProfile?.plan_name) {
      setProviderError('Upload or select a policy first so network status can be checked against the plan name.')
      return
    }

    setProviderError(null)
    setNetworkChecks(prev => ({ ...prev, [provider.npi]: { loading: true } }))

    try {
      const res = await apiFetch('/providers/network-status', {
        method: 'POST',
        body: JSON.stringify({ npi: provider.npi, plan_name: policyProfile.plan_name }),
      })
      const data = await readApiResponse(res)
      if (!res.ok) throw new Error(formatApiError(data, 'Network status check failed'))
      setNetworkChecks(prev => ({ ...prev, [provider.npi]: data }))
    } catch (err) {
      setNetworkChecks(prev => ({ ...prev, [provider.npi]: { error: err.message } }))
    }
  }

  const addProviderToClaim = (provider) => {
    const network = networkChecks[provider.npi]?.result
    const address = provider.address
      ? `${provider.address.address_1}, ${provider.address.city}, ${provider.address.state} ${provider.address.postal_code}`
      : 'address unavailable'
    const providerText = `\n\nProvider/facility context from CMS NPPES: ${provider.name}, NPI ${provider.npi}, ${provider.primary_specialty}, ${address}.${network ? ` Network-status estimate for ${policyProfile?.plan_name}: ${network}` : ''}`
    setClaimText(prev => `${prev}${providerText}`.trim())
  }

  return (
    <section className="section-white section-pad">
      <div className="main">
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }}>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label">
            <span className="line" /> Step 2
          </motion.p>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.55 }} className="section-title">
            Evaluate your <span className="gradient-text">healthcare claim</span>
          </motion.h1>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-subtitle" style={{ marginBottom: '2rem' }}>
            Describe your medical encounter. The system calculates your estimated cost, and if denied, it can help draft an appeal letter.
          </motion.p>
        </motion.div>

        {!policyProfile && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
            style={{ marginBottom: '2rem', padding: '1.25rem 1.5rem', background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', borderRadius: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <IconAlertTriangle size={24} style={{ color: 'var(--warning)' }} />
              <div>
                <h4 style={{ fontWeight: 700, color: 'var(--warning)', fontSize: '0.9375rem', marginBottom: '0.25rem' }}>Policy Required</h4>
                <p style={{ color: 'var(--warning)', fontSize: '0.8125rem', fontWeight: 500, opacity: 0.8 }}>Upload your policy first for accurate cost calculations.</p>
              </div>
            </div>
            <button className="btn btn-red" style={{ flexShrink: 0 }} onClick={() => navigate('/policy')}>Upload Policy →</button>
          </motion.div>
        )}

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
          className="card" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <div className="feature-icon emerald" style={{ background: 'var(--success-bg)', color: 'var(--success)', border: '1px solid var(--success-border)' }}><IconStethoscope size={20} /></div>
              <div>
                <h2 style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>Provider & Facility Network Check</h2>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', maxWidth: '44rem' }}>
                  Search the CMS NPPES registry for real US doctors and hospitals, then estimate network status against your loaded plan before planned non-emergency care.
                </p>
              </div>
            </div>
            <span className="badge badge-info">CMS NPPES</span>
          </div>

          <div className="grid-4" style={{ gap: '0.75rem', marginBottom: '1rem' }}>
            <input className="input" placeholder="Last name or facility" value={providerSearch.last_name}
              onChange={e => {
                const val = e.target.value
                const isFacilityLike = /\b(hospital|clinic|center|medical|health|imaging|surgery|associates|group|care)\b/i.test(val)
                setProviderSearch(prev => ({ 
                  ...prev, 
                  last_name: val,
                  ...(isFacilityLike ? { is_facility: true } : {})
                }))
              }} />
            <input className="input" placeholder="Specialty" value={providerSearch.taxonomy_description}
              onChange={e => setProviderSearch(prev => ({ ...prev, taxonomy_description: e.target.value }))} />
            <input className="input" placeholder="City" value={providerSearch.city}
              onChange={e => setProviderSearch(prev => ({ ...prev, city: e.target.value }))} />
            <input className="input" placeholder="State" maxLength={2} value={providerSearch.state}
              onChange={e => setProviderSearch(prev => ({ ...prev, state: e.target.value.toUpperCase() }))} />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
            <label style={{ 
              display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', 
              color: providerSearch.is_facility ? 'var(--accent)' : 'var(--text-primary)', 
              fontWeight: providerSearch.is_facility ? 800 : 600,
              transition: 'all 0.2s'
            }}>
              <input type="checkbox" checked={providerSearch.is_facility}
                onChange={e => setProviderSearch(prev => ({ ...prev, is_facility: e.target.checked }))} 
                style={{ accentColor: 'var(--accent)', transform: providerSearch.is_facility ? 'scale(1.1)' : 'scale(1)' }}/>
              Search hospitals / facilities
            </label>
            <button className="btn btn-red" onClick={handleProviderSearch} disabled={providerLoading}>
              {providerLoading ? <><span className="spinner" /> Searching...</> : <><IconSearch size={18} /> Search Providers</>}
            </button>
          </div>

          <p style={{ marginTop: '1rem', fontSize: '0.75rem', color: 'var(--text-tertiary)', lineHeight: 1.5, display: 'flex', gap: '0.5rem' }}>
            <IconAlertTriangle size={14} style={{ flexShrink: 0, marginTop: '2px' }} />
            Network data is an estimate unless your insurer confirms it. For emergencies and certain surprise out-of-network bills, the No Surprises Act may cap patient cost-sharing at in-network amounts.
          </p>

          {providerError && (
            <div style={{ marginTop: '1.25rem', padding: '0.875rem 1rem', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: '0.75rem', color: 'var(--danger)', fontSize: '0.875rem', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconAlertTriangle size={16} /> {providerError}
            </div>
          )}

          {providerResults.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem', marginTop: '1.5rem' }}>
              {providerResults.map(provider => {
                const network = networkChecks[provider.npi]
                return (
                  <div key={provider.npi} style={{ border: '1px solid var(--border-secondary)', borderRadius: '1rem', padding: '1.25rem', background: 'var(--bg-secondary)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                      <div>
                        <h3 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)' }}>{provider.name}</h3>
                        <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.375rem', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                          <span className="badge badge-zinc" style={{ fontSize: '0.625rem', padding: '0.125rem 0.375rem' }}>NPI {provider.npi}</span>
                          {provider.primary_specialty}
                        </p>
                        {provider.address && (
                          <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                            <IconMapPin size={12} /> {provider.address.address_1}, {provider.address.city}, {provider.address.state} {provider.address.postal_code}
                          </p>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                        <button className="btn btn-outline" style={{ padding: '0.5rem 0.75rem', fontSize: '0.8125rem' }} onClick={() => handleNetworkCheck(provider)} disabled={!policyProfile || network?.loading}>
                          {network?.loading ? <><span className="spinner" style={{ width: '12px', height: '12px' }} /> Checking...</> : <><IconActivity size={14} /> Check Network</>}
                        </button>
                        <button className="btn btn-outline" style={{ padding: '0.5rem 0.75rem', fontSize: '0.8125rem' }} onClick={() => addProviderToClaim(provider)}>Use in Claim</button>
                      </div>
                    </div>
                    {network?.result && (
                      <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'var(--bg-card)', border: '1px solid var(--border-primary)', borderRadius: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
                        {network.result}
                      </div>
                    )}
                    {network?.error && (
                      <div style={{ marginTop: '1rem', fontSize: '0.8125rem', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                        <IconAlertTriangle size={14} /> {network.error}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </motion.div>

        <div className="grid-2" style={{ alignItems: 'start' }}>
          {/* ── Input ─────────────────── */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.15 }}>
            <div className="card" style={{ padding: '2rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
                <div className="feature-icon red"><IconFileText size={20} /></div>
                <div>
                  <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Claim Details</h3>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Describe the service, diagnosis, and billing</p>
                </div>
              </div>

              {/* ── EOB Upload Panel ───────────── */}
              <div className="guided-form-panel" style={{ marginBottom: '1.5rem' }}>
                <div className={`guided-form-header${eobResult ? ' open' : ''}`}
                  onClick={() => !eobResult && document.getElementById('eob-upload-input').click()}
                  style={{ cursor: eobResult ? 'default' : 'pointer' }}
                >
                  <span className="guided-form-title">
                    <IconUpload size={16} style={{ color: 'var(--accent)' }} /> Upload EOB PDF
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontWeight: 500, marginLeft: '0.5rem' }}>— auto-fill from Explanation of Benefits</span>
                  </span>
                  {eobFile && !eobResult && (
                    <button
                      type="button"
                      className="btn btn-red"
                      style={{ padding: '0.375rem 0.875rem', fontSize: '0.75rem' }}
                      onClick={e => { e.stopPropagation(); handleEobUpload() }}
                      disabled={eobLoading}
                    >
                      {eobLoading ? <><span className="spinner" /> Parsing...</> : 'Extract Fields'}
                    </button>
                  )}
                  {!eobFile && <span style={{ fontSize: '0.75rem', color: 'var(--accent)', fontWeight: 600 }}>Click to select PDF</span>}
                </div>
                <input
                  id="eob-upload-input"
                  type="file"
                  accept="application/pdf"
                  style={{ display: 'none' }}
                  onChange={e => { setEobFile(e.target.files[0] || null); setEobResult(null); setEobError(null) }}
                />
                {eobFile && !eobResult && (
                  <div style={{ padding: '0.875rem 1rem', fontSize: '0.8125rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem', borderTop: '1px solid var(--border-secondary)' }}>
                    <IconFileText size={16} /> <strong>{eobFile.name}</strong>
                    <button type="button" onClick={() => setEobFile(null)} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}><IconX size={14} /> Remove</button>
                  </div>
                )}
                {eobError && (
                  <div style={{ padding: '0.75rem 1rem', fontSize: '0.8125rem', color: 'var(--danger)', borderTop: '1px solid var(--danger-border)', background: 'var(--danger-bg)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}><IconAlertTriangle size={16} /> {eobError}</div>
                )}
                {eobResult && (
                  <div style={{ padding: '1.25rem' }}>
                    {eobResult.validation_errors?.length > 0 && (
                      <div style={{ background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: '0.75rem', padding: '0.875rem 1rem', fontSize: '0.875rem', color: 'var(--danger)', marginBottom: '1.25rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                          <IconAlertTriangle size={16} /> Math Validation Errors
                        </div>
                        <ul style={{ margin: 0, paddingLeft: '1.5rem' }}>
                          {eobResult.validation_errors.map((err, i) => <li key={i}>{err}</li>)}
                        </ul>
                        <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', fontWeight: 600 }}>Please correct the numbers below before continuing.</div>
                      </div>
                    )}
                    <div className="eob-fields-grid">
                      {[
                        { label: 'Date of Service', key: 'date_of_service', type: 'date', val: eobResult.date_of_service, conf: eobResult.confidence?.date_of_service },
                        { label: 'Provider', key: 'provider_name', type: 'text', val: eobResult.provider_name, conf: 'high' },
                        { label: 'Facility', key: 'facility_name', type: 'text', val: eobResult.facility_name, conf: 'high' },
                        { label: 'CPT Code', key: 'cpt_code', type: 'text', val: eobResult.cpt_code, conf: eobResult.confidence?.cpt_code },
                        { label: 'ICD-10', key: 'icd_10_code', type: 'text', val: eobResult.icd_10_code, conf: 'high' },
                        { label: 'Billed Amount ($)', key: 'billed_amount', type: 'number', val: eobResult.billed_amount, conf: eobResult.confidence?.billed_amount },
                        { label: 'Allowed Amount ($)', key: 'allowed_amount', type: 'number', val: eobResult.allowed_amount, conf: eobResult.confidence?.allowed_amount },
                        { label: 'Patient Resp ($)', key: 'patient_responsibility', type: 'number', val: eobResult.patient_responsibility, conf: 'high' },
                        { label: 'CARC Code', key: 'denial_carc_code', type: 'text', val: eobResult.denial_carc_code, conf: eobResult.confidence?.denial_carc_code },
                        { label: 'Denial Date', key: 'denial_date', type: 'date', val: eobResult.denial_date, conf: 'high' },
                      ].map(({ label, key, type, val, conf }) => (
                        <div key={label} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-secondary)', borderRadius: '0.75rem', padding: '0.625rem 0.875rem' }}>
                          <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.25rem', display: 'flex', justifyContent: 'space-between' }}>
                            {label}
                            {conf === 'low' && <span style={{ color: 'var(--warning)', fontSize: '0.625rem', display: 'flex', alignItems: 'center', gap: '0.125rem' }}><IconAlertTriangle size={10} /> verify</span>}
                          </div>
                          <input
                            className="input"
                            type={type}
                            step={type === 'number' ? '0.01' : undefined}
                            value={val == null ? '' : val}
                            onChange={e => {
                               let v = e.target.value;
                               if (type === 'number') v = v === '' ? null : Number(v);
                               setEobResult(prev => {
                                 // Clear validation errors when user starts editing so they can attempt to fix it
                                 const updated = { ...prev, [key]: v };
                                 if (updated.validation_errors) updated.validation_errors = [];
                                 return updated;
                               });
                            }}
                            style={{ padding: '0.375rem 0.5rem', fontSize: '0.875rem', minHeight: 'auto', background: 'var(--bg-card)' }}
                          />
                        </div>
                      ))}
                    </div>
                    {eobResult.denial_reason_text && (
                      <div style={{ background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: '0.75rem', padding: '0.875rem 1rem', fontSize: '0.875rem', color: 'var(--danger)', marginBottom: '1.25rem', lineHeight: 1.5 }}>
                        <strong>Denial reason:</strong> {eobResult.denial_reason_text}
                      </div>
                    )}
                    <div style={{ display: 'flex', gap: '0.75rem' }}>
                      <button type="button" className="btn btn-red" style={{ flex: 1, padding: '0.75rem', fontSize: '0.875rem' }} onClick={() => prefillFromEob(eobResult)}>
                        <IconCheckCircle size={16} /> Re-sync to Claim Description
                      </button>
                      <button type="button" className="btn btn-outline" style={{ padding: '0.75rem 1rem' }} onClick={() => { setEobResult(null); setEobFile(null) }}>Clear</button>
                    </div>
                  </div>
                )}
              </div>

              {/* ── CPT Lookup ─────────────────────── */}
              <CptLookup
                disabled={!policyProfile}
                onSelect={({ code, desc }) => {
                  // Append structured CPT line to textarea if not already present
                  const line = `Procedure: CPT ${code} — ${desc}.`
                  setClaimText(prev =>
                    prev.includes(`CPT ${code}`)
                      ? prev
                      : prev ? `${prev}\n${line}` : line
                  )
                }}
              />

              <textarea className="input" value={claimText} onChange={e => setClaimText(e.target.value)}
                placeholder="e.g., I went to the ER for chest pain on July 1st. The hospital billed $15,000..."
                style={{ minHeight: '160px', marginBottom: '1.25rem' }} disabled={!policyProfile}
              />

              <label style={{ display: 'block', marginBottom: '1.5rem' }}>
                <span style={{ display: 'block', fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                  EOB allowed amount
                </span>
                <input
                  className="input"
                  type="number"
                  min="0"
                  step="0.01"
                  value={allowedAmount}
                  onChange={e => setAllowedAmount(e.target.value)}
                  placeholder="Optional, e.g. 1200.00"
                  disabled={!policyProfile}
                />
                <span style={{ display: 'flex', gap: '0.375rem', fontSize: '0.75rem', color: 'var(--text-tertiary)', lineHeight: 1.5, marginTop: '0.5rem' }}>
                  <IconAlertTriangle size={14} style={{ flexShrink: 0, marginTop: '2px' }} />
                  Use the allowed amount, plan discount, or approved amount from your EOB. If left blank, PolicyCrab labels the result as an estimate and does not assume a negotiated rate.
                </span>
              </label>

              <div style={{ marginBottom: '1.5rem' }}>
                <span style={{ display: 'block', fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                  Network Status
                </span>
                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                  {[['IN_NETWORK', 'In-Network'], ['OUT_OF_NETWORK', 'Out-of-Network'], ['OON_EMERGENCY', 'OON Emergency (NSA)']].map(([val, label]) => (
                    <button 
                      key={val} 
                      type="button"
                      className={`btn ${networkStatus === val ? 'btn-red' : 'btn-outline'}`} 
                      style={{ fontSize: '0.8125rem', padding: '0.5rem 1rem' }} 
                      onClick={() => setNetworkStatus(networkStatus === val ? '' : val)}
                      disabled={!policyProfile}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* ── Guided Form ────────────── */}
              <div className="guided-form-panel">
                <div className={`guided-form-header${guidedOpen ? ' open' : ''}`} onClick={() => setGuidedOpen(o => !o)}>
                  <span className="guided-form-title"><IconEdit size={16} style={{ color: 'var(--text-secondary)' }} /> Guided Intake Fields <span style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)', fontWeight: 500 }}>(optional)</span></span>
                  <span style={{ fontSize: '1rem', color: 'var(--text-tertiary)' }}>{guidedOpen ? <IconChevronUp size={20} /> : <IconChevronDown size={20} />}</span>
                </div>
                {guidedOpen && (
                  <div className="guided-form-body">
                    <div className="guided-field">
                      <label>Date of Service</label>
                      <input className="input" type="date" value={guided.date_of_service} onChange={e => setGuided(p => ({ ...p, date_of_service: e.target.value }))} />
                    </div>
                    <div className="guided-field">
                      <label>Provider Name</label>
                      <input className="input" placeholder="e.g., Dr. Smith" value={guided.provider_name} onChange={e => setGuided(p => ({ ...p, provider_name: e.target.value }))} />
                    </div>
                    <div className="guided-field">
                      <label>Denial Date</label>
                      <input className="input" type="date" value={guided.denial_date} onChange={e => setGuided(p => ({ ...p, denial_date: e.target.value }))} />
                    </div>
                    <div className="guided-field">
                      <label>Denial Reason</label>
                      <select className="input" value={guided.denial_reason} onChange={e => setGuided(p => ({ ...p, denial_reason: e.target.value }))}>
                        {DENIAL_REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                      </select>
                    </div>
                    <div className="guided-field">
                      <label>CARC / RARC Code</label>
                      <input className="input" placeholder="e.g., CO-50" value={guided.carc_code} onChange={e => setGuided(p => ({ ...p, carc_code: e.target.value }))} />
                    </div>
                    <div className="guided-form-build">
                      <button className="btn btn-outline" type="button" onClick={buildFromGuided}>Add to Claim Description →</button>
                    </div>
                  </div>
                )}
              </div>

              <button className="btn btn-red" onClick={handleEvaluate} disabled={loading || !policyProfile || claimText.trim().length < 20} style={{ width: '100%', padding: '1rem', fontSize: '1rem' }}>
                {loading ? <><span className="spinner" /> Evaluating Pipeline...</> : <><IconZap size={18} /> Run Evaluation</>}
              </button>

              {/* ── Progress Stepper ────────── */}
              {loading && (
                <div className="claim-progress" style={{ marginTop: '1.5rem', background: 'var(--bg-secondary)', padding: '1.25rem', borderRadius: '1rem' }}>
                  <span className="claim-progress-title" style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem', display: 'block' }}>Pipeline Progress</span>
                  <div className="claim-progress-steps" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {PROGRESS_STEPS.map((s, i) => (
                      <div key={i} className={`progress-step${i < progressStep ? ' done' : i === progressStep ? ' active' : ''}`} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div className="progress-step-dot" style={{ 
                          width: '24px', height: '24px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: i < progressStep ? 'var(--success)' : i === progressStep ? 'var(--accent)' : 'var(--border-secondary)',
                          color: i <= progressStep ? '#fff' : 'var(--text-tertiary)',
                          fontSize: '0.75rem', fontWeight: 700,
                          transition: 'all 0.3s ease',
                          boxShadow: i === progressStep ? '0 0 0 4px var(--accent-subtle)' : 'none'
                        }}>
                          {i < progressStep ? <IconCheckCircle size={14} /> : i + 1}
                        </div>
                        <span className="progress-step-label" style={{ 
                          fontSize: '0.875rem', 
                          fontWeight: i === progressStep ? 700 : 500, 
                          color: i < progressStep ? 'var(--text-secondary)' : i === progressStep ? 'var(--text-primary)' : 'var(--text-tertiary)',
                          transition: 'color 0.3s ease'
                        }}>
                          {s.label}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ── AI Transparency Log (Phase 2 — XPRIZE Evidence) ── */}
              {loading && (
                <div style={{ marginTop: '1rem' }}>
                  <AILogViewer task="legal_writing" active={loading} />
                </div>
              )}

              {error && (
                <div style={{ marginTop: '1.25rem', padding: '0.875rem 1rem', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: '0.75rem', color: 'var(--danger)', fontSize: '0.875rem', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <IconAlertTriangle size={18} /> {error}
                </div>
              )}
            </div>

            {result?.claim_case && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
                className="card" style={{ marginTop: '1.5rem', padding: '1.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-secondary)' }}>
                <h4 style={{ fontWeight: 800, fontSize: '1rem', marginBottom: '1rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <IconCpu size={18} style={{ color: 'var(--text-secondary)' }} /> Agent 2: Normalized Intake
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {[
                    ['CPT Code', `${result.claim_case.cpt_code} — ${result.claim_case.cpt_description}`],
                    ['ICD-10', result.claim_case.icd_10_code],
                    ['Network', result.claim_case.network_status],
                    ['Emergency', result.claim_case.is_emergency ? '✅ Yes' : '❌ No'],
                  ].map(([l, v]) => <div className="result-row" key={l} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--border-primary)' }}><span className="result-label" style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{l}</span><span className="result-value" style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)', textAlign: 'right' }}>{v}</span></div>)}
                </div>
                {result.claim_case.nsa_applies && (
                  <div style={{ marginTop: '1rem' }}><span className="badge badge-purple" style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', padding: '0.5rem 0.75rem' }}><IconShield size={14} /> No Surprises Act Applies</span></div>
                )}
              </motion.div>
            )}
          </motion.div>

          {/* ── Results ────────────────── */}
          <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.55, delay: 0.25 }}>
            {result ? (
              <>
                <div className="card" style={{ marginBottom: '1.5rem', overflow: 'hidden' }}>
                  <div style={{ padding: '1.25rem 1.5rem', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)' }}>Cost Breakdown</h3>
                    {result.route_decision === 'denied' ? <span className="badge badge-danger">Denied</span> : <span className="badge badge-success">Approved</span>}
                  </div>
                  <div style={{ padding: '1.5rem' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {[
                        ['Billed Amount', `$${result.cost_breakdown.billed_amount?.toLocaleString()}`, ''],
                        ['Allowed Amount', `$${result.cost_breakdown.allowed_amount?.toLocaleString()}`, ''],
                        ['Applied to Deductible', `$${result.cost_breakdown.applied_to_deductible?.toLocaleString()}`, ''],
                        ['Coinsurance', `$${result.cost_breakdown.coinsurance_amount?.toLocaleString()}`, ''],
                      ].map(([l, v]) => <div className="result-row" key={l} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0' }}><span className="result-label" style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{l}</span><span className="result-value" style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)' }}>{v}</span></div>)}
                    </div>

                    <div style={{ height: '1px', background: 'var(--border-secondary)', margin: '1rem 0' }} />

                    <div style={{ marginBottom: '1.25rem' }}>
                      {result.cost_breakdown.allowed_amount_source === 'eob'
                        ? <span className="badge badge-success">EOB-based allowed amount</span>
                        : <span className="badge badge-warning">Estimate: no EOB allowed amount</span>}
                    </div>

                    <div className="result-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '0.75rem 0', alignItems: 'center' }}>
                      <span className="result-label" style={{ fontWeight: 800, color: 'var(--text-primary)', fontSize: '1.125rem' }}>Your Total Responsibility</span>
                      <span className="result-value money" style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--accent)' }}>${result.cost_breakdown.total_patient_responsibility?.toLocaleString()}</span>
                    </div>
                    <div className="result-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0' }}>
                      <span className="result-label" style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Insurer Pays</span>
                      <span className="result-value" style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--success)' }}>${result.cost_breakdown.total_insurer_payout?.toLocaleString()}</span>
                    </div>
                  </div>
                </div>

                {result.cost_breakdown?.calculation_notes?.length > 0 && (
                  <div className="card" style={{ padding: '1.25rem 1.5rem', marginBottom: '1.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-secondary)' }}>
                    <h4 style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Waterfall Notes</h4>
                    <ul style={{ fontSize: '0.8125rem', paddingLeft: '1.25rem', listStyle: 'disc', color: 'var(--text-secondary)', lineHeight: 1.5, display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
                      {result.cost_breakdown.calculation_notes.map((n, i) => <li key={i}>{n}</li>)}
                    </ul>
                  </div>
                )}

                {result.explanation && (
                  <div className="explanation-box" style={{ marginBottom: result.appeal_output ? '1.5rem' : 0, background: 'var(--info-bg)', border: '1px solid var(--info-border)' }}>
                    <h4 style={{ color: 'var(--info)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}><IconFileText size={18} /> Plain English Summary</h4>
                    <div style={{ whiteSpace: 'pre-wrap', color: 'var(--text-primary)', fontSize: '0.9375rem', lineHeight: 1.6 }}>{result.explanation}</div>
                  </div>
                )}

                {/* ── Agent 3: Policy Analyzer Results ────────────────── */}
                {result.appeal_output && (
                  <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                    style={{
                      marginBottom: '1.5rem',
                      border: result.appeal_output.contradiction_detected
                        ? '1px solid var(--accent-border)'
                        : '1px solid var(--border-primary)',
                      borderRadius: 'var(--radius-2xl)',
                      overflow: 'hidden',
                      background: 'var(--bg-card)',
                      boxShadow: result.appeal_output.contradiction_detected ? '0 8px 32px var(--accent-subtle)' : 'var(--shadow-sm)'
                    }}
                  >
                    {/* Header */}
                    <div style={{
                      padding: '1.25rem 1.5rem',
                      background: result.appeal_output.contradiction_detected
                        ? 'var(--accent-subtle)'
                        : 'var(--bg-secondary)',
                      borderBottom: '1px solid var(--border-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '1rem',
                      flexWrap: 'wrap',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div className="feature-icon red"><IconSearch size={20} /></div>
                        <div>
                          <h3 style={{ fontWeight: 800, color: 'var(--text-primary)', fontSize: '1.0625rem' }}>Agent 3: Policy Analyzer</h3>
                          <p style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>Cross-referencing denial against your loaded policy document</p>
                        </div>
                      </div>
                      {result.appeal_output.contradiction_strength && (
                        <span className={`badge ${
                          result.appeal_output.contradiction_strength === 'STRONG' ? 'badge-danger' :
                          result.appeal_output.contradiction_strength === 'MODERATE' ? 'badge-warning' :
                          result.appeal_output.contradiction_strength === 'WEAK' ? 'badge-info' :
                          'badge-zinc'
                        }`}>
                          {result.appeal_output.contradiction_strength === 'STRONG' ? '🚨 Strong Contradiction Found' :
                           result.appeal_output.contradiction_strength === 'MODERATE' ? '⚠️ Moderate Contradiction Found' :
                           result.appeal_output.contradiction_strength === 'WEAK' ? '🔎 Weak Contradiction Signal' :
                           '✓ No Direct Contradiction'}
                        </span>
                      )}
                    </div>

                    <div style={{ padding: '1.5rem' }}>
                      {/* AI Honest Assessment */}
                      {result.appeal_output.honest_assessment && (
                        <div style={{
                          background: 'var(--bg-secondary)',
                          border: '1px solid var(--border-secondary)',
                          borderRadius: 'var(--radius-lg)',
                          padding: '1rem 1.25rem',
                          marginBottom: '1.25rem',
                          display: 'flex',
                          gap: '0.75rem',
                          alignItems: 'flex-start',
                        }}>
                          <span style={{ fontSize: '1.25rem', lineHeight: 1, flexShrink: 0 }}>🤖</span>
                          <div>
                            <p style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.375rem' }}>AI Honest Assessment</p>
                            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.65, fontWeight: 500 }}>
                              {result.appeal_output.honest_assessment}
                            </p>
                          </div>
                        </div>
                      )}

                      {/* Appeal Recommendation */}
                      {result.appeal_output.appeal_recommendation && (
                        <div style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>Recommendation:</span>
                          <span className={`badge ${
                            result.appeal_output.appeal_recommendation === 'STRONG_APPEAL' ? 'badge-success' :
                            result.appeal_output.appeal_recommendation === 'APPEAL' ? 'badge-info' :
                            result.appeal_output.appeal_recommendation === 'EXCEPTION_REQUEST' ? 'badge-purple' :
                            result.appeal_output.appeal_recommendation === 'UNLIKELY_TO_WIN' ? 'badge-warning' :
                            'badge-danger'
                          }`} style={{ fontSize: '0.75rem', padding: '0.375rem 1rem' }}>
                            {result.appeal_output.appeal_recommendation === 'STRONG_APPEAL' ? '✅ File an Appeal — Strong Case' :
                             result.appeal_output.appeal_recommendation === 'APPEAL' ? '📋 Appeal Recommended' :
                             result.appeal_output.appeal_recommendation === 'EXCEPTION_REQUEST' ? '🔄 Formulary Exception Request' :
                             result.appeal_output.appeal_recommendation === 'UNLIKELY_TO_WIN' ? '⚠️ Unlikely to Win' :
                             '❌ Claim Correctly Denied'}
                          </span>
                        </div>
                      )}

                      {/* Policy Citations */}
                      {result.appeal_output.policy_citations?.length > 0 ? (
                        <div>
                          <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.875rem' }}>
                            📄 {result.appeal_output.policy_citations.length} Policy Clause{result.appeal_output.policy_citations.length !== 1 ? 's' : ''} Found
                          </p>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
                            {result.appeal_output.policy_citations.map((citation, i) => (
                              <div key={i} style={{ border: '1px solid var(--accent-border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
                                <div style={{
                                  background: 'var(--accent-subtle)',
                                  padding: '0.625rem 1rem',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '0.625rem',
                                  borderBottom: '1px solid var(--accent-border)',
                                }}>
                                  <span style={{
                                    fontFamily: "'JetBrains Mono', monospace",
                                    fontSize: '0.6875rem',
                                    fontWeight: 800,
                                    background: 'var(--accent)',
                                    color: '#fff',
                                    borderRadius: '0.375rem',
                                    padding: '0.125rem 0.5rem',
                                    letterSpacing: '0.04em',
                                    flexShrink: 0,
                                  }}>PAGE {citation.page_number}</span>
                                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent)' }}>Policy Contradiction</span>
                                </div>
                                <div style={{ padding: '1rem', background: 'var(--bg-card)' }}>
                                  <blockquote style={{
                                    borderLeft: '3px solid var(--accent)',
                                    paddingLeft: '1rem',
                                    margin: '0 0 1rem',
                                    fontStyle: 'italic',
                                    fontSize: '0.9375rem',
                                    color: 'var(--text-secondary)',
                                    lineHeight: 1.65,
                                  }}>
                                    "{citation.exact_clause_text}"
                                  </blockquote>
                                  {citation.insurer_mistake && (
                                    <div style={{
                                      background: 'var(--danger-bg)',
                                      border: '1px solid var(--danger-border)',
                                      borderRadius: 'var(--radius-sm)',
                                      padding: '0.625rem 0.875rem',
                                      fontSize: '0.875rem',
                                      color: 'var(--danger)',
                                      fontWeight: 600,
                                      lineHeight: 1.5,
                                      display: 'flex',
                                      alignItems: 'flex-start',
                                      gap: '0.5rem'
                                    }}>
                                      <IconAlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
                                      <span>Insurer Error: {citation.insurer_mistake}</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <p style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                          {result.appeal_output.contradiction_detected
                            ? '⚙️ Analysis complete — see assessment above.'
                            : '📋 No direct policy contradictions detected. Appeal relies on regulatory grounds.'}
                        </p>
                      )}
                    </div>
                  </motion.div>
                )}

                {result.appeal_output && (
                  <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}
                    className="card" style={{ marginTop: '1.5rem', marginBottom: '1.5rem', padding: '1.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-secondary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                      <div className="feature-icon" style={{ background: 'var(--info-bg)', color: 'var(--info)', border: '1px solid var(--info-border)' }}><IconServer size={20} /></div>
                      <div>
                        <h3 style={{ fontWeight: 800, color: 'var(--text-primary)', fontSize: '1.0625rem' }}>Agent 4: Denial Triage</h3>
                        <p style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>Determining liability: Provider Billing Error vs. Payer Violation</p>
                      </div>
                    </div>
                    
                    <div style={{ padding: '1.25rem', background: 'var(--bg-card)', border: '1px solid var(--border-primary)', borderRadius: '1rem', marginBottom: '1rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                        <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Triage Path</span>
                        <span className={`badge ${result.appeal_output.triage_path === 'PROVIDER_CODING_ERROR' ? 'badge-warning' : 'badge-danger'}`} style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                          <IconAlertTriangle size={14} />
                          {result.appeal_output.triage_path === 'PROVIDER_CODING_ERROR' ? 'PROVIDER CODING ERROR' : 'PAYER ILLEGAL DENIAL'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Confidence</span>
                        <span style={{ fontSize: '0.875rem', fontWeight: 700, color: result.appeal_output.triage_confidence === 'HIGH' ? 'var(--success)' : 'var(--warning)' }}>
                          {result.appeal_output.triage_confidence}
                        </span>
                      </div>
                    </div>
                    
                    <div style={{ background: 'var(--info-bg)', padding: '1.25rem', borderRadius: '1rem', borderLeft: '4px solid var(--info)' }}>
                      <p style={{ fontSize: '0.9375rem', color: 'var(--info)', fontWeight: 500, lineHeight: 1.6 }}>
                        {result.appeal_output.triage_action_summary}
                      </p>
                    </div>
                  </motion.div>
                )}

                {result.appeal_output && (
                  <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.3 }}
                    className="card" style={{ border: '2px solid var(--accent)', boxShadow: '0 8px 32px var(--accent-subtle)', padding: '2.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
                      <div className="feature-icon red" style={{ transform: 'scale(1.2)' }}><IconScale size={24} /></div>
                      <div>
                        <h3 style={{ fontWeight: 800, color: 'var(--accent)', fontSize: '1.25rem' }}>Agent 5: Appeal Letter</h3>
                        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Drafted with plan and legal references</p>
                      </div>
                    </div>

                    <div className="grid-2" style={{ gap: '1rem', marginBottom: '2rem' }}>
                      <div style={{ background: 'var(--bg-secondary)', padding: '1rem 1.25rem', borderRadius: '1rem', border: '1px solid var(--border-secondary)' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Framework</span>
                        <div className="badge badge-purple" style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', width: 'fit-content', marginTop: '0.5rem', padding: '0.375rem 0.75rem' }}>
                          <IconBriefcase size={14} /> {result.appeal_output.appeal_framework}
                        </div>
                      </div>
                      <div style={{ background: 'var(--bg-secondary)', padding: '1rem 1.25rem', borderRadius: '1rem', border: '1px solid var(--border-secondary)' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Deadline</span>
                        <div style={{ fontWeight: 800, color: result.appeal_output.days_remaining < 30 ? 'var(--danger)' : 'var(--text-primary)', marginTop: '0.5rem', fontSize: '1rem' }}>
                          {new Date(result.appeal_output.appeal_deadline).toLocaleDateString()} 
                          <span style={{ fontSize: '0.875rem', fontWeight: 600, opacity: 0.8, marginLeft: '0.5rem' }}>({result.appeal_output.days_remaining} days)</span>
                        </div>
                      </div>
                    </div>

                    <div className="appeal-letter-toolbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
                      <h4 style={{ fontSize: '0.875rem', fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Formal Appeal Letter</h4>
                      <div className="appeal-letter-actions" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        {letterActionStatus && <span style={{ fontSize: '0.75rem', color: 'var(--success)', fontWeight: 600, marginRight: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}><IconCheckCircle size={12} /> {letterActionStatus}</span>}
                        <button type="button" className="btn btn-outline" style={{ padding: '0.5rem 0.75rem', fontSize: '0.8125rem' }} onClick={handleCopyAppealLetter}><IconCopy size={16} /> Copy</button>
                        <button type="button" className="btn btn-outline" style={{ padding: '0.5rem 0.75rem', fontSize: '0.8125rem' }} onClick={handleDownloadAppealLetter}><IconDownload size={16} /> .txt</button>
                        <button 
                          type="button" 
                          className="btn btn-red" 
                          style={{ padding: '0.5rem 1rem', fontSize: '0.8125rem' }} 
                          onClick={() => navigate('/studio', { state: { 
                            letter: result.appeal_output.appeal_letter,
                            policyProfile,
                            claimCase: result.claim_case,
                            appealOutput: result.appeal_output,
                            eobHighlights: null, // Would come from ingestion phase in a full flow
                            costBreakdown: result.cost_breakdown
                          } })}
                        >
                          <IconWand size={16} /> Open in Appeal Studio <IconArrowRight size={16} />
                        </button>
                      </div>
                    </div>
                    <div className="appeal-letter" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-secondary)', padding: '2rem', borderRadius: '1rem', fontFamily: "'Merriweather', 'Times New Roman', serif", fontSize: '0.9375rem', lineHeight: 1.8, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
                      {result.appeal_output.appeal_letter}
                    </div>

                    {/* ── Next Steps ────────── */}
                    {result.appeal_output.recommended_next_steps?.length > 0 && (
                      <div style={{ marginTop: '2rem', background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', borderRadius: '1rem', padding: '1.5rem' }}>
                        <h4 style={{ fontSize: '0.875rem', fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>Recommended Next Steps</h4>
                        <ul className="next-steps-list" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                          {result.appeal_output.recommended_next_steps.map((step, i) => (
                            <li key={i} className="next-step-item" style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                              <span className="next-step-num" style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'var(--accent-subtle)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 800, flexShrink: 0 }}>{i + 1}</span>
                              <span style={{ fontSize: '0.9375rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{step}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </motion.div>
                )}

                {/* ── Appeal Roadmap ────────── */}
                {result.appeal_output && (
                  <div className="appeal-roadmap" style={{ marginTop: '2.5rem' }}>
                    <div className="appeal-roadmap-header" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
                      <div className="feature-icon red"><IconMap size={20} /></div>
                      <h4 style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--text-primary)' }}>Multi-Level Appeal Roadmap</h4>
                    </div>
                    <div className="appeal-roadmap-body" style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <div style={{ position: 'absolute', left: '24px', top: '24px', bottom: '24px', width: '2px', background: 'var(--border-secondary)', zIndex: 0 }} />
                      
                      {APPEAL_LEVELS.map((level, i) => (
                        <div key={i} className={`roadmap-level${i === 0 ? ' active' : (escalatedLevel === i + 1 && escalatedResult ? ' active' : '')}`} style={{ position: 'relative', zIndex: 1, display: 'flex', gap: '1.25rem', opacity: i === 0 || (escalatedLevel === i + 1 && escalatedResult) ? 1 : 0.6 }}>
                          <span className="roadmap-level-num" style={{ 
                            width: '48px', height: '48px', borderRadius: '50%', 
                            background: i === 0 || (escalatedLevel === i + 1 && escalatedResult) ? 'var(--accent)' : 'var(--bg-secondary)', 
                            color: i === 0 || (escalatedLevel === i + 1 && escalatedResult) ? '#fff' : 'var(--text-tertiary)',
                            border: `2px solid ${i === 0 || (escalatedLevel === i + 1 && escalatedResult) ? 'var(--accent)' : 'var(--border-secondary)'}`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center', 
                            fontSize: '1.125rem', fontWeight: 800, flexShrink: 0,
                            boxShadow: i === 0 || (escalatedLevel === i + 1 && escalatedResult) ? '0 4px 12px var(--accent-subtle)' : 'none',
                            transition: 'all var(--transition-fast)'
                          }}>{i + 1}</span>
                          <div className="roadmap-level-info" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-primary)', borderRadius: '1rem', padding: '1.5rem', flex: 1, boxShadow: i === 0 ? 'var(--shadow-sm)' : 'none' }}>
                            <h5 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.375rem' }}>{level.title}</h5>
                            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{level.desc}</p>
                            {i === 0 && (
                              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--success)', background: 'var(--success-bg)', border: '1px solid var(--success-border)', borderRadius: '999px', padding: '0.25rem 0.75rem', marginTop: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                                <IconCheckCircle size={14} /> Current — Letter Generated Above
                              </span>
                            )}
                            {(i === 1 || i === 2) && (
                              <div style={{ marginTop: '1rem' }}>
                                {escalatedLevel === i + 1 && escalatedLoading ? (
                                  <span style={{ fontSize: '0.8125rem', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600 }}><span className="spinner" style={{ width: '14px', height: '14px', borderWidth: '2px' }} /> Drafting...</span>
                                ) : escalatedLevel === i + 1 && escalatedResult ? (
                                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--success)', background: 'var(--success-bg)', border: '1px solid var(--success-border)', borderRadius: '999px', padding: '0.25rem 0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                                    <IconCheckCircle size={14} /> Letter Ready ↓
                                  </span>
                                ) : (
                                  <button
                                    type="button"
                                    className="btn btn-outline"
                                    style={{ fontSize: '0.8125rem', padding: '0.5rem 1rem' }}
                                    onClick={() => handleDraftEscalated(i + 1)}
                                    disabled={escalatedLoading}
                                  >
                                    <IconEdit size={14} /> Draft Level {i + 1} Letter
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Escalated letter output */}
                    {escalatedResult && (
                      <div style={{ marginTop: '2rem', borderTop: '2px dashed var(--border-secondary)', paddingTop: '2rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
                          <h5 style={{ fontWeight: 800, color: 'var(--accent)', fontSize: '1.125rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <IconFileText size={20} /> Level {escalatedResult.level}: {escalatedResult.level_name}
                          </h5>
                          <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <button type="button" className="btn btn-outline" style={{ fontSize: '0.8125rem', padding: '0.5rem 0.75rem' }}
                              onClick={() => navigator.clipboard.writeText(escalatedResult.appeal_letter || '')}><IconCopy size={16} /> Copy</button>
                            <button type="button" className="btn btn-outline" style={{ fontSize: '0.8125rem', padding: '0.5rem 0.75rem' }}
                              onClick={() => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([escalatedResult.appeal_letter || ''], { type: 'text/plain' })); a.download = `appeal-level${escalatedResult.level}.txt`; a.click() }}><IconDownload size={16} /> Download .txt</button>
                          </div>
                        </div>
                        {escalatedResult.deadline_date && (
                          <div style={{ fontSize: '0.875rem', color: 'var(--warning)', background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', borderRadius: '0.75rem', padding: '0.75rem 1rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
                            <IconAlertTriangle size={18} /> File by: <strong>{new Date(escalatedResult.deadline_date).toLocaleDateString()}</strong>
                          </div>
                        )}
                        <div className="appeal-letter" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-secondary)', padding: '2rem', borderRadius: '1rem', fontFamily: "'Merriweather', 'Times New Roman', serif", fontSize: '0.9375rem', lineHeight: 1.8, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
                          {escalatedResult.appeal_letter}
                        </div>
                        {escalatedResult.recommended_next_steps?.length > 0 && (
                          <div style={{ marginTop: '1.5rem', background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', borderRadius: '1rem', padding: '1.25rem' }}>
                            <h6 style={{ fontSize: '0.8125rem', fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1rem' }}>Next Steps</h6>
                            <ol style={{ paddingLeft: '1.25rem', fontSize: '0.875rem', color: 'var(--text-secondary)', listStyle: 'decimal', lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                              {escalatedResult.recommended_next_steps.map((s, i) => <li key={i}>{s}</li>)}
                            </ol>
                          </div>
                        )}
                        {escalatedError && (
                          <div style={{ padding: '0.75rem 1rem', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: '0.75rem', color: 'var(--danger)', fontSize: '0.875rem', marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
                            <IconAlertTriangle size={16} /> {escalatedError}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div className="card" style={{ padding: '4rem 2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <div style={{ width: '80px', height: '80px', borderRadius: '50%', background: 'var(--bg-secondary)', border: '1px solid var(--border-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1.5rem', color: 'var(--text-tertiary)' }}>
                  <IconZap size={40} />
                </div>
                <h3 style={{ fontWeight: 800, fontSize: '1.375rem', marginBottom: '0.5rem', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Ready to Evaluate</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem', maxWidth: '20rem', margin: '0 auto', lineHeight: 1.5 }}>
                  {policyProfile ? 'Describe your claim to run the cost engine.' : 'Upload a policy first.'}
                </p>
              </div>
            )}
          </motion.div>
        </div>
      </div>
    </section>
  )
}
