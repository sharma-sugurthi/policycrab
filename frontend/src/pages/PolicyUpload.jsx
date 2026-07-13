import { useState } from 'react'
import { motion } from 'framer-motion'
import { apiFetch } from '../lib/api'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

// Editable numeric field row
function EditableNumericField({ label, field, value, onChange, isDefaulted, prefix = '$' }) {
  return (
    <div className="policy-editable-field">
      <div className="policy-editable-label">
        <span>{label}</span>
        {isDefaulted && <span className="defaulted-tag">ESTIMATED</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
        {prefix && <span style={{ fontSize: '0.875rem', color: '#71717a', fontWeight: 600 }}>{prefix}</span>}
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
  const [policyText, setPolicyText] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Editable profile state
  const [editableProfile, setEditableProfile] = useState(null)
  const [confirmed, setConfirmed] = useState(false)

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
    onPolicyParsed(editableProfile)
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

      const data = await res.json()
      if (data.success && data.policy_profile) {
        setResult(data)
        setEditableProfile({ ...data.policy_profile })
        if (data.extracted_text) setPolicyText(data.extracted_text)
      } else {
        setError(data.errors?.join(', ') || 'Failed to parse policy')
      }
    } catch (err) {
      setError(`Network error: ${err.message}`)
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
            Upload your Summary of Benefits and Coverage (SBC) PDF or paste the text. Then review and confirm the extracted fields before evaluating claims.
          </motion.p>
        </motion.div>

        <div className="grid-2" style={{ alignItems: 'start' }}>
          {/* ── Input ─────────────────── */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
            <div className="card" style={{ padding: '2rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                <div className="feature-icon red">📋</div>
                <div>
                  <h3 style={{ fontWeight: 700, fontSize: '1rem', color: '#09090b' }}>Policy Document</h3>
                  <p style={{ fontSize: '0.8125rem', color: '#a1a1aa' }}>Upload a PDF or paste your SBC/EOB text</p>
                </div>
              </div>

              <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '0.75rem', padding: '1rem', marginBottom: '1.25rem', fontSize: '0.8125rem', color: '#1e40af' }}>
                <strong style={{ display: 'block', marginBottom: '0.25rem' }}>💡 What should I upload?</strong>
                Upload your <strong>Summary of Benefits and Coverage (SBC)</strong>. This is usually an 8-page document detailing deductibles, copays, and out-of-pocket maximums. Or, upload an <strong>Explanation of Benefits (EOB)</strong> for a specific claim.
              </div>

              <div style={{ marginBottom: '1.25rem', background: '#fafafa', border: '1px dashed #d4d4d8', borderRadius: '0.75rem', padding: '1.25rem', textAlign: 'center' }}>
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={e => setSelectedFile(e.target.files[0])}
                  style={{ display: 'none' }}
                  id="pdf-upload"
                />
                <label htmlFor="pdf-upload" style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                  <div style={{ width: '40px', height: '40px', background: '#fff', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', color: '#dc2626' }}>
                    📄
                  </div>
                  <span style={{ fontWeight: 600, color: '#dc2626', fontSize: '0.875rem' }}>
                    {selectedFile ? selectedFile.name : 'Click to select a PDF'}
                  </span>
                  {!selectedFile && <span style={{ fontSize: '0.75rem', color: '#71717a' }}>Max size: 10MB</span>}
                </label>
                {selectedFile && (
                  <button onClick={() => setSelectedFile(null)} style={{ background: 'transparent', border: 'none', color: '#71717a', fontSize: '0.75rem', marginTop: '0.5rem', cursor: 'pointer', textDecoration: 'underline' }}>
                    Clear selection
                  </button>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', margin: '1rem 0' }}>
                <div style={{ height: '1px', flex: 1, background: '#e4e4e7' }} />
                <span style={{ fontSize: '0.75rem', color: '#a1a1aa', fontWeight: 600, textTransform: 'uppercase' }}>OR PASTE TEXT</span>
                <div style={{ height: '1px', flex: 1, background: '#e4e4e7' }} />
              </div>

              <textarea
                value={policyText}
                onChange={e => { setPolicyText(e.target.value); setSelectedFile(null); }}
                placeholder="Paste your insurance policy document text here..."
                style={{ minHeight: '180px', marginBottom: '1.25rem' }}
                disabled={!!selectedFile}
              />

              <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.5rem' }}>
                <button className="btn btn-red" onClick={handleUpload} disabled={loading || (!selectedFile && policyText.trim().length < 50)}>
                  {loading ? <><span className="spinner" /> Analyzing...</> : '🔍 Analyze Policy'}
                </button>
                <button className="btn btn-ghost" onClick={() => { setPolicyText(sampleSBC); setSelectedFile(null); }}>
                  📝 Load Sample Text
                </button>
              </div>

              {error && (
                <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.75rem', color: '#dc2626', fontSize: '0.8125rem', fontWeight: 500 }}>
                  ❌ {error}
                </div>
              )}
            </div>
          </motion.div>

          {/* ── Results + Editable Fields ────── */}
          <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.55, delay: 0.3 }} style={{ position: 'relative' }}>
            {editableProfile ? (
              <>
                {/* Header */}
                <div className="results-panel" style={{ marginBottom: '1.5rem' }}>
                  <div className="results-header">
                    <h3 style={{ fontWeight: 700, fontSize: '1rem' }}>
                      {confirmed ? '✅ Policy Confirmed' : '📝 Review & Confirm Extracted Fields'}
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

                  <div className="results-body">
                    {/* Extraction warnings */}
                    {result?.extraction_warnings?.length > 0 && (
                      <div className="extraction-warnings" style={{ marginBottom: '1rem' }}>
                        <h5>⚠️ Please verify these extracted values:</h5>
                        <ul>
                          {result.extraction_warnings.map((w, i) => <li key={i}>{w}</li>)}
                        </ul>
                      </div>
                    )}

                    <p style={{ fontSize: '0.8125rem', color: '#71717a', marginBottom: '1rem', lineHeight: 1.5 }}>
                      Review AI-extracted values below. <strong style={{ color: '#92400e' }}>Amber fields</strong> were estimated (not explicitly found in the document) — please verify before using.
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
                    <div style={{ height: '1px', background: '#f4f4f5', margin: '0.75rem 0' }} />
                    <p style={{ fontSize: '0.75rem', fontWeight: 700, color: '#71717a', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.25rem' }}>In-Network Cost Sharing</p>

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
                        <span style={{ fontSize: '0.875rem', color: '#71717a', fontWeight: 600 }}>%</span>
                      </div>
                    </div>

                    {/* Copays */}
                    <div style={{ height: '1px', background: '#f4f4f5', margin: '0.75rem 0' }} />
                    <p style={{ fontSize: '0.75rem', fontWeight: 700, color: '#71717a', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.25rem' }}>Copay Schedule</p>

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
                          <span style={{ fontSize: '0.875rem', color: '#71717a', fontWeight: 600 }}>$</span>
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
                  className={confirmed ? 'btn btn-ghost' : 'btn btn-red'}
                  style={{ width: '100%', padding: '0.875rem', fontSize: '0.9375rem' }}
                  onClick={handleConfirm}
                >
                  {confirmed ? '✅ Policy Confirmed — Re-confirm after edits' : '✔ Confirm & Use This Policy →'}
                </button>

                {confirmed && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    style={{ marginTop: '1rem', padding: '0.875rem 1.25rem', background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '1rem', fontSize: '0.875rem', color: '#065f46', fontWeight: 600 }}
                  >
                    ✅ Policy is active — go to <strong>Claim Evaluator</strong> to run a claim.
                  </motion.div>
                )}

                {result?.explanation && (
                  <div className="explanation-box" style={{ marginTop: '1.5rem' }}>
                    <h4>💡 Plain English Summary</h4>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{result.explanation}</div>
                  </div>
                )}
              </>
            ) : (
              <div className="card" style={{ padding: '4rem 2rem', textAlign: 'center' }}>
                <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📋</div>
                <h3 style={{ fontWeight: 800, fontSize: '1.25rem', marginBottom: '0.5rem' }}>No Policy Loaded</h3>
                <p style={{ color: '#71717a', fontSize: '0.875rem', maxWidth: '20rem', margin: '0 auto' }}>
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
