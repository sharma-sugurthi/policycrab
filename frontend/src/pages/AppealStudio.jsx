import React, { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { jsPDF } from 'jspdf'
import { 
  IconWand, IconPackage, IconPrinter, IconLayers, 
  IconType, IconBookOpen, IconChevronRight, IconCornerUpLeft,
  IconArrowRight, IconCheckCircle, IconAlertTriangle,
  IconCopy, IconDownload, IconScale, IconFileText
} from '../components/Icons'
import { apiFetch, readApiResponse, formatApiError } from '../lib/api'

// ── Smart Send Panel ──────────────────────────────────────────────────────────
function SmartSendPanel({ policyProfile, claimCase, currentLetter }) {
  const [suggestion, setSuggestion] = useState(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [sendingDirect, setSendingDirect] = useState(false)
  const [sentDirect, setSentDirect] = useState(false)

  const carrierName = policyProfile?.carrier_name
  const state = policyProfile?.state
  const claimId = claimCase?.claim_id || 'DRAFT'

  useEffect(() => {
    if (!carrierName || !state) return
    const fetchSuggestion = async () => {
      setLoading(true)
      try {
        const res = await apiFetch('/api/email/smart-suggest', {
          method: 'POST',
          body: JSON.stringify({ carrier_name: carrierName, state, appeal_level: 1 })
        })
        const data = await readApiResponse(res)
        if (res.ok) setSuggestion(data)
      } catch {/* silent */} finally {
        setLoading(false)
      }
    }
    fetchSuggestion()
  }, [carrierName, state])

  const handleOpenMailto = async () => {
    if (!suggestion?.suggestions?.length) return
    const topEmail = suggestion.suggestions[0].email
    try {
      const res = await apiFetch('/api/email/build-mailto', {
        method: 'POST',
        body: JSON.stringify({
          to_email: topEmail,
          carrier_name: carrierName,
          patient_name: 'Patient',
          claim_id: claimId,
          appeal_text: currentLetter,
          appeal_level: 1,
        })
      })
      const data = await readApiResponse(res)
      if (res.ok) window.location.href = data.mailto_uri
    } catch {/* silent */}
  }

  const handleDirectSend = async () => {
    setSendingDirect(true)
    try {
      const res = await apiFetch('/api/email/send-appeal', {
        method: 'POST',
        body: JSON.stringify({ claim_id: claimId, appeal_text: currentLetter })
      })
      if (res.ok) setSentDirect(true)
    } catch {/* silent */} finally {
      setSendingDirect(false)
    }
  }

  const handleCopyEmail = (email) => {
    navigator.clipboard.writeText(email)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const confidenceColors = { HIGH: '#10b981', MEDIUM: '#f59e0b', LOW: '#ef4444' }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
      style={{
        marginTop: '2rem',
        background: 'linear-gradient(135deg, rgba(59,130,246,0.08), rgba(168,85,247,0.05))',
        border: '1px solid rgba(59,130,246,0.25)',
        borderRadius: '16px',
        padding: '1.75rem',
      }}
    >
      <h2 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
        📬 Send Your Appeal
      </h2>

      {loading && (
        <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem' }}>🔍 Finding carrier appeals address…</p>
      )}

      {!loading && suggestion && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

          {/* Suggested emails */}
          {suggestion.suggestions.map((s, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem',
              background: 'var(--bg-card, #fff)', borderRadius: '10px', padding: '0.875rem 1rem',
              border: '1px solid var(--border-primary)',
            }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '2px' }}>{s.label}</div>
                <div style={{ fontWeight: 700, fontSize: '0.9375rem', color: 'var(--text-primary)' }}>{s.email}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{
                  padding: '2px 10px', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 700,
                  background: (confidenceColors[s.confidence] || '#3b82f6') + '20',
                  color: confidenceColors[s.confidence] || '#3b82f6',
                  border: `1px solid ${(confidenceColors[s.confidence] || '#3b82f6')}40`,
                }}>{s.confidence}</span>
                <button onClick={() => handleCopyEmail(s.email)} className="btn btn-ghost"
                  style={{ padding: '0.375rem 0.75rem', fontSize: '0.75rem', border: '1px solid var(--border-primary)' }}>
                  {copied ? '✓ Copied!' : '📋 Copy'}
                </button>
              </div>
            </div>
          ))}

          {/* Fax / Portal info */}
          {(suggestion.fax_number || suggestion.submission_portal_url) && (
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              {suggestion.fax_number && (
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>
                  📠 Fax: <strong style={{ color: 'var(--text-primary)' }}>{suggestion.fax_number}</strong>
                </span>
              )}
              {suggestion.submission_portal_url && (
                <a href={suggestion.submission_portal_url} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize: '0.8125rem', color: 'var(--accent)', fontWeight: 600 }}>
                  🌐 Carrier Portal →
                </a>
              )}
            </div>
          )}

          {/* Send CTAs */}
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
            <button
              onClick={handleOpenMailto}
              className="btn btn-red"
              style={{ padding: '0.75rem 1.5rem', fontSize: '0.9rem' }}
            >
              📧 Open in Gmail / Mail App
            </button>
            <button
              onClick={handleDirectSend}
              disabled={sendingDirect || sentDirect}
              className="btn btn-outline"
              style={{ padding: '0.75rem 1.5rem', fontSize: '0.9rem' }}
            >
              {sentDirect ? '✅ Sent via PolicyCrab!' : sendingDirect ? '⏳ Sending…' : '✉️ Send via PolicyCrab'}
            </button>
          </div>

          <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>
            💡 <strong>Tip:</strong> Emails from your personal Gmail/Outlook clear insurer spam filters more reliably than bulk senders.
          </p>
        </div>
      )}

      {!loading && !suggestion && (
        <p style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)' }}>
          Carrier email not found in directory. Use the "Send via PolicyCrab" button to send to your own inbox.
          <button onClick={handleDirectSend} disabled={sendingDirect || sentDirect} className="btn btn-outline"
            style={{ marginLeft: '1rem', padding: '0.5rem 1rem', fontSize: '0.8125rem' }}>
            {sentDirect ? '✅ Sent!' : sendingDirect ? '⏳…' : '✉️ Send to My Inbox'}
          </button>
        </p>
      )}
    </motion.div>
  )
}


