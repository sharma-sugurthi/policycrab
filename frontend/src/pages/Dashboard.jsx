import { useState, useEffect, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import { apiFetch, formatApiError, readApiResponse } from '../lib/api'
import { jsPDF } from 'jspdf'

// ── Session-scoped key for document extraction summaries ─────
const SS_VAULT_KEY = 'policycrab_vault_docs'

// ── Confidence badge helper ─────────────────────────────────
function ConfidenceBadge({ level }) {
  if (!level) return null
  const map = {
    high:   { bg: '#ecfdf5', color: '#059669', border: '#a7f3d0', label: 'High' },
    medium: { bg: '#fffbeb', color: '#d97706', border: '#fde68a', label: 'Med' },
    low:    { bg: '#fef2f2', color: '#dc2626', border: '#fecaca', label: 'Low' },
  }
  const s = map[level] || map.low
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '1px 7px', borderRadius: '9999px',
      fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.04em',
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
    }}>{s.label}</span>
  )
}

// ── Document type label ─────────────────────────────────────
function DocTypeBadge({ type }) {
  const map = {
    eob:     { label: 'EOB',    bg: '#eff6ff', color: '#2563eb', border: '#bfdbfe' },
    bill:    { label: 'Bill',   bg: '#fffbeb', color: '#d97706', border: '#fde68a' },
    policy:  { label: 'Policy', bg: '#f5f3ff', color: '#7c3aed', border: '#ddd6fe' },
    unknown: { label: 'Doc',    bg: '#fafafa', color: '#3f3f46', border: '#e4e4e7' },
  }
  const s = map[type] || map.unknown
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 9px', borderRadius: '9999px',
      fontSize: '0.65rem', fontWeight: 700,
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
    }}>{s.label}</span>
  )
}

// ── Extracted field rows ─────────────────────────────────────
const FIELD_DEFS = [
  { key: 'date_of_service',       label: 'Date of Service',       confKey: 'date_of_service' },
  { key: 'billed_amount',         label: 'Billed Amount',         confKey: 'billed_amount',   prefix: '$' },
  { key: 'allowed_amount',        label: 'Allowed Amount',        confKey: 'allowed_amount',  prefix: '$' },
  { key: 'plan_paid_amount',      label: 'Plan Paid',             prefix: '$' },
  { key: 'patient_responsibility',label: 'Patient Responsibility', prefix: '$' },
  { key: 'provider_name',         label: 'Provider' },
  { key: 'facility_name',         label: 'Facility' },
  { key: 'cpt_code',              label: 'CPT Code',              confKey: 'cpt_code' },
  { key: 'cpt_description',       label: 'CPT Description' },
  { key: 'icd_10_code',           label: 'ICD-10 Code' },
  { key: 'denial_carc_code',      label: 'CARC Code',             confKey: 'denial_carc_code' },
  { key: 'denial_rarc_code',      label: 'RARC Code' },
  { key: 'denial_reason_text',    label: 'Denial Reason' },
]

import '../legacy.css'

