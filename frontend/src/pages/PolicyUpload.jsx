import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { apiFetch, formatApiError, readApiResponse } from '../lib/api'
import { useNavigate } from 'react-router-dom'
import { IconFileText, IconCheckCircle, IconUpload, IconSearch, IconFolder, IconX, IconAlertTriangle } from '../components/Icons'
import AILogViewer from '../components/AILogViewer'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }
const MAX_POLICIES = 5

// Editable numeric field row
function EditableNumericField({ label, field, value, onChange, isDefaulted, prefix = '$' }) {
  return (
    <div className="policy-editable-field">
      <div className="policy-editable-label">
        <span>{label}</span>
        {isDefaulted && <span className="defaulted-tag">ESTIMATED</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
        {prefix && <span style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>{prefix}</span>}
        <input
          className={`policy-field-input${isDefaulted ? ' defaulted' : ''}`}
          type="number"
          min="0"
          step="0.01"
          value={value ?? ''}
          onChange={e => onChange(field, e.target.value === '' ? null : Number(e.target.value))}
        />
      </div>
    </div>
  )
}

function EditableTextField({ label, field, value, onChange, isDefaulted }) {
  return (
    <div className="policy-editable-field">
      <div className="policy-editable-label">
        <span>{label}</span>
        {isDefaulted && <span className="defaulted-tag">ESTIMATED</span>}
      </div>
      <input
        className={`policy-field-input${isDefaulted ? ' defaulted' : ''}`}
        type="text"
        value={value ?? ''}
        onChange={e => onChange(field, e.target.value)}
      />
    </div>
  )
}

function EditableSelectField({ label, field, value, onChange, options }) {
  return (
    <div className="policy-editable-field">
      <div className="policy-editable-label">
        <span>{label}</span>
      </div>
      <select
        className="policy-field-input"
        value={value ?? ''}
        onChange={e => onChange(field, e.target.value)}
        style={{ fontFamily: 'Inter, system-ui, sans-serif', appearance: 'auto' }}
      >
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

export default function PolicyUpload({ onPolicyParsed }) {
  const navigate = useNavigate()
  const [policyText, setPolicyText] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Editable profile state
  const [editableProfile, setEditableProfile] = useState(null)
  const [confirmed, setConfirmed] = useState(false)

  // Saved policies state
  const [savedPolicies, setSavedPolicies] = useState([])
  const [policiesLoading, setPoliciesLoading] = useState(true)
  const [deletingId, setDeletingId] = useState(null)

  // Fetch saved policies on mount
  const fetchPolicies = useCallback(async () => {
    try {
      setPoliciesLoading(true)
      const res = await apiFetch('/history/policies')
      const data = await readApiResponse(res)
      setSavedPolicies(Array.isArray(data) ? data : [])
    } catch {
      // Silently fail — saved policies are a convenience feature
    } finally {
      setPoliciesLoading(false)
    }
  }, [])

  useEffect(() => { fetchPolicies() }, [fetchPolicies])

  const handleDeletePolicy = async (policyId) => {
    if (!confirm('Delete this saved policy? This cannot be undone.')) return
    setDeletingId(policyId)
    try {
      await apiFetch(`/history/policies/${policyId}`, { method: 'DELETE' })
      setSavedPolicies(prev => prev.filter(p => p.id !== policyId))
    } catch {
      setError('Failed to delete policy. Please try again.')
    } finally {
      setDeletingId(null)
    }
  }

  const handleLoadSaved = (policy) => {
    const profile = policy.policy_profile
    if (!profile) return
    setEditableProfile({ ...profile })
    setResult({
      policy_profile: profile,
      extraction_confidence: 'HIGH',
      session_id: policy.session_id,
      policy_indexed: Boolean(policy.session_id),
    })
    setConfirmed(false)
    setError(null)
  }

  const handleFieldChange = (field, value) => {
    setEditableProfile(prev => ({ ...prev, [field]: value }))
    setConfirmed(false)
  }

  const handleCopayChange = (key, value) => {
    setEditableProfile(prev => ({
      ...prev,
      copay_schedule: { ...prev.copay_schedule, [key]: value === '' ? null : Number(value) },
    }))
    setConfirmed(false)
  }

  const handleConfirm = () => {
    onPolicyParsed(editableProfile, {
      session_id: result?.session_id || null,
      policy_indexed: Boolean(result?.policy_indexed),
    })
    setConfirmed(true)
  }

  const handleUpload = async () => {
    if (!selectedFile && policyText.trim().length < 50) {
      setError('Please upload a PDF or paste at least 50 characters of policy text.')
      return
    }

    setLoading(true); setError(null); setResult(null); setEditableProfile(null); setConfirmed(false)

    try {
      let res;
      if (selectedFile) {
        const formData = new FormData()
        formData.append('file', selectedFile)
        res = await apiFetch('/policy/upload-pdf', { method: 'POST', body: formData })
      } else {
        res = await apiFetch('/policy/upload', {
          method: 'POST',
          body: JSON.stringify({ policy_text: policyText })
        })
      }

      const data = await readApiResponse(res)
      if (data?.success && data.policy_profile) {
        setResult(data)
        setEditableProfile({ ...data.policy_profile })
        if (data.extracted_text) setPolicyText(data.extracted_text)
        // Refresh saved policies list
        fetchPolicies()
      } else if (data?.session_id && data.policy_indexed) {
        setResult(data)
        setError(formatApiError(data, 'Policy details were saved, but the summary could not be completed.'))
      } else {
        setError(formatApiError(data, 'We could not read this policy. Please try again.'))
      }
    } catch (err) {
      setError(`We could not reach the server: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const confidenceClass = result?.extraction_confidence
    ? `confidence-badge-${result.extraction_confidence}`
    : null

  const sampleSBC = `Blue Shield PPO Gold Plan\nCarrier: Blue Shield of California\nPlan Type: PPO (Preferred Provider Organization)\nLegal Status: Fully Insured, regulated by California Department of Insurance\nState: CA\n\nIn-Network Benefits:\n- Annual Deductible (Individual): $1,500\n- Annual Deductible (Family): $3,000\n- Out-of-Pocket Maximum (Individual): $6,000\n- Out-of-Pocket Maximum (Family): $12,000\n- Coinsurance: You pay 20%, Plan pays 80% after deductible\n\nOut-of-Network Benefits:\n- Annual Deductible: $3,000\n- Out-of-Pocket Maximum: $12,000\n- Coinsurance: You pay 40%, Plan pays 60%\n\nCopays:\n- Primary Care Visit: $25\n- Specialist Visit: $50\n- Urgent Care: $75\n- Emergency Room: $250 (waived if admitted)\n- Generic Rx: $10\n- Preferred Brand Rx: $35\n- Specialty Rx: 20% coinsurance\n\nPlan Features:\n- HSA Eligible: No\n- PCP Referral Required: No (PPO)\n- Prior Authorization Required: Elective surgery, advanced imaging (MRI, CT, PET), specialty drugs\n- Essential Health Benefits: All 10 ACA categories covered\n\nExcluded Services: Cosmetic surgery, experimental treatments, long-term custodial care`

  return (
    <section className="section-white section-pad">
      <div className="main">
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }}>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label">
            <span className="line" /> Step 1
          </motion.p>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.55 }} className="section-title">
            Upload your <span className="gradient-text">policy document</span>
          </motion.h1>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-subtitle" style={{ marginBottom: '3rem' }}>
            Upload your plan summary or paste the text. Review the extracted details before evaluating a claim.
          </motion.p>
        </motion.div>

        <div className="grid-2" style={{ alignItems: 'start' }}>
          {/* ── Input ─────────────────── */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
            <div className="card" style={{ padding: '2rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                <div className="feature-icon red"><IconFileText size={20} /></div>
                <div>
                  <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Policy Document</h3>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Upload the pages with costs, coverage, or denial details</p>
                </div>
              </div>

              <div style={{ background: 'var(--info-bg)', border: '1px solid var(--info-border)', borderRadius: '0.75rem', padding: '1.25rem', marginBottom: '1.5rem', fontSize: '0.8125rem', color: 'var(--info)' }}>
                <strong style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', fontSize: '0.875rem' }}>
                  <IconCheckCircle size={16} /> What pages should I upload?
                </strong>
                <div style={{ display: 'grid', gap: '0.875rem' }}>
                  {[
                    ['SBC or plan summary', 'Look for pages labeled deductible, out-of-pocket maximum, copay, coinsurance, exclusions, prior authorization, or network benefits.'],
                    ['EOB or claim letter', 'Use pages with billed amount, allowed amount, plan paid, patient responsibility, denial reason, CPT/ICD codes, and appeal deadline.'],
                    ['Skip when possible', 'Avoid full ID cards, blank forms, duplicate pages, and unrelated medical records. Redact SSNs or member IDs before uploading.'],
                  ].map(([title, body]) => (
                    <div key={title} style={{ display: 'grid', gridTemplateColumns: '6px 1fr', gap: '0.625rem', alignItems: 'start' }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'currentColor', marginTop: '0.35rem', opacity: 0.5 }} />
                      <span><strong>{title}:</strong> {body}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ marginBottom: '1.5rem', background: 'var(--bg-secondary)', border: '1px dashed var(--border-primary)', borderRadius: '1rem', padding: '1.5rem', textAlign: 'center', transition: 'all var(--transition-fast)' }}
                   onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                   onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-primary)'}>
                <input
                  type="file"
                   accept=".pdf,application/pdf"
                  onChange={e => setSelectedFile(e.target.files[0])}
                  style={{ display: 'none' }}
                  id="pdf-upload"
                />
                <label htmlFor="pdf-upload" style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{ width: '48px', height: '48px', background: 'var(--bg-primary)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: 'var(--shadow-sm)', color: 'var(--accent)' }}>
                    <IconUpload size={24} />
                  </div>
                  <span style={{ fontWeight: 600, color: 'var(--accent)', fontSize: '0.9375rem' }}>
                    {selectedFile ? selectedFile.name : 'Click to select a PDF'}
                  </span>
                  {!selectedFile && <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Max size: 10MB</span>}
                </label>
                {selectedFile && (
                  <button onClick={() => setSelectedFile(null)} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '0.75rem', cursor: 'pointer', textDecoration: 'underline' }}>
                    Clear selection
                  </button>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', margin: '1.5rem 0' }}>
                <div style={{ height: '1px', flex: 1, background: 'var(--border-primary)' }} />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>OR PASTE TEXT</span>
                <div style={{ height: '1px', flex: 1, background: 'var(--border-primary)' }} />
              </div>

              <textarea
                className="input"
                value={policyText}
                onChange={e => { setPolicyText(e.target.value); setSelectedFile(null); }}
                placeholder="Paste your insurance policy document text here..."
                style={{ minHeight: '180px', marginBottom: '1.5rem' }}
                disabled={!!selectedFile}
              />

              <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
                <button className="btn btn-red" style={{ flex: 1 }} onClick={handleUpload} disabled={loading || (!selectedFile && policyText.trim().length < 50)}>
                  {loading ? <><span className="spinner" /> Analyzing...</> : <><IconSearch size={18} /> Analyze Policy</>}
                </button>
                <button className="btn btn-outline" onClick={() => { setPolicyText(sampleSBC); setSelectedFile(null); }}>
                  <IconFileText size={18} /> Sample Text
                </button>
              </div>

              {error && (
                <div style={{ marginTop: '1rem', padding: '0.875rem 1rem', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: '0.75rem', color: 'var(--danger)', fontSize: '0.875rem', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <IconAlertTriangle size={18} /> {error}
                </div>
              )}

              {loading && (
                <div style={{ marginTop: '1rem' }}>
                  <AILogViewer task="extraction" active={loading} />
                </div>
              )}
            </div>

            {/* ── Saved Policies Panel ────────────── */}
            <div className="card" style={{ padding: '1.5rem', marginTop: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                  <IconFolder size={20} style={{ color: 'var(--text-secondary)' }} />
                  <h3 style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--text-primary)' }}>Saved Policies</h3>
                </div>
                <span style={{
                  fontSize: '0.6875rem', fontWeight: 700, padding: '0.25rem 0.625rem',
                  borderRadius: '999px',
                  background: savedPolicies.length >= MAX_POLICIES ? 'var(--danger-bg)' : 'var(--bg-secondary)',
                  color: savedPolicies.length >= MAX_POLICIES ? 'var(--danger)' : 'var(--text-secondary)',
                  border: `1px solid ${savedPolicies.length >= MAX_POLICIES ? 'var(--danger-border)' : 'var(--border-primary)'}`,
                }}>
                  {savedPolicies.length} / {MAX_POLICIES} slots
                </span>
              </div>

              {policiesLoading ? (
                <div style={{ textAlign: 'center', padding: '2rem 1.5rem', color: 'var(--text-tertiary)', fontSize: '0.875rem' }}>
                  <span className="spinner" style={{ marginRight: '0.5rem', borderColor: 'var(--border-primary)', borderTopColor: 'var(--text-tertiary)' }} /> Loading...
                </div>
              ) : savedPolicies.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem 1.5rem', color: 'var(--text-tertiary)', fontSize: '0.875rem' }}>
                  No saved policies yet. Upload one above to get started.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {savedPolicies.map(p => {
                    const profile = p.policy_profile
                    const name = profile?.plan_name || 'Unnamed Policy'
                    const carrier = profile?.carrier_name || ''
                    const planType = profile?.plan_type || ''
                    const date = p.created_at ? new Date(p.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''
                    return (
                      <div key={p.id} style={{
                        display: 'flex', alignItems: 'center', gap: '0.75rem',
                        padding: '0.75rem 1rem', borderRadius: '0.75rem',
                        background: 'var(--bg-secondary)', border: '1px solid var(--border-secondary)',
                        transition: 'border-color var(--transition-fast)',
                      }}
                        onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border-primary)'}
                        onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-secondary)'}
                      >
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <p style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {name}
                          </p>
                          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                            {[carrier, planType, date].filter(Boolean).join(' · ')}
                          </p>
                        </div>
                        <button
                          onClick={() => handleLoadSaved(p)}
                          className="btn btn-outline"
                          style={{
                            padding: '0.375rem 0.75rem', fontSize: '0.75rem',
                          }}
                        >
                          Load
                        </button>
                        <button
                          onClick={() => handleDeletePolicy(p.id)}
                          disabled={deletingId === p.id}
                          style={{
                            padding: '0.375rem', background: 'transparent', color: 'var(--text-tertiary)', border: 'none',
                            borderRadius: '0.5rem', cursor: 'pointer', opacity: deletingId === p.id ? 0.5 : 1,
                          }}
                          aria-label="Delete saved policy"
                        >
                          {deletingId === p.id ? '...' : <IconX size={16} />}
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}

              {savedPolicies.length >= MAX_POLICIES && (
                <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', borderRadius: '0.75rem', fontSize: '0.8125rem', color: 'var(--warning)', display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                  <IconAlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
                  <span>You've reached the {MAX_POLICIES}-policy limit. Delete one to upload a new policy.</span>
                </div>
              )}
            </div>
          </motion.div>

          {/* ── Results + Editable Fields ────── */}
          <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.55, delay: 0.3 }} style={{ position: 'relative' }}>
            {editableProfile ? (
              <>
                {/* Header */}
                <div className="card" style={{ marginBottom: '1.5rem', overflow: 'hidden' }}>
                  <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--bg-secondary)' }}>
                    <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)' }}>
                      {confirmed ? '✅ Policy Confirmed' : '📝 Review Extracted Fields'}
                    </h3>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      {confidenceClass && (
                        <span className={`badge ${confidenceClass}`}>
                          {result.extraction_confidence} CONFIDENCE
                        </span>
                      )}
                      {confirmed
                        ? <span className="badge badge-success">Active</span>
                        : <span className="badge badge-warning">Unconfirmed</span>
                      }
                    </div>
                  </div>

                  <div style={{ padding: '1.5rem' }}>
                    {/* Extraction warnings */}
                    {result?.extraction_warnings?.length > 0 && (
                      <div className="extraction-warnings" style={{ marginBottom: '1.5rem' }}>
                        <h5 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <IconAlertTriangle size={16} /> Please verify these extracted values:
                        </h5>
                        <ul>
                          {result.extraction_warnings.map((w, i) => <li key={i}>{w}</li>)}
                        </ul>
                      </div>
                    )}

                    {/* Policy search status banner */}
                    {result?.session_id && (
                      <div style={{
                        display: 'flex', alignItems: 'flex-start', gap: '0.875rem',
                        padding: '1rem',
                        background: result.policy_indexed ? 'var(--success-bg)' : 'var(--warning-bg)',
                        border: `1px solid ${result.policy_indexed ? 'var(--success-border)' : 'var(--warning-border)'}`,
                        borderRadius: '0.75rem',
                        marginBottom: '1.5rem',
                      }}>
                        <div style={{ color: result.policy_indexed ? 'var(--success)' : 'var(--warning)', marginTop: '2px' }}>
                          {result.policy_indexed ? <IconCheckCircle size={20} /> : <IconAlertTriangle size={20} />}
                        </div>
                        <div>
                          <p style={{ fontSize: '0.875rem', fontWeight: 700, color: result.policy_indexed ? 'var(--success)' : 'var(--warning)', marginBottom: '0.25rem' }}>
                            {result?.policy_indexed
                                        ? `Policy search ready — ${result.policy_page_count || '?'} pages indexed`
                                        : 'Document indexing failed — appeal letters will use the available policy details'}
                          </p>
                          <p style={{ fontSize: '0.8125rem', color: result.policy_indexed ? 'var(--success)' : 'var(--warning)', opacity: 0.8, lineHeight: 1.5 }}>
                            {result.policy_indexed
                                        ? 'Your policy is ready for reference, and appeal notes can point to exact page numbers.'
                                        : 'The document could not be saved for later reference. Please try uploading again.'}
                          </p>
                          {result.policy_indexed && (
                            <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.5rem', fontFamily: 'monospace' }}>
                              Session: {result.session_id}
                            </p>
                          )}
                        </div>
                      </div>
                    )}

                    <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1.5rem', lineHeight: 1.5 }}>
                      Review AI-extracted values below. <strong style={{ color: 'var(--warning)' }}>Amber fields</strong> were estimated (not explicitly found in the document) — please verify before using.
                    </p>

                    {/* Plan identity */}
                    <EditableTextField label="Plan Name" field="plan_name" value={editableProfile.plan_name} onChange={handleFieldChange} />
                    <EditableTextField label="Carrier" field="carrier_name" value={editableProfile.carrier_name} onChange={handleFieldChange} />
                    <EditableSelectField
                      label="Plan Type" field="plan_type" value={editableProfile.plan_type}
                      onChange={handleFieldChange}
                      options={['HMO', 'PPO', 'EPO', 'POS']}
                    />
                    <EditableSelectField
                      label="Legal Classification" field="legal_classification" value={editableProfile.legal_classification}
                      onChange={handleFieldChange}
                      options={['FULLY_INSURED', 'SELF_FUNDED_ERISA', 'MEDICARE_ADVANTAGE', 'MEDICARE_ORIGINAL', 'MEDICAID_MANAGED', 'INDIVIDUAL_ACA']}
                    />
                    <EditableTextField label="State" field="state" value={editableProfile.state} onChange={handleFieldChange} />

                    {/* Divider */}
                    <div style={{ height: '1px', background: 'var(--border-secondary)', margin: '1.25rem 0' }} />
                    <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.5rem' }}>In-Network Cost Sharing</p>

                    <EditableNumericField label="Individual Deductible" field="in_network_deductible_individual" value={editableProfile.in_network_deductible_individual} onChange={handleFieldChange} />
                    <EditableNumericField label="Individual OOP Max" field="in_network_oop_max_individual" value={editableProfile.in_network_oop_max_individual} onChange={handleFieldChange} />
                    <div className="policy-editable-field">
                      <div className="policy-editable-label"><span>Coinsurance (patient %)</span></div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                        <input
                          className="policy-field-input"
                          type="number" min="0" max="100" step="1"
                          value={editableProfile.in_network_coinsurance != null ? Math.round(editableProfile.in_network_coinsurance * 100) : ''}
                          onChange={e => handleFieldChange('in_network_coinsurance', e.target.value === '' ? null : Number(e.target.value) / 100)}
                        />
                        <span style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>%</span>
                      </div>
                    </div>

                    {/* Copays */}
                    <div style={{ height: '1px', background: 'var(--border-secondary)', margin: '1.25rem 0' }} />
                    <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.5rem' }}>Copay Schedule</p>

                    {editableProfile.copay_schedule && Object.entries({
                      primary_care: 'Primary Care',
                      specialist: 'Specialist',
                      urgent_care: 'Urgent Care',
                      emergency_room: 'Emergency Room',
                      generic_rx: 'Generic Rx',
                      preferred_brand_rx: 'Brand Rx',
                    }).map(([key, label]) => (
                      <div className="policy-editable-field" key={key}>
                        <div className="policy-editable-label"><span>{label}</span></div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                          <span style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>$</span>
                          <input
                            className="policy-field-input"
                            type="number" min="0" step="1"
                            value={editableProfile.copay_schedule[key] ?? ''}
                            onChange={e => handleCopayChange(key, e.target.value)}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Confirm button */}
                <button
                  className={confirmed ? 'btn btn-outline' : 'btn btn-red'}
                  style={{ width: '100%', padding: '1rem', fontSize: '1rem' }}
                  onClick={handleConfirm}
                >
                  {confirmed ? 'Re-confirm after edits' : <><IconCheckCircle size={18} /> Confirm & Use This Policy</>}
                </button>

                {confirmed && (
                  <motion.button
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    style={{ 
                      marginTop: '1rem', 
                      width: '100%',
                      padding: '1rem 1.25rem', 
                      background: 'var(--success-bg)', 
                      border: '1px solid var(--success-border)', 
                      borderRadius: 'var(--radius-full)', 
                      fontSize: '0.9375rem', 
                      color: 'var(--success)', 
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.5rem',
                      boxShadow: 'var(--shadow-sm)'
                    }}
                    onClick={() => navigate('/claim')}
                  >
                    <IconCheckCircle size={18} />
                    <span>Policy is active</span>
                    <span style={{ opacity: 0.5 }}>—</span>
                    <span style={{ textDecoration: 'underline' }}>Go to Claim Evaluator →</span>
                  </motion.button>
                )}

                {result?.explanation && (
                  <div className="explanation-box" style={{ marginTop: '1.5rem', background: 'var(--info-bg)', borderColor: 'var(--info-border)' }}>
                    <h4 style={{ color: 'var(--info)' }}><IconFileText size={18} /> Plain English Summary</h4>
                    <div style={{ whiteSpace: 'pre-wrap', color: 'var(--text-primary)' }}>{result.explanation}</div>
                  </div>
                )}
              </>
            ) : (
              <div className="card" style={{ padding: '4rem 2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <div style={{ width: '80px', height: '80px', borderRadius: '50%', background: 'var(--bg-secondary)', border: '1px solid var(--border-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1.5rem', color: 'var(--text-tertiary)' }}>
                  <IconFileText size={40} />
                </div>
                <h3 style={{ fontWeight: 800, fontSize: '1.375rem', marginBottom: '0.5rem', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>No Policy Loaded</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem', maxWidth: '20rem', margin: '0 auto', lineHeight: 1.5 }}>
                  Paste your policy text and click "Analyze Policy" to extract structured details.
                </p>
              </div>
            )}
          </motion.div>
        </div>
      </div>
    </section>
  )
}