export default function AppealStudio() {
  const location = useLocation()
  const navigate = useNavigate()
  
  // Data passed from ClaimEvaluator
  const state = location.state || {}
  const { 
    letter: initialLetter, 
    policyProfile, 
    claimCase, 
    appealOutput, 
    eobHighlights, 
    costBreakdown 
  } = state

  const [currentLetter, setCurrentLetter] = useState(initialLetter || '')
  const [revisionHistory, setRevisionHistory] = useState([])
  const [loadingAction, setLoadingAction] = useState(null)
  const [dossierLoading, setDossierLoading] = useState(false)
  const [error, setError] = useState(null)
  
  const [lastRevisionResult, setLastRevisionResult] = useState(null)

  // Redirect if accessed directly without state
  useEffect(() => {
    if (!initialLetter) {
      navigate('/dashboard')
    }
  }, [initialLetter, navigate])

  if (!initialLetter) return null

  // ── 1. Apply AI Revision ─────────────────────────────
  const handleRevise = async (actionType) => {
    setLoadingAction(actionType)
    setError(null)
    setLastRevisionResult(null)

    try {
      const response = await apiFetch('/studio/revise', {
        method: 'POST',
        body: JSON.stringify({
          action_type: actionType,
          current_letter: currentLetter,
          context_claim_id: claimCase?.claim_id || '',
          context_denial_reason: claimCase?.denial_reason_text || ''
        })
      })

      const result = await readApiResponse(response)

      if (!response.ok) {
        throw new Error(formatApiError(result))
      }

      if (result.success) {
        // Save current state to history for undo
        setRevisionHistory(prev => [...prev, currentLetter])
        setCurrentLetter(result.revised_letter)
        setLastRevisionResult(result)
      } else {
        // Soft failure — LLM rate limit or parse error
        setError(result.change_summary || 'Failed to apply revision. Your original draft was kept safe.')
      }

    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingAction(null)
    }
  }

  const handleUndo = () => {
    if (revisionHistory.length > 0) {
      const previous = revisionHistory[revisionHistory.length - 1]
      setCurrentLetter(previous)
      setRevisionHistory(prev => prev.slice(0, -1))
      setLastRevisionResult(null)
      setError(null)
    }
  }

  // ── 2. Export / Copy Handlers ─────────────────────────
  const handleCopy = () => {
    navigator.clipboard.writeText(currentLetter)
    alert("Letter copied to clipboard!")
  }

  const handleDownloadTxt = () => {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([currentLetter], { type: 'text/plain' }))
    a.download = `appeal-draft.txt`
    a.click()
  }

  // ── 3. Compile & Download Dossier PDF ────────────────
  const handleGenerateDossier = async () => {
    setDossierLoading(true)
    setError(null)

    try {
      // Step 1: Request structured dossier compilation from backend
      const response = await apiFetch('/studio/dossier', {
        method: 'POST',
        body: JSON.stringify({
          letter_text: currentLetter,
          claim_case: claimCase,
          policy_profile: policyProfile,
          cost_breakdown: costBreakdown,
          appeal_output: appealOutput,
          eob_highlights: eobHighlights
        })
      })

      const dossier = await readApiResponse(response)

      if (!response.ok) {
        throw new Error(formatApiError(dossier))
      }

      // Step 2: Render PDF client-side using jsPDF
      const doc = new jsPDF()
      let y = 20
      
      const addPageIfNeeded = (requiredSpace = 20) => {
        if (y + requiredSpace > 280) {
          doc.addPage()
          y = 20
          // Footer
          doc.setFontSize(8)
          doc.setTextColor(150, 150, 150)
          doc.text("Generated by PolicyCrab AI Advocate", 105, 290, { align: 'center' })
          doc.setTextColor(0, 0, 0)
        }
      }

      // Title Page
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(22)
      doc.setTextColor(225, 29, 72) // Accent Red
      doc.text("Medical Claim Appeal Dossier", 105, y, { align: 'center' })
      y += 10
      
      doc.setFontSize(10)
      doc.setTextColor(100, 100, 100)
      doc.text(`Generated: ${new Date(dossier.generated_at).toLocaleDateString()}`, 105, y, { align: 'center' })
      y += 20

      // Case Summary block
      doc.setFontSize(14)
      doc.setTextColor(0, 0, 0)
      doc.text("Case Summary", 20, y)
      y += 8
      
      doc.setFontSize(11)
      doc.setFont('helvetica', 'normal')
      const summaryItems = [
        `Claim ID: ${dossier.cover?.claim_id || 'N/A'}`,
        `Insurance Carrier: ${dossier.cover?.insurance_carrier || 'N/A'}`,
        `Date of Service: ${dossier.case_summary?.date_of_service || 'N/A'}`,
        `Billed Amount: $${dossier.case_summary?.billed_amount?.toLocaleString() || '0'}`,
        `Patient Responsibility: $${dossier.case_summary?.patient_responsibility?.toLocaleString() || '0'}`,
      ]
      summaryItems.forEach(item => {
        doc.text(item, 25, y)
        y += 7
      })
      
      y += 10

      // Render Sections
      for (const section of dossier.sections) {
        addPageIfNeeded(30)
        
        doc.setFontSize(16)
        doc.setFont('helvetica', 'bold')
        doc.setTextColor(225, 29, 72)
        doc.text(section.title, 20, y)
        y += 10
        
        doc.setFontSize(11)
        doc.setFont('helvetica', 'normal')
        doc.setTextColor(0, 0, 0)

        if (section.section_type === 'letter') {
          const lines = doc.splitTextToSize(section.content, 170)
          for (let i = 0; i < lines.length; i++) {
            addPageIfNeeded(10)
            doc.text(lines[i], 20, y)
            y += 6
          }
        } else if (section.section_type === 'policy_citations') {
          doc.text(section.content, 20, y)
          y += 10
          section.items?.forEach(item => {
            addPageIfNeeded(30)
            doc.setFont('helvetica', 'bold')
            doc.text(`Page ${item.page}:`, 25, y)
            y += 6
            doc.setFont('helvetica', 'italic')
            const quoteLines = doc.splitTextToSize(`"${item.text}"`, 160)
            doc.text(quoteLines, 30, y)
            y += (quoteLines.length * 6) + 4
            
            if (item.mistake) {
              doc.setFont('helvetica', 'bold')
              doc.setTextColor(220, 38, 38)
              doc.text(`Error: ${item.mistake}`, 30, y)
              doc.setTextColor(0, 0, 0)
              y += 8
            }
          })
        } else if (section.section_type === 'next_steps') {
          section.items?.forEach((item, idx) => {
            addPageIfNeeded(15)
            doc.setFont('helvetica', 'bold')
            doc.text(`${idx + 1}.`, 20, y)
            doc.setFont('helvetica', 'normal')
            const stepLines = doc.splitTextToSize(item.step, 160)
            doc.text(stepLines, 28, y)
            y += (stepLines.length * 6) + 4
          })
        } else {
          // Generic section render
          const lines = doc.splitTextToSize(section.content || '', 170)
          doc.text(lines, 20, y)
          y += (lines.length * 6) + 4
        }
        y += 10
      }

      doc.save(`Appeal-Dossier-${dossier.cover?.claim_id || 'Draft'}.pdf`)

    } catch (err) {
      setError(err.message)
    } finally {
      setDossierLoading(false)
    }
  }

  // ── Toolbar Button Definitions ───────────────────────
  const REVISION_ACTIONS = [
    { id: 'assertive', label: 'More Assertive', desc: 'Stronger legal tone', icon: <IconScale size={20} /> },
    { id: 'penalties', label: 'State Penalties', desc: 'Emphasize regulations', icon: <IconLayers size={20} /> },
    { id: 'simplify', label: 'Simplify', desc: 'For online web forms', icon: <IconType size={20} /> },
    { id: 'medical_urgency', label: 'Medical Urgency', desc: 'Highlight care impact', icon: <IconWand size={20} /> },
  ]

  return (
    <section className="section-white section-pad">
      <div className="main">
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }} style={{ marginBottom: '2rem' }}>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label">
            <span className="line" /> Appeal Workspace
          </motion.p>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.55 }} className="section-title">
            Appeal <span className="gradient-text">Studio</span>
          </motion.h1>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-subtitle">
            Revise your appeal draft, assemble evidence, and export a submission packet with consistent formatting.
          </motion.p>
        </motion.div>

        <div style={{ marginBottom: '1.75rem' }}>
          <button onClick={() => navigate(-1)} className="btn btn-ghost" style={{ padding: 0, fontSize: '0.875rem', color: 'var(--text-tertiary)' }}>
            ← Back to Evaluator
          </button>
        </div>

        <div className="studio-layout">
        
        {/* Zone A: AI Co-Pilot Toolbar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconWand size={18} style={{ color: 'var(--accent)' }}/> AI Co-Pilot Revisions
            </h2>
            {revisionHistory.length > 0 && (
              <button onClick={handleUndo} className="btn btn-ghost" style={{ fontSize: '0.8125rem', color: 'var(--warning)' }}>
                <IconCornerUpLeft size={16} /> Undo Last Edit
              </button>
            )}
          </div>

          <div className="studio-toolbar">
            {REVISION_ACTIONS.map(action => (
              <button 
                key={action.id}
                className="studio-action-btn"
                onClick={() => handleRevise(action.id)}
                disabled={loadingAction !== null}
              >
                {loadingAction === action.id ? (
                  <span className="spinner" style={{ width: '20px', height: '20px', borderWidth: '2px', borderColor: 'var(--accent)', borderTopColor: 'transparent' }} />
                ) : (
                  action.icon
                )}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.125rem' }}>
                  <span>{action.label}</span>
                  <span style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)', fontWeight: 500 }}>{action.desc}</span>
                </div>
              </button>
            ))}
          </div>

          {error && (
            <div style={{ padding: '1rem', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: 'var(--radius-lg)', color: 'var(--danger)', fontSize: '0.875rem', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconAlertTriangle size={18} /> {error}
            </div>
          )}

          {lastRevisionResult && (
            <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="studio-revision-alert">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <IconCheckCircle size={18} style={{ color: 'var(--success)' }} />
                <strong style={{ color: 'var(--success)' }}>Revision Applied: {lastRevisionResult.change_summary}</strong>
              </div>
              {lastRevisionResult.focus_bullets?.length > 0 && (
                <ul style={{ paddingLeft: '2rem', fontSize: '0.875rem', color: 'var(--success)', display: 'flex', flexDirection: 'column', gap: '0.25rem', listStyle: 'disc' }}>
                  {lastRevisionResult.focus_bullets.map((bullet, i) => (
                    <li key={i}>{bullet}</li>
                  ))}
                </ul>
              )}
            </motion.div>
          )}
        </div>

        {/* Zone B: Rich Document Editor */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconFileText size={18} /> Draft Document
            </h2>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button onClick={handleCopy} className="btn btn-outline" style={{ padding: '0.5rem 1rem', fontSize: '0.8125rem' }}><IconCopy size={16}/> Copy</button>
              <button onClick={handleDownloadTxt} className="btn btn-outline" style={{ padding: '0.5rem 1rem', fontSize: '0.8125rem' }}><IconDownload size={16}/> .txt</button>
            </div>
          </div>

          <div className="studio-editor-panel">
            <div className="studio-letter-content">
              {currentLetter}
            </div>
          </div>
          
          <div style={{ textAlign: 'right', marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>
            {currentLetter.split(/\s+/).length} words
          </div>
        </div>

        {/* Zone C: Evidence Dossier Panel */}
        <div style={{ marginTop: '2rem' }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <IconPackage size={18} /> Official Evidence Dossier
          </h2>
          
          <div className="studio-dossier-panel">
            <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'var(--bg-card)', border: '1px solid var(--border-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem', color: 'var(--accent)', boxShadow: 'var(--shadow-sm)' }}>
              <IconPrinter size={28} />
            </div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
              Compile Official Submission Packet
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem', maxWidth: '32rem', margin: '0 auto 2rem', lineHeight: 1.6 }}>
              We'll package your revised letter, EOB highlights, and exact policy contradictions into a single formatted PDF, ready to fax or mail to your insurer.
            </p>

            <button 
              onClick={handleGenerateDossier}
              disabled={dossierLoading}
              className="btn btn-red"
              style={{ fontSize: '1rem', padding: '1rem 2.5rem' }}
            >
              {dossierLoading ? (
                <><span className="spinner" style={{ width: '18px', height: '18px', borderWidth: '2px' }}/> Compiling PDF...</>
              ) : (
                <><IconDownload size={20} /> Generate Multi-Page Dossier</>
              )}
            </button>
          </div>
        </div>

        {/* Zone D: Smart Email Routing */}
        <SmartSendPanel policyProfile={policyProfile} claimCase={claimCase} currentLetter={currentLetter} />

        </div>
      </div>
      </section>
    )
}
