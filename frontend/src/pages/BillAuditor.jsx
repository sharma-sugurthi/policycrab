import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { jsPDF } from 'jspdf'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useTasks } from '../contexts/TaskContext'
import { apiFetch, formatApiError, readApiResponse } from '../lib/api'
import { 
  IconReceipt, IconUpload, IconPlus, IconX, IconCheckCircle, 
  IconAlertTriangle, IconActivity, IconFileText, IconDownload, IconCopy, IconMail
} from '../components/Icons'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

export default function BillAuditor() {
  const location = useLocation()
  const { session, user } = useAuth()
  const { addTask, getLatestTask } = useTasks()

  // Input State
  const [lines, setLines] = useState([
    { line_number: 1, cpt_code: '', icd_10_code: '', billed_amount: '', date_of_service: '' }
  ])
  const [file, setFile] = useState(null)
  
  // Network State
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  
  // Results State
  const [result, setResult] = useState(null)
  const [auditId, setAuditId] = useState(null)
  const [letterLoading, setLetterLoading] = useState(false)
  const [letterStatus, setLetterStatus] = useState('')
  const [savedAudits, setSavedAudits] = useState([])

  const fetchAudits = useCallback(async () => {
    if (!session) return
    try {
      const res = await apiFetch('/history/audits')
      if (res.ok) {
        const data = await readApiResponse(res)
        setSavedAudits(Array.isArray(data) ? data : [])
      }
    } catch (e) {
      console.error('Failed to fetch audits:', e)
    }
  }, [session])

  useEffect(() => {
    fetchAudits()
  }, [fetchAudits])

  // ── On mount: restore result from TaskContext if user navigated away ──
  useEffect(() => {
    // Priority 1: explicit navigation from history panel
    if (location.state?.loadAudit) {
      const a = location.state.loadAudit
      setAuditId(a.id)
      setResult(a.audit_result_json)
      if (Array.isArray(a.service_lines_json) && a.service_lines_json.length > 0) {
        setLines(a.service_lines_json.map((l, idx) => ({ ...l, line_number: idx + 1, billed_amount: l.billed_amount?.toString() || '' })))
      }
      window.scrollTo({ top: 400, behavior: 'smooth' })
      return
    }

    // Priority 2: restore from global TaskContext (user navigated away mid/post audit)
    const task = getLatestTask('bill_audit')
    if (task) {
      if (task.status === 'done' && task.result) {
        const { auditResult, auditIdVal, extractedLines } = task.result
        setResult(auditResult)
        setAuditId(auditIdVal)
        if (Array.isArray(extractedLines) && extractedLines.length > 0) setLines(extractedLines)
      } else if (task.status === 'running') {
        setLoading(true)
        // Poll until done - task will resolve independently
        const poll = setInterval(() => {
          const t = getLatestTask('bill_audit')
          if (!t || t.status !== 'running') {
            clearInterval(poll)
            setLoading(false)
            if (t?.status === 'done' && t.result) {
              const { auditResult, auditIdVal, extractedLines } = t.result
              setResult(auditResult)
              setAuditId(auditIdVal)
              if (Array.isArray(extractedLines) && extractedLines.length > 0) setLines(extractedLines)
              fetchAudits()
            } else if (t?.status === 'error') {
              setError(t.error || 'Audit failed.')
            }
          }
        }, 800)
        return () => clearInterval(poll)
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state])

  const deleteAudit = async (id, e) => {
    if (e) e.stopPropagation()
    try {
      const res = await apiFetch(`/history/audits/${id}`, { method: 'DELETE' })
      if (res.ok) {
        setSavedAudits(prev => prev.filter(a => a.id !== id))
        if (auditId === id) {
          setResult(null)
          setAuditId(null)
        }
      }
    } catch (err) {
      console.error('Failed to delete audit:', err)
    }
  }

  const loadSavedReport = (a) => {
    setAuditId(a.id)
    setResult(a.audit_result_json)
    if (Array.isArray(a.service_lines_json) && a.service_lines_json.length > 0) {
      setLines(a.service_lines_json.map((l, idx) => ({ ...l, line_number: idx + 1, billed_amount: l.billed_amount?.toString() || '' })))
    }
    window.scrollTo({ top: 300, behavior: 'smooth' })
  }

  // ── Input Handlers ──────────────────────────────────────────────────
  const addLine = () => {
    setLines(prev => [...prev, { line_number: prev.length + 1, cpt_code: '', icd_10_code: '', billed_amount: '', date_of_service: '' }])
  }

  const removeLine = (index) => {
    if (lines.length === 1) return
    setLines(prev => {
      const newLines = prev.filter((_, i) => i !== index)
      return newLines.map((l, i) => ({ ...l, line_number: i + 1 }))
    })
  }

  const updateLine = (index, field, value) => {
    setLines(prev => {
      const newLines = [...prev]
      newLines[index] = { ...newLines[index], [field]: value }
      return newLines
    })
  }

  const handleFileUpload = (e) => {
    const selected = e.target.files[0]
    if (!selected) return
    setFile(selected)
    setLines([]) // clear manual entry if using upload
  }

  // ── Submit Handlers ─────────────────────────────────────────────────
  const handleAudit = () => {
    // Validate before kicking off the background task
    if (!file) {
      const formattedLines = lines.map(l => ({
        ...l, billed_amount: l.billed_amount ? parseFloat(l.billed_amount) : null,
      })).filter(l => l.cpt_code || l.billed_amount)
      if (formattedLines.length === 0) {
        setError('Please enter at least one service line with a CPT code or billed amount.')
        return
      }
    }

    setLoading(true)
    setError(null)
    setResult(null)
    setLetterStatus('')

    // Capture current file/lines for the closure (they may change if user navigates back)
    const capturedFile = file
    const capturedLines = lines

    addTask('bill_audit', capturedFile ? `Auditing "${capturedFile.name}"…` : 'Auditing bill…', async () => {
      let res
      if (capturedFile) {
        const formData = new FormData()
        formData.append('file', capturedFile)
        res = await apiFetch('/audit/upload', { method: 'POST', body: formData })
      } else {
        const formattedLines = capturedLines.map(l => ({
          ...l, billed_amount: l.billed_amount ? parseFloat(l.billed_amount) : null,
        })).filter(l => l.cpt_code || l.billed_amount)
        res = await apiFetch('/audit/scan', {
          method: 'POST',
          body: JSON.stringify({ service_lines: formattedLines }),
        })
      }

      const data = await readApiResponse(res)
      if (!data.success || !data.audit_result) {
        throw new Error(formatApiError(data, 'Audit failed'))
      }

      const auditResult   = data.audit_result
      const auditIdVal    = data.audit_id || null
      const extractedLines = data.extracted_lines
        ? data.extracted_lines.map((l, idx) => ({
            ...l, line_number: idx + 1, billed_amount: l.billed_amount?.toString() || ''
          }))
        : capturedLines

      // If the component is still mounted, update local state immediately
      setResult(auditResult)
      setAuditId(auditIdVal)
      if (data.extracted_lines) setLines(extractedLines)
      setLoading(false)
      fetchAudits()

      // Return payload so TaskContext stores it for restoration on re-mount
      return { auditResult, auditIdVal, extractedLines }
    }).catch(err => {
      setError(err.message || 'Audit failed')
      setLoading(false)
    })
  }


  // ── Letter Generation ───────────────────────────────────────────────
  const handleGenerateLetter = async () => {
    if (!result) return
    setLetterLoading(true)
    setLetterStatus('')

    try {
      const res = await apiFetch('/audit/dispute-letter', {
        method: 'POST',
        body: JSON.stringify({ audit_result: result, audit_id: auditId })
      })
      const data = await readApiResponse(res)
      if (data.success && data.letter_text) {
        setResult(prev => ({ ...prev, dispute_letter: data.letter_text }))
        setLetterStatus('Letter generated successfully!')
      } else {
        setLetterStatus(formatApiError(data, 'Failed to generate letter'))
      }
    } catch (err) {
      setLetterStatus(`Network error: ${err.message}`)
    } finally {
      setLetterLoading(false)
    }
  }

  const handleDownloadPDF = () => {
    if (!result?.dispute_letter) return
    
    const doc = new jsPDF({ unit: 'pt', format: 'letter' })
    const margin = 60
    const pageW = doc.internal.pageSize.getWidth()
    const maxW = pageW - margin * 2
    let y = margin

    // Header
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(16)
    doc.setTextColor(220, 38, 38)
    doc.text('PolicyCrab - Billing Dispute Letter', margin, y)
    y += 24
    doc.setDrawColor(220, 38, 38)
    doc.setLineWidth(1.5)
    doc.line(margin, y, pageW - margin, y)
    y += 20

    // Body
    doc.setFont('times', 'normal')
    doc.setFontSize(11)
    doc.setTextColor(30)
    
    // Inject known user info for the PDF download as well
    let finalLetter = result.dispute_letter
    if (user?.user_metadata?.full_name) {
      finalLetter = finalLetter.replace(/\[Patient Name\]/gi, user.user_metadata.full_name)
      finalLetter = finalLetter.replace(/\[Your Name\]/gi, user.user_metadata.full_name)
    }
    
    const linesText = doc.splitTextToSize(finalLetter, maxW)
    const pageH = doc.internal.pageSize.getHeight()
    for (const line of linesText) {
      if (y > pageH - 80) { doc.addPage(); y = margin }
      doc.text(line, margin, y)
      y += 15
    }

    doc.save(`billing-dispute-${new Date().toISOString().slice(0, 10)}.pdf`)
    setLetterStatus('Downloaded PDF')
  }

  const handleOpenGmail = () => {
    if (!result?.dispute_letter) return
    
    let finalLetter = result.dispute_letter
    if (user?.user_metadata?.full_name) {
      finalLetter = finalLetter.replace(/\[Patient Name\]/gi, user.user_metadata.full_name)
      finalLetter = finalLetter.replace(/\[Your Name\]/gi, user.user_metadata.full_name)
    }

    const subject = encodeURIComponent("Medical Billing Dispute")
    const body = encodeURIComponent(finalLetter)
    const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&su=${subject}&body=${body}`
    
    window.open(gmailUrl, '_blank')
    setLetterStatus('Opened in Gmail')
  }

  return (
    <section className="section-white section-pad">
      <div className="main">
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }}>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label">
            <span className="line" /> AI Assistant
          </motion.p>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.55 }} className="section-title">
            Hospital Bill <span className="gradient-text">Auditor</span>
          </motion.h1>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-subtitle" style={{ marginBottom: '2rem' }}>
            Upload your medical bill or EOB. We automatically scan for upcoding, unbundling, duplicate charges, and excessive pricing.
          </motion.p>
        </motion.div>

        <div className="grid-2" style={{ alignItems: 'start' }}>
          
          {/* ── Input Panel ────────────────────────────────────────── */}
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.1 }}>
            <div className="card" style={{ padding: '2rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
                <div className="feature-icon red"><IconReceipt size={20} /></div>
                <div>
                  <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Upload or Enter Lines</h3>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Provide the service items to audit</p>
                </div>
              </div>

              {/* Upload Zone */}
              <div className="upload-zone" onClick={() => document.getElementById('bill-upload').click()} style={{ marginBottom: '1.5rem', padding: '1.5rem', border: '2px dashed var(--border-secondary)', borderRadius: '1rem', textAlign: 'center', cursor: 'pointer', background: 'var(--bg-secondary)', transition: 'border-color 0.2s' }} onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'} onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-secondary)'}>
                <IconUpload size={32} style={{ color: 'var(--accent)', marginBottom: '0.75rem' }} />
                <p style={{ fontSize: '0.9375rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>Click to upload PDF or Image</p>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>Auto-extracts all line items instantly</p>
                <input id="bill-upload" type="file" accept="application/pdf,image/*" style={{ display: 'none' }} onChange={handleFileUpload} />
              </div>
              
              {file && (
                <div style={{ padding: '0.875rem 1rem', background: 'var(--accent-subtle)', border: '1px solid var(--accent-border)', borderRadius: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', fontWeight: 600, color: 'var(--accent)' }}>
                    <IconFileText size={16} /> {file.name}
                  </div>
                  <button className="btn btn-ghost" style={{ padding: '0.25rem' }} onClick={() => setFile(null)}><IconX size={16} /></button>
                </div>
              )}

              {/* Divider */}
              {!file && <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', margin: '1.5rem 0' }}>
                <div style={{ flex: 1, height: '1px', background: 'var(--border-secondary)' }} />
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>OR MANUAL ENTRY</span>
                <div style={{ flex: 1, height: '1px', background: 'var(--border-secondary)' }} />
              </div>}

              {/* Manual Entry Table */}
              {!file && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.5rem' }}>
                  {lines.map((line, idx) => (
                    <div key={idx} style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                      <div style={{ width: '24px', height: '36px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)' }}>{idx + 1}</div>
                      <input className="input" style={{ flex: 1.5, padding: '0.5rem 0.75rem', fontSize: '0.8125rem' }} placeholder="CPT (e.g. 99285)" value={line.cpt_code} onChange={e => updateLine(idx, 'cpt_code', e.target.value.toUpperCase())} />
                      <input className="input" style={{ flex: 1.5, padding: '0.5rem 0.75rem', fontSize: '0.8125rem' }} placeholder="ICD (e.g. J00)" value={line.icd_10_code} onChange={e => updateLine(idx, 'icd_10_code', e.target.value.toUpperCase())} />
                      <input className="input" style={{ flex: 1, padding: '0.5rem 0.75rem', fontSize: '0.8125rem' }} type="number" placeholder="$ Billed" value={line.billed_amount} onChange={e => updateLine(idx, 'billed_amount', e.target.value)} />
                      <button className="btn btn-ghost" style={{ width: '36px', height: '36px', padding: 0, flexShrink: 0 }} onClick={() => removeLine(idx)} disabled={lines.length === 1}><IconX size={16} /></button>
                    </div>
                  ))}
                  <button className="btn btn-outline" style={{ alignSelf: 'flex-start', padding: '0.5rem 1rem', fontSize: '0.8125rem' }} onClick={addLine}>
                    <IconPlus size={14} /> Add Line Item
                  </button>
                </div>
              )}

              {error && (
                <div style={{ padding: '0.75rem 1rem', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: '0.5rem', color: 'var(--danger)', fontSize: '0.8125rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <IconAlertTriangle size={16} /> {error}
                </div>
              )}

              <button className="btn btn-red" style={{ width: '100%', padding: '1rem', fontSize: '1rem' }} onClick={handleAudit} disabled={loading || (!file && !lines[0].cpt_code && !lines[0].billed_amount)}>
                {loading ? <><span className="spinner" /> Analyzing Bill...</> : <><IconActivity size={18} /> Audit Bill</>}
              </button>
            </div>
          </motion.div>

          {/* ── Results Panel ──────────────────────────────────────── */}
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
            <AnimatePresence mode="wait">
              {!result ? (
                <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="card" style={{ padding: '3rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
                  <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'var(--bg-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', marginBottom: '1.25rem' }}>
                    <IconReceipt size={32} />
                  </div>
                  <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Awaiting Audit</h3>
                  <p style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', maxWidth: '280px' }}>Upload a bill or enter service lines on the left to see potential savings and errors.</p>
                </motion.div>

              ) : (
                <motion.div key="results" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="card" style={{ overflow: 'hidden' }}>
                  
                  {/* Hero Banner */}
                  <div style={{ padding: '2.5rem 2rem', background: result.overall_risk === 'high' ? 'linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)' : result.overall_risk === 'medium' ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' : 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: '#fff', textAlign: 'center' }}>
                    <p style={{ fontSize: '0.875rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', opacity: 0.9, marginBottom: '0.5rem' }}>
                      {result.overall_risk === 'low' ? 'Looks Clean' : 'Errors Detected'}
                    </p>
                    {result.potential_savings ? (
                      <>
                        <h2 style={{ fontSize: '2.5rem', fontWeight: 900, marginBottom: '0.25rem', letterSpacing: '-0.02em' }}>${result.potential_savings.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</h2>
                        <p style={{ fontSize: '0.9375rem', fontWeight: 500, opacity: 0.9 }}>Estimated Potential Savings</p>
                      </>
                    ) : (
                      <h2 style={{ fontSize: '2rem', fontWeight: 800, letterSpacing: '-0.02em' }}>No major savings found</h2>
                    )}
                  </div>

                  {/* Summary Stats */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px', background: 'var(--border-secondary)' }}>
                    <div style={{ padding: '1.25rem', background: 'var(--bg-card)', textAlign: 'center' }}>
                      <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Billed</p>
                      <p style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>${result.total_billed.toLocaleString(undefined, {minimumFractionDigits: 2})}</p>
                    </div>
                    <div style={{ padding: '1.25rem', background: 'var(--bg-card)', textAlign: 'center' }}>
                      <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Fair Est.</p>
                      <p style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>{result.estimated_fair_total ? `$${result.estimated_fair_total.toLocaleString(undefined, {minimumFractionDigits: 2})}` : 'N/A'}</p>
                    </div>
                  </div>

                  <div style={{ padding: '2rem' }}>
                    <p style={{ fontSize: '0.9375rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '2rem' }}>{result.summary}</p>

                    {/* Flags List */}
                    {result.flags.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2rem' }}>
                        <h4 style={{ fontSize: '0.875rem', fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid var(--border-secondary)', paddingBottom: '0.5rem' }}>Detected Issues</h4>
                        {result.flags.map((flag, idx) => (
                          <div key={idx} style={{ padding: '1.25rem', borderRadius: '1rem', background: flag.severity === 'critical' ? 'var(--danger-bg)' : 'var(--warning-bg)', border: `1px solid ${flag.severity === 'critical' ? 'var(--danger-border)' : 'var(--warning-border)'}` }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                              <span style={{ display: 'inline-flex', padding: '0.25rem 0.625rem', borderRadius: '999px', fontSize: '0.6875rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em', background: flag.severity === 'critical' ? '#fee2e2' : '#fef3c7', color: flag.severity === 'critical' ? '#b91c1c' : '#b45309' }}>
                                Line {flag.line_number} • {flag.issue_type.replace('_', ' ')}
                              </span>
                              {flag.estimated_savings && (
                                <span style={{ fontSize: '0.875rem', fontWeight: 800, color: flag.severity === 'critical' ? 'var(--danger)' : 'var(--warning)' }}>-${flag.estimated_savings.toLocaleString()}</span>
                              )}
                            </div>
                            <p style={{ fontSize: '0.875rem', color: 'var(--text-primary)', fontWeight: 600, marginBottom: '0.375rem', lineHeight: 1.5 }}>{flag.description}</p>
                            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}><strong>Recommendation:</strong> {flag.recommendation}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Dispute Action */}
                    {result.flags.length > 0 && (
                      <div style={{ background: 'var(--bg-secondary)', borderRadius: '1rem', padding: '1.5rem', border: '1px solid var(--border-secondary)', textAlign: 'center' }}>
                        {!result.dispute_letter ? (
                          <>
                            <h4 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Take Action</h4>
                            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1.25rem', maxWidth: '300px', margin: '0 auto 1.25rem' }}>Generate a formal dispute letter citing these exact billing errors to send to the hospital.</p>
                            <button className="btn btn-red" onClick={handleGenerateLetter} disabled={letterLoading}>
                              {letterLoading ? <><span className="spinner" /> Drafting...</> : <><IconFileText size={16} /> Draft Dispute Letter</>}
                            </button>
                            {letterStatus && <p style={{ fontSize: '0.8125rem', color: 'var(--danger)', marginTop: '0.75rem' }}>{letterStatus}</p>}
                          </>
                        ) : (
                          <>
                            <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '48px', height: '48px', borderRadius: '50%', background: 'var(--success-bg)', color: 'var(--success)', marginBottom: '1rem' }}>
                              <IconCheckCircle size={24} />
                            </div>
                            <h4 style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '1.25rem' }}>Letter Ready</h4>
                            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
                              <button className="btn btn-red" onClick={handleOpenGmail}><IconMail size={16} /> Open in Gmail</button>
                              <button className="btn btn-outline" onClick={handleDownloadPDF}><IconDownload size={16} /> Download PDF</button>
                              <button className="btn btn-outline" onClick={() => { navigator.clipboard.writeText(result.dispute_letter); setLetterStatus('Copied!') }}><IconCopy size={16} /> Copy Text</button>
                            </div>
                            {letterStatus && <p style={{ fontSize: '0.8125rem', color: 'var(--success)', marginTop: '0.75rem', fontWeight: 600 }}>{letterStatus}</p>}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </div>

        {/* ── Saved Cloud Audits ── */}
        {savedAudits.length > 0 && (
          <div style={{ marginTop: '3.5rem', borderTop: '1px solid var(--border-secondary)', paddingTop: '2.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', marginBottom: '1.5rem' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>Saved Cloud Audits</h3>
              <span style={{
                padding: '2px 8px', borderRadius: '9999px', background: '#ecfdf5', color: '#059669',
                border: '1px solid #a7f3d0', fontSize: '0.7rem', fontWeight: 700
              }}>
                ☁ Cloud Synced
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1.25rem' }}>
              {savedAudits.map((a) => (
                <div
                  key={a.id}
                  onClick={() => loadSavedReport(a)}
                  style={{
                    background: auditId === a.id ? 'var(--bg-secondary)' : 'var(--bg-card)',
                    border: auditId === a.id ? '1.5px solid var(--danger)' : '1px solid var(--border-secondary)',
                    borderRadius: '1.25rem', padding: '1.5rem', cursor: 'pointer', transition: 'all 0.2s ease',
                    boxShadow: auditId === a.id ? '0 0 0 3px var(--danger-bg)' : 'none'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem', marginBottom: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span className={`badge ${a.overall_risk === 'high' ? 'badge-danger' : a.overall_risk === 'medium' ? 'badge-warning' : 'badge-success'}`} style={{ textTransform: 'uppercase', fontSize: '0.65rem' }}>
                        {a.overall_risk} Risk
                      </span>
                      <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                        {a.source === 'upload' ? '📁 Uploaded Bill' : '✍ Manual Scan'}
                      </span>
                    </div>
                    <button
                      className="btn btn-ghost"
                      style={{ padding: '0.25rem 0.5rem', color: 'var(--danger)', fontSize: '0.8rem' }}
                      onClick={(e) => deleteAudit(a.id, e)}
                      title="Delete saved audit"
                    >
                      🗑
                    </button>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', background: 'var(--bg-secondary)', padding: '0.75rem 1rem', borderRadius: '0.75rem' }}>
                    <div>
                      <p style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Billed Amount</p>
                      <p style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--text-primary)' }}>${Number(a.total_billed || 0).toLocaleString()}</p>
                    </div>
                    {a.potential_savings > 0 && (
                      <div style={{ textAlign: 'right' }}>
                        <p style={{ fontSize: '0.7rem', fontWeight: 600, color: '#059669', textTransform: 'uppercase' }}>Est. Savings</p>
                        <p style={{ fontSize: '1.125rem', fontWeight: 800, color: '#059669' }}>-${Number(a.potential_savings).toLocaleString()}</p>
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                    <span>{new Date(a.created_at).toLocaleDateString()}</span>
                    <span style={{ fontWeight: 700, color: auditId === a.id ? 'var(--danger)' : 'var(--text-primary)' }}>
                      {auditId === a.id ? '✓ Currently Viewing' : 'Click to Load →'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