// ── Document Vault Component ────────────────────────────────
function DocumentVault({ policyProfile, onGoToClaim }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [progressText, setProgressText] = useState('Uploading document...')
  const [result, setResult] = useState(null)        // last extraction result
  const [error, setError] = useState(null)
  const [history, setHistory] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(SS_VAULT_KEY) || '[]') } catch { return [] }
  })
  const inputRef = useRef(null)

  useEffect(() => {
    let interval;
    if (uploading && uploadProgress < 100) {
      interval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev < 20) {
            setProgressText('Uploading document...')
            return prev + 5
          } else if (prev < 50) {
            setProgressText('Analyzing layout...')
            return prev + 2
          } else if (prev < 85) {
            setProgressText('Extracting fields via AI...')
            return prev + 1
          } else if (prev < 95) {
            setProgressText('Validating data...')
            return prev + 0.5
          }
          return prev
        })
      }, 200)
    } else if (!uploading) {
      setUploadProgress(0)
      setProgressText('Uploading document...')
    }
    return () => clearInterval(interval)
  }, [uploading, uploadProgress])

  const saveToHistory = useCallback((entry) => {
    setHistory(prev => {
      const next = [entry, ...prev].slice(0, 10) // keep last 10
      try { sessionStorage.setItem(SS_VAULT_KEY, JSON.stringify(next)) } catch {}
      return next
    })
  }, [])

  const processFile = useCallback(async (file) => {
    if (!file) return
    const MAX = 10 * 1024 * 1024
    if (file.size > MAX) { setError('File too large. Maximum is 10 MB.'); return }

    const isPdf = file.type.includes('pdf') || file.name.toLowerCase().endsWith('.pdf')
      const isImg = file.type.startsWith('image/')
      if (!isPdf && !isImg) { setError('Unsupported type. Please upload a PDF or image (JPG, PNG, TIFF, WEBP).'); return }
      if (isImg) {
        setError('Image uploads are temporarily unavailable because they cannot be scrubbed locally before processing. Upload a text-based PDF instead.')
        return
      }

    setUploading(true)
    setError(null)
    setResult(null)

    try {
      const form = new FormData()
      form.append('file', file)
      const res = await apiFetch('/eob/parse', { method: 'POST', body: form })
      const data = await readApiResponse(res)
      if (!res.ok) throw new Error(formatApiError(data, 'Extraction failed'))
      setResult({ ...data, filename: file.name, uploadedAt: new Date().toISOString() })
      saveToHistory({
        filename: file.name,
        uploadedAt: new Date().toISOString(),
        document_type: data.extracted?.document_type || 'unknown',
        is_denied: data.extracted?.is_denied,
        billed_amount: data.extracted?.billed_amount,
        cpt_code: data.extracted?.cpt_code,
        extraction_method: data.extraction_method,
      })
    } catch (e) {
      setError(e.message || 'Something went wrong.')
    } finally {
      setUploadProgress(100)
      setTimeout(() => setUploading(false), 500)
    }
  }, [saveToHistory])

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) processFile(file)
  }, [processFile])

  const onFileChange = useCallback((e) => {
    const file = e.target.files[0]
    if (file) processFile(file)
    e.target.value = ''
  }, [processFile])

  // Pre-fill claim form via sessionStorage then navigate
  const fillClaimForm = () => {
    if (!result?.extracted) return
    const ex = result.extracted
    const prefill = {
      cpt_code: ex.cpt_code || '',
      cpt_description: ex.cpt_description || '',
      icd_10_code: ex.icd_10_code || '',
      date_of_service: ex.date_of_service || '',
      billed_amount: ex.billed_amount || '',
      allowed_amount: ex.allowed_amount || '',
      provider_name: ex.provider_name || '',
      facility_name: ex.facility_name || '',
      denial_carc_code: ex.denial_carc_code || '',
      denial_rarc_code: ex.denial_rarc_code || '',
      is_denied: ex.is_denied || false,
      denial_reason_text: ex.denial_reason_text || '',
      _source: 'document_vault',
    }
    try { sessionStorage.setItem('policycrab_eob_prefill', JSON.stringify(prefill)) } catch {}
    onGoToClaim?.()
  }

  const docType = result?.extracted?.document_type || null
  const isDenied = result?.extracted?.is_denied
  const conf = result?.extracted?.confidence || {}

  return (
    <div className="legacy-theme" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

      {/* ── Upload Zone ── */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !uploading && inputRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? '#dc2626' : '#d4d4d8'}`,
          borderRadius: '1.25rem',
          background: dragging ? '#fef2f2' : '#fafafa',
          padding: '3rem 2rem',
          textAlign: 'center',
          cursor: uploading ? 'default' : 'pointer',
          transition: 'all 0.2s ease',
        }}
      >
        <input ref={inputRef} type="file" accept=".pdf,application/pdf" style={{ display: 'none' }} onChange={onFileChange} />
        {uploading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem', width: '100%', maxWidth: '400px', margin: '0 auto' }}>
            <div style={{ width: '100%', height: '8px', background: '#e4e4e7', borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{ 
                height: '100%', 
                background: '#dc2626', 
                width: `${uploadProgress}%`,
                transition: 'width 0.2s ease-out'
              }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
              <p style={{ color: '#71717a', fontSize: '0.85rem', fontWeight: 600 }}>{progressText}</p>
              <p style={{ color: '#a1a1aa', fontSize: '0.75rem', fontWeight: 700 }}>{Math.floor(uploadProgress)}%</p>
            </div>
            {uploadProgress > 50 && (
              <p style={{ color: '#a1a1aa', fontSize: '0.7rem', marginTop: '0.5rem', fontStyle: 'italic' }}>
                Long documents may take up to a minute to process...
              </p>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{
              width: 52, height: 52, borderRadius: '1rem',
              background: '#fef2f2', display: 'flex', alignItems: 'center',
              justifyContent: 'center', fontSize: '1.5rem', margin: '0 auto 0.5rem',
            }}>📄</div>
            <p style={{ fontSize: '0.9375rem', fontWeight: 700, color: '#09090b' }}>
              Drop your document here
            </p>
            <p style={{ fontSize: '0.8125rem', color: '#71717a' }}>
              EOB, medical bill, or insurance policy · PDF or image · Max 10 MB
            </p>
            <button className="btn btn-red" style={{ marginTop: '0.75rem', padding: '0.5rem 1.5rem', fontSize: '0.8125rem' }}>
              Browse Files
            </button>
          </div>
        )}
      </div>

      {/* ── Error ── */}
      {error && (
        <div style={{
          background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.75rem',
          padding: '0.875rem 1rem', color: '#dc2626', fontSize: '0.875rem', fontWeight: 600,
        }}>
          ⚠ {error}
        </div>
      )}

      {/* ── Extraction Results ── */}
      {result && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          style={{ border: '1px solid #e4e4e7', borderRadius: '1.25rem', overflow: 'hidden' }}
        >
          {/* Header */}
          <div style={{
            background: '#fafafa', borderBottom: '1px solid #f4f4f5',
            padding: '1rem 1.25rem',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#09090b' }}>
                {result.filename}
              </span>
              {docType && <DocTypeBadge type={docType} />}
              {isDenied && (
                <span className="badge badge-danger">Denied</span>
              )}
              <span style={{ fontSize: '0.7rem', color: '#a1a1aa' }}>
                via {result.extraction_method === 'pytesseract_ocr' ? 'OCR' : 'PDF'}
              </span>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {(docType === 'eob' || docType === 'bill') && (
                <button
                  className="btn btn-red"
                  style={{ fontSize: '0.75rem', padding: '0.4rem 1rem' }}
                  onClick={fillClaimForm}
                  title="Pre-fill the Claim Evaluator form with these extracted values"
                >
                  Fill Claim Form →
                </button>
              )}
              <button
                className="btn btn-ghost"
                style={{ fontSize: '0.75rem' }}
                onClick={() => setResult(null)}
              >✕</button>
            </div>
          </div>

          {/* Field grid */}
          <div style={{ padding: '1.25rem' }}>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
              gap: '0.5rem',
            }}>
              {FIELD_DEFS.map(({ key, label, confKey, prefix }) => {
                const val = result.extracted?.[key]
                if (val == null || val === '' || val === false) return null
                const displayVal = typeof val === 'number'
                  ? `${prefix || ''}${Number(val).toLocaleString()}`
                  : key === 'is_denied' ? (val ? 'Yes' : 'No') : String(val)
                const cLevel = confKey ? conf[confKey] : null

                return (
                  <div key={key} style={{
                    display: 'flex', flexDirection: 'column', gap: '3px',
                    background: '#fafafa', borderRadius: '0.75rem',
                    padding: '0.625rem 0.75rem', border: '1px solid #f4f4f5',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: 600, color: '#a1a1aa', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        {label}
                      </span>
                      {cLevel && <ConfidenceBadge level={cLevel} />}
                    </div>
                    <span style={{ fontSize: '0.875rem', fontWeight: 700, color: '#09090b', wordBreak: 'break-word' }}>
                      {displayVal}
                    </span>
                  </div>
                )
              })}
            </div>

            {result.extracted?.denial_reason_text && (
              <div style={{
                marginTop: '0.75rem', padding: '0.875rem 1rem',
                background: '#fef2f2', borderRadius: '0.75rem', border: '1px solid #fecaca',
              }}>
                <p style={{ fontSize: '0.7rem', fontWeight: 700, color: '#dc2626', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
                  Denial Reason (verbatim)
                </p>
                <p style={{ fontSize: '0.875rem', color: '#7f1d1d', lineHeight: 1.6 }}>
                  {result.extracted.denial_reason_text}
                </p>
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* ── Upload History ── */}
      {history.length > 0 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3 style={{ fontSize: '0.875rem', fontWeight: 700, color: '#3f3f46' }}>Recent Documents</h3>
            <button
              className="btn btn-ghost"
              style={{ fontSize: '0.7rem', padding: '0.25rem 0.625rem' }}
              onClick={() => {
                setHistory([])
                try { sessionStorage.removeItem(SS_VAULT_KEY) } catch {}
              }}
            >
              Clear history
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {history.map((h, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '0.625rem 0.875rem', borderRadius: '0.75rem',
                background: '#fafafa', border: '1px solid #f4f4f5', gap: '0.75rem', flexWrap: 'wrap',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                  <span style={{ fontSize: '1rem' }}>
                    {h.document_type === 'eob' ? '📋' : h.document_type === 'bill' ? '🧾' : h.document_type === 'policy' ? '📑' : '📄'}
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <p style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#09090b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '200px' }}>{h.filename}</p>
                    <p style={{ fontSize: '0.7rem', color: '#a1a1aa' }}>{new Date(h.uploadedAt).toLocaleString()}</p>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', flexShrink: 0 }}>
                  {h.document_type && <DocTypeBadge type={h.document_type} />}
                  {h.is_denied && <span className="badge badge-danger" style={{ fontSize: '0.6rem' }}>Denied</span>}
                  {h.billed_amount && (
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#3f3f46' }}>
                      ${Number(h.billed_amount).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {history.length === 0 && !result && (
        <p style={{ fontSize: '0.8125rem', color: '#a1a1aa', textAlign: 'center' }}>
          No documents uploaded yet. Upload an EOB or medical bill above.
        </p>
      )}
    </div>
  )
}

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

// ── Bill Auditor Component ──────────────────────────────────
function BillAuditor({ history }) {
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [manualEntry, setManualEntry] = useState(false)
  const [form, setForm] = useState({
    cpt_code: '',
    cpt_description: '',
    icd_10_code: '',
    billed_amount: '',
    provider_name: '',
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleScan = async (dataToScan) => {
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const payload = {
        cpt_code: dataToScan.cpt_code,
        cpt_description: dataToScan.cpt_description,
        icd_10_code: dataToScan.icd_10_code,
        billed_amount: dataToScan.billed_amount ? parseFloat(dataToScan.billed_amount.toString().replace(/[^0-9.]/g, '')) : null,
        provider_name: dataToScan.provider_name || dataToScan.facility_name,
        date_of_service: dataToScan.date_of_service,
        denial_reason_text: dataToScan.denial_reason_text
      }

      const res = await apiFetch('/audit/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      
      const data = await res.json()
      if (!res.ok) throw new Error(formatApiError(data, 'Audit failed'))
      
      setResult(data.audit_result)
    } catch (err) {
      setError(err.message || 'Failed to scan bill.')
    } finally {
      setLoading(false)
    }
  }

  const getRiskColor = (score) => {
    if (score === 'Red') return { bg: '#fef2f2', text: '#dc2626', border: '#fecaca' }
    if (score === 'Yellow') return { bg: '#fffbeb', text: '#d97706', border: '#fde68a' }
    return { bg: '#ecfdf5', text: '#059669', border: '#a7f3d0' }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {!result ? (
        <>
          {/* Input Selection */}
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <button 
              className={`btn ${!manualEntry ? 'btn-red' : 'btn-ghost'}`}
              onClick={() => setManualEntry(false)}
            >
              Select from Vault
            </button>
            <button 
              className={`btn ${manualEntry ? 'btn-red' : 'btn-ghost'}`}
              onClick={() => { setManualEntry(true); setSelectedDoc(null); }}
            >
              Manual Entry
            </button>
          </div>

          {!manualEntry ? (
            <div style={{ background: '#fafafa', borderRadius: '1rem', padding: '1.5rem', border: '1px solid #f4f4f5' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', color: '#09090b' }}>Select a recent document</h3>
              {history && history.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {history.map((doc, idx) => (
                    <div 
                      key={idx} 
                      onClick={() => setSelectedDoc(doc)}
                      style={{
                        padding: '1rem',
                        borderRadius: '0.75rem',
                        border: `2px solid ${selectedDoc === doc ? '#dc2626' : '#e4e4e7'}`,
                        background: selectedDoc === doc ? '#fef2f2' : '#fff',
                        cursor: 'pointer',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                      }}
                    >
                      <div>
                        <p style={{ fontWeight: 600, color: '#09090b', fontSize: '0.9375rem' }}>{doc.filename}</p>
                        <p style={{ fontSize: '0.75rem', color: '#71717a' }}>Uploaded {new Date(doc.uploadedAt).toLocaleDateString()}</p>
                      </div>
                      {doc.billed_amount && (
                        <span style={{ fontWeight: 700, color: '#3f3f46' }}>${Number(doc.billed_amount).toLocaleString()}</span>
                      )}
                    </div>
                  ))}
                  
                  <button 
                    className="btn btn-red" 
                    style={{ marginTop: '1rem', alignSelf: 'flex-start' }}
                    disabled={!selectedDoc || loading}
                    onClick={() => handleScan(selectedDoc)}
                  >
                    {loading ? 'Scanning...' : 'Scan Selected Bill'}
                  </button>
                </div>
              ) : (
                <p style={{ color: '#71717a', fontSize: '0.875rem' }}>No documents in your Vault yet. Upload one first.</p>
              )}
            </div>
          ) : (
            <div style={{ background: '#fafafa', borderRadius: '1rem', padding: '1.5rem', border: '1px solid #f4f4f5', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
               <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#09090b' }}>Enter bill details</h3>
               <div className="grid-2">
                 <div>
                   <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#71717a', marginBottom: '0.25rem' }}>CPT Code</label>
                   <input className="input" value={form.cpt_code} onChange={e => setForm({...form, cpt_code: e.target.value})} placeholder="e.g. 99285" />
                 </div>
                 <div>
                   <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#71717a', marginBottom: '0.25rem' }}>Billed Amount</label>
                   <input className="input" value={form.billed_amount} onChange={e => setForm({...form, billed_amount: e.target.value})} placeholder="$" />
                 </div>
                 <div>
                   <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#71717a', marginBottom: '0.25rem' }}>ICD-10 Code (Diagnosis)</label>
                   <input className="input" value={form.icd_10_code} onChange={e => setForm({...form, icd_10_code: e.target.value})} placeholder="e.g. R07.9" />
                 </div>
                 <div>
                   <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#71717a', marginBottom: '0.25rem' }}>Provider/Facility</label>
                   <input className="input" value={form.provider_name} onChange={e => setForm({...form, provider_name: e.target.value})} placeholder="Hospital Name" />
                 </div>
                 <div style={{ gridColumn: '1 / -1' }}>
                   <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#71717a', marginBottom: '0.25rem' }}>CPT Description (Optional)</label>
                   <input className="input" value={form.cpt_description} onChange={e => setForm({...form, cpt_description: e.target.value})} placeholder="Emergency Dept Visit..." />
                 </div>
               </div>
               <button 
                  className="btn btn-red" 
                  style={{ alignSelf: 'flex-start' }}
                  disabled={loading || (!form.cpt_code && !form.billed_amount)}
                  onClick={() => handleScan(form)}
                >
                  {loading ? 'Scanning...' : 'Scan Bill Data'}
                </button>
            </div>
          )}

          {error && (
            <div style={{ padding: '1rem', background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', borderRadius: '0.75rem', fontWeight: 600 }}>
              ⚠ {error}
            </div>
          )}
        </>
      ) : (
        /* Results View */
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
          <div style={{ border: '1px solid #e4e4e7', borderRadius: '1.25rem', overflow: 'hidden' }}>
            <div style={{ background: '#fafafa', borderBottom: '1px solid #f4f4f5', padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
               <div>
                 <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#09090b', marginBottom: '0.25rem' }}>Audit Complete</h3>
                 <p style={{ color: '#71717a', fontSize: '0.9375rem' }}>{result.summary}</p>
               </div>
               
               <div style={{ 
                 padding: '0.5rem 1rem', 
                 borderRadius: '0.75rem',
                 background: getRiskColor(result.risk_score).bg,
                 color: getRiskColor(result.risk_score).text,
                 border: `1px solid ${getRiskColor(result.risk_score).border}`,
                 fontWeight: 800,
                 fontSize: '1.125rem',
                 textAlign: 'center'
               }}>
                 {result.risk_score} Risk
               </div>
            </div>

            <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {result.flags && result.flags.length > 0 ? (
                result.flags.map((flag, idx) => (
                  <div key={idx} style={{ 
                    padding: '1.25rem', 
                    borderRadius: '1rem', 
                    background: '#fff', 
                    border: '1px solid #e4e4e7',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                      <span style={{ 
                        background: '#fef2f2', color: '#dc2626', padding: '2px 8px', 
                        borderRadius: '4px', fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase'
                      }}>
                        {flag.issue_type}
                      </span>
                    </div>
                    <p style={{ color: '#09090b', fontSize: '0.9375rem', fontWeight: 500, marginBottom: '0.5rem' }}>
                      {flag.description}
                    </p>
                    <div style={{ background: '#fafafa', padding: '0.75rem', borderRadius: '0.5rem', borderLeft: '3px solid #dc2626' }}>
                      <p style={{ fontSize: '0.8125rem', color: '#52525b', fontWeight: 600 }}>Recommendation:</p>
                      <p style={{ fontSize: '0.8125rem', color: '#3f3f46', marginTop: '0.25rem' }}>{flag.recommendation}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ textAlign: 'center', padding: '2rem 0', color: '#059669', fontWeight: 600 }}>
                   ✅ No major billing anomalies detected.
                </div>
              )}
            </div>
            
            <div style={{ padding: '1rem 1.5rem', background: '#fafafa', borderTop: '1px solid #f4f4f5', display: 'flex', justifyContent: 'flex-end' }}>
               <button className="btn btn-outline" onClick={() => setResult(null)}>Scan Another Bill</button>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}

// ── Cost Estimator Component ────────────────────────────────
function CostEstimator({ policy }) {
  const [cpt, setCpt] = useState('')
  const [providerCharge, setProviderCharge] = useState('')
  const [result, setResult] = useState(null)

  const handleEstimate = () => {
    if (!policy) return
    const charge = parseFloat(providerCharge.toString().replace(/[^0-9.]/g, ''))
    if (isNaN(charge) || charge <= 0) return

    // Simple math logic based on standard insurance structure
    const inDeductible = policy.in_network_deductible_individual || 0
    const inCoinsurance = policy.in_network_coinsurance_percent || 20 // default 20% if not specified
    const inOOPMax = policy.in_network_oop_max_individual || 5000

    const outDeductible = policy.out_of_network_deductible_individual || inDeductible * 2
    const outCoinsurance = policy.out_of_network_coinsurance_percent || 50
    const outOOPMax = policy.out_of_network_oop_max_individual || inOOPMax * 2

    // Note: This is a very simplified pre-care estimation assuming 0 used so far.
    // In-Network Calculation
    let inPatientResp = 0
    if (charge <= inDeductible) {
      inPatientResp = charge
    } else {
      inPatientResp = inDeductible + ((charge - inDeductible) * (inCoinsurance / 100))
    }
    inPatientResp = Math.min(inPatientResp, inOOPMax)

    // Out-of-Network Calculation (assuming no balance billing limits for this basic calc)
    let outPatientResp = 0
    if (charge <= outDeductible) {
      outPatientResp = charge
    } else {
      outPatientResp = outDeductible + ((charge - outDeductible) * (outCoinsurance / 100))
    }
    outPatientResp = Math.min(outPatientResp, outOOPMax)
    
    // Add potential balance billing risk for OON
    const planPaidOon = charge - outPatientResp
    const maxAllowedOon = charge * 0.7 // Arbitrary UCR assumption for demo
    const balanceBillingRisk = Math.max(0, charge - maxAllowedOon - outPatientResp)

    setResult({
      charge,
      inNetwork: {
        patientResp: inPatientResp,
        planPaid: charge - inPatientResp
      },
      outOfNetwork: {
        patientResp: outPatientResp + balanceBillingRisk,
        planPaid: charge - (outPatientResp + balanceBillingRisk),
        balanceBillingRisk
      }
    })
  }

  if (!policy) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', background: '#fafafa', borderRadius: '1rem', border: '1px dashed #d4d4d8' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#09090b', marginBottom: '0.5rem' }}>No Policy Loaded</h3>
        <p style={{ color: '#71717a', fontSize: '0.875rem' }}>You need to load a policy from the Overview tab to use the Cost Estimator.</p>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ background: '#fafafa', borderRadius: '1rem', padding: '1.5rem', border: '1px solid #f4f4f5' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#09090b', marginBottom: '1rem' }}>Enter Procedure Details</h3>
        <div className="grid-2">
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#71717a', marginBottom: '0.25rem' }}>CPT Code (Optional)</label>
            <input className="input" value={cpt} onChange={e => setCpt(e.target.value)} placeholder="e.g. 99213" />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#71717a', marginBottom: '0.25rem' }}>Estimated Provider Charge</label>
            <input className="input" value={providerCharge} onChange={e => setProviderCharge(e.target.value)} placeholder="$" type="number" />
          </div>
        </div>
        <button 
          className="btn btn-red" 
          style={{ marginTop: '1rem' }}
          disabled={!providerCharge}
          onClick={handleEstimate}
        >
          Calculate Estimate
        </button>
      </div>

      {result && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          {/* In Network */}
          <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '1rem', padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#065f46', marginBottom: '0.5rem' }}>In-Network</h3>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', borderBottom: '1px dashed #a7f3d0', paddingBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.875rem', color: '#047857' }}>Estimated Patient Cost</span>
              <span style={{ fontSize: '1.125rem', fontWeight: 800, color: '#065f46' }}>${result.inNetwork.patientResp.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.75rem', color: '#059669' }}>Plan Pays</span>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#047857' }}>${result.inNetwork.planPaid.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
            </div>
          </div>

          {/* Out of Network */}
          <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '1rem', padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#92400e', marginBottom: '0.5rem' }}>Out-of-Network</h3>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', borderBottom: '1px dashed #fde68a', paddingBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.875rem', color: '#b45309' }}>Estimated Patient Cost</span>
              <span style={{ fontSize: '1.125rem', fontWeight: 800, color: '#92400e' }}>${result.outOfNetwork.patientResp.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '0.75rem', color: '#d97706' }}>Plan Pays</span>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#b45309' }}>${result.outOfNetwork.planPaid.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
            </div>
            {result.outOfNetwork.balanceBillingRisk > 0 && (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.75rem', color: '#dc2626' }}>Balance Billing Risk</span>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#b91c1c' }}>+${result.outOfNetwork.balanceBillingRisk.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
              </div>
            )}
          </div>
          
          <div style={{ gridColumn: '1 / -1', background: '#fafafa', padding: '1rem', borderRadius: '0.75rem', border: '1px solid #e4e4e7' }}>
             <p style={{ fontSize: '0.75rem', color: '#71717a', fontStyle: 'italic' }}>
               * Note: This is an estimate based on your policy's basic deductible and coinsurance structures, assuming your deductible has not yet been met for the year. Actual costs will vary based on contracted rates, negotiated UCR amounts, and previously accumulated out-of-pocket spending.
             </p>
          </div>
        </motion.div>
      )}
    </div>
  )
}

export default function Dashboard({ policyProfile, onPolicySelected }) {
  const { session } = useAuth()
  const navigate = useNavigate()
  const [policies, setPolicies] = useState([])
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(true)
  const [compareIds, setCompareIds] = useState(new Set())
  const [activeTab, setActiveTab] = useState('overview')
  const [vaultHistory, setVaultHistory] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(SS_VAULT_KEY) || '[]') } catch { return [] }
  })


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
    if (profile) {
      const selected = policies.find(p => p.policy_profile === profile)
      onPolicySelected?.(profile, {
        session_id: selected?.session_id || null,
        policy_indexed: Boolean(selected?.session_id),
      })
    }
    navigate('/claim')
  }

  const goToClaimFromVault = () => {
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

  const TABS = [
    { id: 'overview', label: '📊 Overview' },
    { id: 'vault',    label: '📄 Document Vault', badge: 'New' },
    { id: 'auditor',  label: '🔎 Bill Auditor', badge: 'Beta' },
    { id: 'estimator',label: '🧮 Cost Estimator' },
  ]

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
    <div className="legacy-theme">
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

        {/* ── Tab Strip ─────────────────────────────────────────── */}
        <div style={{
          display: 'flex', gap: '0.375rem',
          borderBottom: '1px solid #e4e4e7',
          marginBottom: '2rem',
          overflowX: 'auto',
        }}>
          {TABS.map(tab => (
            <button
              key={tab.id}
              id={`dashboard-tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.75rem 1.25rem',
                background: 'none', border: 'none',
                borderBottom: `2px solid ${activeTab === tab.id ? '#dc2626' : 'transparent'}`,
                color: activeTab === tab.id ? '#dc2626' : '#71717a',
                fontWeight: activeTab === tab.id ? 700 : 500,
                fontSize: '0.875rem',
                cursor: 'pointer',
                transition: 'all 0.18s ease',
                whiteSpace: 'nowrap',
                marginBottom: '-1px',
              }}
            >
              {tab.label}
              {tab.badge && (
                <span style={{
                  padding: '1px 6px', borderRadius: '9999px',
                  background: '#fef2f2', color: '#dc2626',
                  fontSize: '0.6rem', fontWeight: 800, letterSpacing: '0.04em',
                }}>
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Overview Tab ──────────────────────────────────────── */}
        {activeTab === 'overview' && (
          <>
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
                          document.getElementById('compare-table')?.scrollIntoView({ behavior: 'smooth' })
                        } else {
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
                        <p>Upload your plan summary or policy PDF to unlock claim evaluation.</p>
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
                          {c.appeal_output?.cited_regulations?.length > 0 && (
                            <div style={{ marginTop: '0.5rem', padding: '0.5rem 0.75rem', background: '#eff6ff', borderRadius: '0.5rem', border: '1px solid #bfdbfe' }}>
                              <p style={{ fontSize: '0.7rem', fontWeight: 700, color: '#1e40af', textTransform: 'uppercase', marginBottom: '0.25rem' }}>Smart Appeal Strategy</p>
                              <p style={{ fontSize: '0.8125rem', color: '#1e3a8a', fontWeight: 500 }}>
                                {c.appeal_output.cited_regulations[0].statute}: {c.appeal_output.cited_regulations[0].description}
                              </p>
                            </div>
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
          </>
        )}

        {/* ── Document Vault Tab ────────────────────────────────── */}
        {activeTab === 'vault' && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            <div style={{ marginBottom: '1.5rem' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#09090b', marginBottom: '0.375rem' }}>
                Document Vault
              </h2>
              <p style={{ fontSize: '0.875rem', color: '#71717a', lineHeight: 1.6, maxWidth: '48rem' }}>
                Upload any healthcare document — EOB, medical bill, or insurance policy. The AI reads it and extracts key fields automatically.
                Use <strong>Fill Claim Form</strong> to pre-populate the Claim Evaluator without typing anything.
              </p>
            </div>
            <DocumentVault policyProfile={policyProfile} onGoToClaim={goToClaimFromVault} />
          </motion.div>
        )}

        {/* ── Bill Auditor Tab ──────────────────────────────────── */}
        {activeTab === 'auditor' && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            <div style={{ marginBottom: '1.5rem' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#09090b', marginBottom: '0.375rem' }}>
                Bill Auditor
              </h2>
              <p style={{ fontSize: '0.875rem', color: '#71717a', lineHeight: 1.6, maxWidth: '48rem' }}>
                Scan a medical bill for upcoding, unbundled procedures, or excessive charges using our predictive auditing engine.
                Select an uploaded document from your vault or enter the codes manually.
              </p>
            </div>
            <BillAuditor history={vaultHistory} />
          </motion.div>
        )}

        {/* ── Cost Estimator Tab ────────────────────────────────── */}
        {activeTab === 'estimator' && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            <div style={{ marginBottom: '1.5rem' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#09090b', marginBottom: '0.375rem' }}>
                Proactive Cost Estimator
              </h2>
              <p style={{ fontSize: '0.875rem', color: '#71717a', lineHeight: 1.6, maxWidth: '48rem' }}>
                Calculate potential out-of-pocket costs before you receive care. Enter a procedure cost to see your estimated patient responsibility based on your loaded policy's deductible and coinsurance.
              </p>
            </div>
            <CostEstimator policy={policyProfile || (policies.length > 0 ? policies[0].policy_profile : null)} />
          </motion.div>
        )}

      </div>
    </section>
    </div>
  )
}


