import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { apiFetch } from '../lib/api'
import { jsPDF } from 'jspdf'

const PROGRESS_STEPS = [
  { label: 'Normalizing claim' },
  { label: 'Running cost engine' },
  { label: 'Routing framework' },
  { label: 'Drafting appeal' },
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

export default function ClaimEvaluator({ policyProfile, onResult }) {
  const navigate = useNavigate()
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

  const handleEobUpload = async () => {
    if (!eobFile) return
    setEobLoading(true); setEobResult(null); setEobError(null)
    try {
      const formData = new FormData()
      formData.append('file', eobFile)
      const res = await apiFetch('/eob/parse', { method: 'POST', body: formData })
      const data = await res.json()
      if (data.success && data.extracted) {
        setEobResult(data.extracted)
      } else {
        setEobError(data.detail || 'EOB extraction failed.')
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

  const handleEvaluate = async () => {
    if (!policyProfile) { setError('Upload a policy first.'); return }
    if (claimText.trim().length < 20) { setError('Please describe the claim in more detail.'); return }
    setLoading(true); setError(null); setResult(null); setLetterActionStatus(''); setProgressStep(0)
    try {
      const res = await apiFetch('/claim/evaluate', { 
        method: 'POST', 
        body: JSON.stringify({
          claim_description: claimText,
          policy_profile: policyProfile,
          allowed_amount: allowedAmount ? Number(allowedAmount) : null,
        }) 
      })
      const data = await res.json()
      if (data.success && data.cost_breakdown) { setResult(data); onResult(data.cost_breakdown) }
      else { setError(data.errors?.join(', ') || 'Evaluation failed') }
    } catch (err) { setError(`Network error: ${err.message}`) }
    finally { setLoading(false) }
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
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Provider search failed')
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
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Network status check failed')
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

  const loadSample = (type) => {
    if (type === 'approved') {
      setClaimText("I went to my in-network doctor for a routine office visit because I had a bad cold. The bill was $250.")
      setAllowedAmount('160')
    } else if (type === 'nsa') {
      setClaimText("I went to the ER at City Hospital because of severe chest pain. The hospital is out-of-network. They billed $15,000.")
      setAllowedAmount('1200')
    } else {
      setClaimText("I had an MRI on my right knee. My insurance denied it saying it wasn't medically necessary (Code CO-50). The facility billed $3,500. No prior authorization was done.")
      setAllowedAmount('')
    }
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
            Describe your medical encounter. The deterministic engine calculates your exact cost, and if denied, the AI drafts an appeal letter.
          </motion.p>
        </motion.div>

        {!policyProfile && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
            style={{ marginBottom: '2rem', padding: '1.25rem 1.5rem', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h4 style={{ fontWeight: 700, color: '#92400e', fontSize: '0.9375rem', marginBottom: '0.25rem' }}>⚠️ Policy Required</h4>
              <p style={{ color: '#a16207', fontSize: '0.8125rem', fontWeight: 500 }}>Upload your policy first for accurate cost calculations.</p>
            </div>
            <button className="btn btn-red" style={{ flexShrink: 0 }} onClick={() => navigate('/policy')}>Upload Policy →</button>
          </motion.div>
        )}

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
          className="card" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start', marginBottom: '1rem', flexWrap: 'wrap' }}>
            <div>
              <h2 style={{ fontSize: '1.125rem', fontWeight: 800, color: '#09090b', marginBottom: '0.25rem' }}>Provider & Facility Network Check</h2>
              <p style={{ fontSize: '0.8125rem', color: '#71717a', maxWidth: '44rem' }}>
                Search the CMS NPPES registry for real US doctors and hospitals, then estimate network status against your loaded plan before planned non-emergency care.
              </p>
            </div>
            <span className="badge badge-info">CMS NPPES</span>
          </div>

          <div className="grid-4" style={{ gap: '0.75rem', marginBottom: '0.75rem' }}>
            <input className="input" placeholder="Last name or facility" value={providerSearch.last_name}
              onChange={e => setProviderSearch(prev => ({ ...prev, last_name: e.target.value }))} />
            <input className="input" placeholder="Specialty" value={providerSearch.taxonomy_description}
              onChange={e => setProviderSearch(prev => ({ ...prev, taxonomy_description: e.target.value }))} />
            <input className="input" placeholder="City" value={providerSearch.city}
              onChange={e => setProviderSearch(prev => ({ ...prev, city: e.target.value }))} />
            <input className="input" placeholder="State" maxLength={2} value={providerSearch.state}
              onChange={e => setProviderSearch(prev => ({ ...prev, state: e.target.value.toUpperCase() }))} />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: '#3f3f46', fontWeight: 600 }}>
              <input type="checkbox" checked={providerSearch.is_facility}
                onChange={e => setProviderSearch(prev => ({ ...prev, is_facility: e.target.checked }))} />
              Search hospitals / facilities
            </label>
            <button className="btn btn-red" onClick={handleProviderSearch} disabled={providerLoading}>
              {providerLoading ? <><span className="spinner" /> Searching...</> : 'Search Providers'}
            </button>
          </div>

          <p style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: '#71717a', lineHeight: 1.5 }}>
            Network data is an estimate unless your insurer confirms it. For emergencies and certain surprise out-of-network bills, the No Surprises Act may cap patient cost-sharing at in-network amounts.
          </p>

          {providerError && (
            <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.75rem', color: '#dc2626', fontSize: '0.8125rem', fontWeight: 500 }}>
              {providerError}
            </div>
          )}

          {providerResults.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
              {providerResults.map(provider => {
                const network = networkChecks[provider.npi]
                return (
                  <div key={provider.npi} style={{ border: '1px solid #e4e4e7', borderRadius: '0.75rem', padding: '1rem', background: '#fafafa' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                      <div>
                        <h3 style={{ fontSize: '0.9375rem', fontWeight: 800, color: '#09090b' }}>{provider.name}</h3>
                        <p style={{ fontSize: '0.8125rem', color: '#52525b', marginTop: '0.25rem' }}>
                          NPI {provider.npi} · {provider.primary_specialty}
                        </p>
                        {provider.address && (
                          <p style={{ fontSize: '0.75rem', color: '#71717a', marginTop: '0.25rem' }}>
                            {provider.address.address_1}, {provider.address.city}, {provider.address.state} {provider.address.postal_code}
                          </p>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                        <button className="btn btn-ghost" onClick={() => handleNetworkCheck(provider)} disabled={!policyProfile || network?.loading}>
                          {network?.loading ? 'Checking...' : 'Check Network'}
                        </button>
                        <button className="btn btn-ghost" onClick={() => addProviderToClaim(provider)}>Use in Claim</button>
                      </div>
                    </div>
                    {network?.result && (
                      <div style={{ marginTop: '0.75rem', fontSize: '0.8125rem', color: '#3f3f46', whiteSpace: 'pre-wrap' }}>
                        {network.result}
                      </div>
                    )}
                    {network?.error && (
                      <div style={{ marginTop: '0.75rem', fontSize: '0.8125rem', color: '#dc2626' }}>{network.error}</div>
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
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                <div className="feature-icon emerald">🧾</div>
                <div>
                  <h3 style={{ fontWeight: 700, fontSize: '1rem', color: '#09090b' }}>Claim Details</h3>
                  <p style={{ fontSize: '0.8125rem', color: '#a1a1aa' }}>Describe the service, diagnosis, and billing</p>
                </div>
              </div>

              {/* ── EOB Upload Panel ───────────── */}
              <div className="guided-form-panel" style={{ marginBottom: '1rem' }}>
                <div className={`guided-form-header${eobResult ? ' open' : ''}`}
                  onClick={() => !eobResult && document.getElementById('eob-upload-input').click()}
                  style={{ cursor: eobResult ? 'default' : 'pointer' }}
                >
                  <span className="guided-form-title">
                    📄 Upload EOB PDF
                    <span style={{ fontSize: '0.6875rem', color: '#a1a1aa', fontWeight: 500 }}> — auto-fill from your Explanation of Benefits</span>
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
                  {!eobFile && <span style={{ fontSize: '0.75rem', color: '#dc2626', fontWeight: 600 }}>Click to select PDF</span>}
                </div>
                <input
                  id="eob-upload-input"
                  type="file"
                  accept="application/pdf"
                  style={{ display: 'none' }}
                  onChange={e => { setEobFile(e.target.files[0] || null); setEobResult(null); setEobError(null) }}
                />
                {eobFile && !eobResult && (
                  <div style={{ padding: '0.75rem 1rem', fontSize: '0.8125rem', color: '#52525b', display: 'flex', alignItems: 'center', gap: '0.5rem', borderTop: '1px solid #f4f4f5' }}>
                    📄 <strong>{eobFile.name}</strong>
                    <button type="button" onClick={() => setEobFile(null)} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#a1a1aa', cursor: 'pointer', fontSize: '0.75rem' }}>✕ Remove</button>
                  </div>
                )}
                {eobError && (
                  <div style={{ padding: '0.75rem 1rem', fontSize: '0.8125rem', color: '#dc2626', borderTop: '1px solid #fecaca', background: '#fef2f2' }}>❌ {eobError}</div>
                )}
                {eobResult && (
                  <div style={{ padding: '1rem' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginBottom: '1rem' }}>
                      {[
                        ['Date of Service', eobResult.date_of_service, eobResult.confidence?.date_of_service],
                        ['Provider', eobResult.provider_name, 'high'],
                        ['Facility', eobResult.facility_name, 'high'],
                        ['CPT Code', eobResult.cpt_code, eobResult.confidence?.cpt_code],
                        ['ICD-10', eobResult.icd_10_code, 'high'],
                        ['Billed Amount', eobResult.billed_amount != null ? `$${Number(eobResult.billed_amount).toLocaleString()}` : null, eobResult.confidence?.billed_amount],
                        ['Allowed Amount', eobResult.allowed_amount != null ? `$${Number(eobResult.allowed_amount).toLocaleString()}` : null, eobResult.confidence?.allowed_amount],
                        ['Patient Responsibility', eobResult.patient_responsibility != null ? `$${Number(eobResult.patient_responsibility).toLocaleString()}` : null, 'high'],
                        ['CARC Code', eobResult.denial_carc_code, eobResult.confidence?.denial_carc_code],
                        ['Denial Date', eobResult.denial_date, 'high'],
                      ].filter(([, val]) => val != null).map(([label, val, conf]) => (
                        <div key={label} style={{ background: '#fafafa', border: '1px solid #f4f4f5', borderRadius: '0.625rem', padding: '0.5rem 0.75rem' }}>
                          <div style={{ fontSize: '0.65rem', fontWeight: 700, color: '#71717a', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.1rem', display: 'flex', justifyContent: 'space-between' }}>
                            {label}
                            {conf === 'low' && <span style={{ color: '#d97706', fontSize: '0.6rem' }}>⚠ verify</span>}
                          </div>
                          <div style={{ fontSize: '0.875rem', fontWeight: 600, color: '#09090b' }}>{val}</div>
                        </div>
                      ))}
                    </div>
                    {eobResult.denial_reason_text && (
                      <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.75rem', padding: '0.75rem 1rem', fontSize: '0.8125rem', color: '#dc2626', marginBottom: '1rem' }}>
                        <strong>Denial reason:</strong> {eobResult.denial_reason_text}
                      </div>
                    )}
                    <div style={{ display: 'flex', gap: '0.75rem' }}>
                      <button type="button" className="btn btn-red" style={{ flex: 1 }} onClick={() => prefillFromEob(eobResult)}>
                        ✅ Pre-fill Claim Description →
                      </button>
                      <button type="button" className="btn btn-ghost" onClick={() => { setEobResult(null); setEobFile(null) }}>Clear</button>
                    </div>
                  </div>
                )}
              </div>

              <textarea value={claimText} onChange={e => setClaimText(e.target.value)}
                placeholder="e.g., I went to the ER for chest pain on July 1st. The hospital billed $15,000..."
                style={{ minHeight: '140px', marginBottom: '1rem' }} disabled={!policyProfile}
              />

              <label style={{ display: 'block', marginBottom: '1rem' }}>
                <span style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 700, color: '#3f3f46', marginBottom: '0.375rem' }}>
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
                <span style={{ display: 'block', fontSize: '0.75rem', color: '#71717a', lineHeight: 1.5, marginTop: '0.375rem' }}>
                  Use the allowed amount, plan discount, or approved amount from your EOB. If left blank, PolicyCrab labels the result as an estimate and does not assume a negotiated rate.
                </span>
              </label>

              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
                {[['In-Network Visit', 'approved'], ['OON Emergency (NSA)', 'nsa'], ['Denied MRI', 'denied']].map(([l, t]) => (
                  <button key={t} className="btn btn-ghost" style={{ fontSize: '0.75rem', padding: '0.375rem 0.75rem' }} onClick={() => loadSample(t)} disabled={!policyProfile}>
                    {l}
                  </button>
                ))}
              </div>

              {/* ── Guided Form ────────────── */}
              <div className="guided-form-panel">
                <div className={`guided-form-header${guidedOpen ? ' open' : ''}`} onClick={() => setGuidedOpen(o => !o)}>
                  <span className="guided-form-title">📝 Guided Intake Fields <span style={{ fontSize: '0.6875rem', color: '#a1a1aa', fontWeight: 500 }}>(optional)</span></span>
                  <span style={{ fontSize: '0.75rem', color: '#a1a1aa' }}>{guidedOpen ? '▲' : '▼'}</span>
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
                      <select value={guided.denial_reason} onChange={e => setGuided(p => ({ ...p, denial_reason: e.target.value }))}>
                        {DENIAL_REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                      </select>
                    </div>
                    <div className="guided-field">
                      <label>CARC / RARC Code</label>
                      <input className="input" placeholder="e.g., CO-50" value={guided.carc_code} onChange={e => setGuided(p => ({ ...p, carc_code: e.target.value }))} />
                    </div>
                    <div className="guided-form-build">
                      <button className="btn btn-ghost" type="button" onClick={buildFromGuided}>Add to Claim Description →</button>
                    </div>
                  </div>
                )}
              </div>

              <button className="btn btn-red" onClick={handleEvaluate} disabled={loading || !policyProfile || claimText.trim().length < 20} style={{ width: '100%' }}>
                {loading ? <><span className="spinner" /> Evaluating Pipeline...</> : '⚡ Run Evaluation'}
              </button>

              {/* ── Progress Stepper ────────── */}
              {loading && (
                <div className="claim-progress" style={{ marginTop: '1rem' }}>
                  <span className="claim-progress-title">Pipeline Progress</span>
                  <div className="claim-progress-steps">
                    {PROGRESS_STEPS.map((s, i) => (
                      <div key={i} className={`progress-step${i < progressStep ? ' done' : i === progressStep ? ' active' : ''}`}>
                        <div className="progress-step-dot">{i < progressStep ? '✓' : i + 1}</div>
                        <span className="progress-step-label">{s.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {error && (
                <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.75rem', color: '#dc2626', fontSize: '0.8125rem', fontWeight: 500 }}>
                  ❌ {error}
                </div>
              )}
            </div>

            {result?.claim_case && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
                className="card card-zinc" style={{ marginTop: '1.5rem', padding: '1.5rem' }}>
                <h4 style={{ fontWeight: 700, fontSize: '0.9375rem', marginBottom: '0.75rem' }}>Agent 2: Normalized Intake</h4>
                {[
                  ['CPT Code', `${result.claim_case.cpt_code} — ${result.claim_case.cpt_description}`],
                  ['ICD-10', result.claim_case.icd_10_code],
                  ['Network', result.claim_case.network_status],
                  ['Emergency', result.claim_case.is_emergency ? '✅ Yes' : '❌ No'],
                ].map(([l, v]) => <div className="result-row" key={l}><span className="result-label">{l}</span><span className="result-value">{v}</span></div>)}
                {result.claim_case.nsa_applies && (
                  <div style={{ marginTop: '0.5rem' }}><span className="badge badge-purple">⚖️ No Surprises Act Applies</span></div>
                )}
              </motion.div>
            )}
          </motion.div>

          {/* ── Results ────────────────── */}
          <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.55, delay: 0.25 }}>
            {result ? (
              <>
                <div className="results-panel" style={{ marginBottom: '1.5rem' }}>
                  <div className="results-header">
                    <h3 style={{ fontWeight: 700, fontSize: '1rem' }}>Cost Breakdown</h3>
                    {result.route_decision === 'denied' ? <span className="badge badge-danger">Denied</span> : <span className="badge badge-success">Approved</span>}
                  </div>
                  <div className="results-body">
                    {[
                      ['Billed Amount', `$${result.cost_breakdown.billed_amount?.toLocaleString()}`, ''],
                      ['Allowed Amount', `$${result.cost_breakdown.allowed_amount?.toLocaleString()}`, ''],
                      ['Applied to Deductible', `$${result.cost_breakdown.applied_to_deductible?.toLocaleString()}`, ''],
                      ['Coinsurance', `$${result.cost_breakdown.coinsurance_amount?.toLocaleString()}`, ''],
                    ].map(([l, v]) => <div className="result-row" key={l}><span className="result-label">{l}</span><span className="result-value">{v}</span></div>)}

                    <div style={{ height: '1px', background: '#e4e4e7', margin: '0.75rem 0' }} />

                    <div style={{ marginBottom: '0.75rem' }}>
                      {result.cost_breakdown.allowed_amount_source === 'eob'
                        ? <span className="badge badge-success">EOB-based allowed amount</span>
                        : <span className="badge badge-warning">Estimate: no EOB allowed amount</span>}
                    </div>

                    <div className="result-row">
                      <span className="result-label" style={{ fontWeight: 700, color: '#09090b' }}>Your Total Responsibility</span>
                      <span className="result-value money" style={{ fontSize: '1.25rem' }}>${result.cost_breakdown.total_patient_responsibility?.toLocaleString()}</span>
                    </div>
                    <div className="result-row">
                      <span className="result-label">Insurer Pays</span>
                      <span className="result-value">${result.cost_breakdown.total_insurer_payout?.toLocaleString()}</span>
                    </div>
                  </div>
                </div>

                {result.cost_breakdown?.calculation_notes?.length > 0 && (
                  <div className="card card-zinc" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
                    <h4 style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#71717a', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Waterfall Notes</h4>
                    <ul style={{ fontSize: '0.8125rem', paddingLeft: '1.25rem', listStyle: 'disc', color: '#3f3f46' }}>
                      {result.cost_breakdown.calculation_notes.map((n, i) => <li key={i} style={{ marginBottom: '0.25rem' }}>{n}</li>)}
                    </ul>
                  </div>
                )}

                {result.explanation && (
                  <div className="explanation-box" style={{ marginBottom: result.appeal_output ? '1.5rem' : 0 }}>
                    <h4>💡 Plain English Summary</h4>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{result.explanation}</div>
                  </div>
                )}

                {result.appeal_output && (
                  <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
                    className="card" style={{ border: '1px solid #dc2626', boxShadow: '0 4px 24px rgba(220,38,38,0.15)', padding: '2rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
                      <div className="feature-icon red">⚖️</div>
                      <div>
                        <h3 style={{ fontWeight: 800, color: '#dc2626', fontSize: '1.125rem' }}>Agent 3: Appeal Letter</h3>
                        <p style={{ fontSize: '0.8125rem', color: '#a1a1aa' }}>RAG-powered regulatory response</p>
                      </div>
                    </div>

                    <div className="grid-2" style={{ gap: '0.75rem', marginBottom: '1.5rem' }}>
                      <div style={{ background: '#fafafa', padding: '0.75rem 1rem', borderRadius: '0.75rem' }}>
                        <span style={{ fontSize: '0.75rem', color: '#71717a', fontWeight: 500 }}>Framework</span>
                        <div className="badge badge-purple" style={{ display: 'block', width: 'fit-content', marginTop: '0.25rem' }}>{result.appeal_output.appeal_framework}</div>
                      </div>
                      <div style={{ background: '#fafafa', padding: '0.75rem 1rem', borderRadius: '0.75rem' }}>
                        <span style={{ fontSize: '0.75rem', color: '#71717a', fontWeight: 500 }}>Deadline</span>
                        <div style={{ fontWeight: 700, color: result.appeal_output.days_remaining < 30 ? '#dc2626' : '#09090b', marginTop: '0.25rem', fontSize: '0.875rem' }}>
                          {new Date(result.appeal_output.appeal_deadline).toLocaleDateString()} ({result.appeal_output.days_remaining} days)
                        </div>
                      </div>
                    </div>

                    <div className="appeal-letter-toolbar">
                      <h4 style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#71717a', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Formal Appeal Letter</h4>
                      <div className="appeal-letter-actions">
                        {letterActionStatus && <span>{letterActionStatus}</span>}
                        <button type="button" className="btn btn-ghost" onClick={handleCopyAppealLetter}>Copy Letter</button>
                        <button type="button" className="btn btn-ghost" onClick={handleDownloadAppealLetter}>Download .txt</button>
                        <button type="button" className="btn btn-red" onClick={handleDownloadPDF}>Download PDF</button>
                      </div>
                    </div>
                    <div className="appeal-letter">{result.appeal_output.appeal_letter}</div>

                    {/* ── Next Steps ────────── */}
                    {result.appeal_output.recommended_next_steps?.length > 0 && (
                      <div style={{ marginTop: '1.5rem' }}>
                        <h4 style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#71717a', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>Recommended Next Steps</h4>
                        <ul className="next-steps-list">
                          {result.appeal_output.recommended_next_steps.map((step, i) => (
                            <li key={i} className="next-step-item">
                              <span className="next-step-num">{i + 1}</span>
                              <span>{step}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </motion.div>
                )}

                {/* ── Appeal Roadmap ────────── */}
                {result.appeal_output && (
                  <div className="appeal-roadmap">
                    <div className="appeal-roadmap-header">
                      <div className="feature-icon red">🗺️</div>
                      <h4>Multi-Level Appeal Roadmap</h4>
                    </div>
                    <div className="appeal-roadmap-body">
                      {APPEAL_LEVELS.map((level, i) => (
                        <div key={i} className={`roadmap-level${i === 0 ? ' active' : ''}`}>
                          <span className="roadmap-level-num">{i + 1}</span>
                          <div className="roadmap-level-info">
                            <h5>{level.title}</h5>
                            <p>{level.desc}</p>
                          </div>
                        </div>
                      ))}
                      <p style={{ fontSize: '0.75rem', color: '#a1a1aa', marginTop: '0.5rem', lineHeight: 1.5 }}>
                        The appeal letter above is for Level 1 (Internal Appeal). If denied again, escalate to the next level.
                      </p>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="card" style={{ padding: '4rem 2rem', textAlign: 'center' }}>
                <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⚡</div>
                <h3 style={{ fontWeight: 800, fontSize: '1.25rem', marginBottom: '0.5rem' }}>Ready to Evaluate</h3>
                <p style={{ color: '#71717a', fontSize: '0.875rem', maxWidth: '20rem', margin: '0 auto' }}>
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
