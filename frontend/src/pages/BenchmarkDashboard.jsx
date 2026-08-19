import { Fragment, useState, useEffect, useRef, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'
import { apiFetch, formatApiError, readApiResponse } from '../lib/api'
import { 
  IconBarChart, IconActivity, IconCheckCircle, IconAlertTriangle, 
  IconDownload, IconRefreshCw, IconServer, IconChevronDown, 
  IconChevronUp, IconSearch, IconFileText, IconZap, IconCpu, IconShield, IconCopy
} from '../components/Icons'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

export default function BenchmarkDashboard() {
  const [cases, setCases] = useState([])
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // Test Execution State
  const [running, setRunning] = useState(false)
  const [runMode, setRunMode] = useState(null) // 'quick' | 'full'
  const [taskId, setTaskId] = useState(null)
  const [progress, setProgress] = useState(null)
  const [liveStreamLogs, setLiveStreamLogs] = useState([])
  
  // Filtering State
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedStatus, setSelectedStatus] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedCaseId, setExpandedCaseId] = useState(null)

  const eventSourceRef = useRef(null)

  const normalizeCasesResponse = (payload) => {
    if (!payload) return []
    if (Array.isArray(payload.cases)) return payload.cases
    if (Array.isArray(payload.data?.cases)) return payload.data.cases
    if (Array.isArray(payload.results)) return payload.results
    return []
  }

  const normalizeResultsResponse = (payload) => {
    if (!payload) return null
    if (payload.summary || Array.isArray(payload.results)) return payload
    if (payload.data && (payload.data.summary || Array.isArray(payload.data.results))) return payload.data
    return null
  }

  // ── Initial Load ────────────────────────────────────────────────────
  useEffect(() => {
    fetchData()
    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close()
    }
  }, [])

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [resResults, resCases] = await Promise.all([
        apiFetch('/benchmark/results'),
        apiFetch('/benchmark/cases')
      ])
      
      const resultsData = await readApiResponse(resResults)
      const casesData = await readApiResponse(resCases)
      const normalizedCases = normalizeCasesResponse(casesData)
      const normalizedResults = normalizeResultsResponse(resultsData)
      
      setCases(normalizedCases)
      setResults(normalizedResults)
    } catch (err) {
      setError('Could not load benchmark data from backend: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  // ── Run Evaluation Suite ────────────────────────────────────────────
  const handleStartRun = async (mode) => {
    if (running) return
    setRunning(true)
    setRunMode(mode)
    setError(null)
    setProgress({ completed: 0, total: mode === 'quick' ? 21 : 200, passed: 0, currentStep: 'Initializing engine...' })
    setLiveStreamLogs([])
    
    try {
      const res = await apiFetch('/benchmark/run', {
        method: 'POST',
        body: JSON.stringify({ mode, concurrency: 2 })
      })
      const data = await readApiResponse(res)
      if (data?.task_id) {
        setTaskId(data.task_id)
        connectSSE(data.task_id, mode)
      } else {
        setError(formatApiError(data, 'Failed to initiate evaluation run'))
        setRunning(false)
      }
    } catch (err) {
      setError(err.message)
      setRunning(false)
    }
  }

  const connectSSE = (id, mode) => {
    if (eventSourceRef.current) eventSourceRef.current.close()
    const es = new EventSource(`/api/tasks/${id}/stream`)
    eventSourceRef.current = es

    es.addEventListener('progress', (e) => {
      try {
        const payload = JSON.parse(e.data)
        setProgress({
          completed: payload.completed_cases || 0,
          total: payload.total_cases || (mode === 'quick' ? 21 : 200),
          passed: payload.passed_cases || 0,
          currentStep: payload.current_step || 'Processing...',
          percent: payload.progress || 0
        })
        
        if (payload.latest_case) {
          setLiveStreamLogs(prev => [payload.latest_case, ...prev].slice(0, 50))
        }
      } catch (err) {
        console.error('SSE parse error:', err)
      }
    })

    es.addEventListener('completed', async (e) => {
      try {
        const payload = JSON.parse(e.data)
        if (payload.result) {
          setResults(payload.result)
        } else {
          await fetchData()
        }
      } catch (err) {
        console.error('SSE complete parse error:', err)
        await fetchData()
      } finally {
        es.close()
        setRunning(false)
        setTaskId(null)
      }
    })

    es.addEventListener('failed', (e) => {
      try {
        const payload = JSON.parse(e.data)
        setError('Evaluation run failed: ' + (payload.error || 'Unknown error'))
      } catch (err) {
        setError('Evaluation run disconnected')
      } finally {
        es.close()
        setRunning(false)
        setTaskId(null)
      }
    })

    es.onerror = () => {
      // If error occurs, check status via regular fetch after a short delay
      setTimeout(async () => {
        try {
          const res = await apiFetch(`/tasks/${id}`)
          const taskData = await readApiResponse(res)
          if (taskData?.state === 'SUCCESS' || taskData?.status === 'done') {
            setResults(taskData.result || taskData.task?.result || null)
            setRunning(false)
            es.close()
          } else if (taskData?.state === 'FAILURE' || taskData?.status === 'failed') {
            setError(taskData.error || taskData.task?.error || 'Task failed')
            setRunning(false)
            es.close()
          }
        } catch (err) {
          console.error('Task polling check failed:', err)
        }
      }, 3000)
    }
  }

  // ── Report Export Handlers ──────────────────────────────────────────
  const handleDownloadJSON = () => {
    if (!results) return
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(results, null, 2))
    const downloadAnchor = document.createElement('a')
    downloadAnchor.setAttribute("href", dataStr)
    downloadAnchor.setAttribute("download", `policycrab-benchmark-${new Date().toISOString().slice(0,10)}.json`)
    document.body.appendChild(downloadAnchor)
    downloadAnchor.click()
    downloadAnchor.remove()
  }

  const handleExportPDF = () => {
    if (!results) return
    const doc = new jsPDF({ unit: 'pt', format: 'letter' })
    const margin = 54
    const pageW = doc.internal.pageSize.getWidth()
    let y = margin

    // Title & Badge
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(20)
    doc.setTextColor(220, 38, 38)
    doc.text('PolicyCrab AI - Official Medical Claim Reasoning Report', margin, y)
    y += 24
    
    doc.setFontSize(12)
    doc.setTextColor(60)
    doc.text('Multi-Agent Medical Billing & Triage Efficiency Suite', margin, y)
    y += 20
    
    doc.setDrawColor(220, 38, 38)
    doc.setLineWidth(1.5)
    doc.line(margin, y, pageW - margin, y)
    y += 25

    // Summary Section
    const sum = results.summary || {}
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(14)
    doc.setTextColor(30)
    doc.text('1. Executive Triage Automation Summary', margin, y)
    y += 20

    doc.setFont('times', 'normal')
    doc.setFontSize(11)
    doc.text(`Total Evaluated Scenarios: ${sum.total || 0} cases`, margin + 10, y)
    y += 18
    doc.text(`Successfully Correct Reasoning: ${sum.passed || 0} cases`, margin + 10, y)
    y += 18
    doc.text(`Autonomous Resolution Rate: ${sum.accuracy_percent || 0}% (Target: ≥ 85.0% Automation, 15% Escalation)`, margin + 10, y)
    y += 18
    doc.text(`Execution Mode: ${sum.mode ? sum.mode.toUpperCase() : 'FULL SUITE'}`, margin + 10, y)
    y += 18
    doc.text(`Date of Evaluation: ${new Date(sum.timestamp ? sum.timestamp * 1000 : Date.now()).toUTCString()}`, margin + 10, y)
    y += 30

    // Category Breakdown Table
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(14)
    doc.text('2. Automation Efficiency by Medical Denial & Billing Fraud Category', margin, y)
    y += 22

    if (sum.categories) {
      Object.entries(sum.categories).forEach(([cat, stats]) => {
        const catName = cat.replace(/_/g, ' ').toUpperCase()
        doc.setFont('helvetica', 'bold')
        doc.setFontSize(10)
        doc.text(`${catName}:`, margin + 10, y)
        doc.setFont('times', 'normal')
        doc.text(`${stats.passed} / ${stats.total} correct (${stats.accuracy}% accuracy)`, margin + 200, y)
        y += 16
        if (y > doc.internal.pageSize.getHeight() - 80) { doc.addPage(); y = margin }
      })
    }
    y += 25

    // Architecture Notes
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(14)
    doc.text('3. Architectural & Scientific Rigor', margin, y)
    y += 20
    doc.setFont('times', 'normal')
    doc.setFontSize(10)
    const notesText = "This automated benchmark suite tests the PolicyCrab multi-agent LangGraph pipeline against 200 synthetic ground-truth US healthcare scenarios. Each test case evaluates the pipeline's capability to detect explicit insurance exclusions, verify emergency EMTALA exceptions, identify No Surprises Act (45 CFR § 149.410) balance billing violations, and catch provider-side upcoding or unbundling errors. The AI engine utilizes advanced multi-tier neuro-symbolic reasoning to achieve high-precision billing alignment."
    const splitNotes = doc.splitTextToSize(notesText, pageW - margin * 2)
    doc.text(splitNotes, margin, y)
    y += (splitNotes.length * 12) + 30

    // Force a new page for the detailed tables if there isn't much space
    if (y > doc.internal.pageSize.getHeight() - 200) {
      doc.addPage()
      y = margin
    }

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(14)
    doc.text('4. Detailed Case Evaluation Log', margin, y)
    y += 15

    // Build table data
    const tableData = (results.results || []).map(r => {
      const expectedRoute = r.expected?.route_decision || r.expected?.triage_path || 'unknown'
      const actualRoute = r.actual?.route_decision || r.actual?.triage_path || 'unknown'
      
      const scenario = r.claim_description ? `PATIENT SCENARIO:\n${r.claim_description}\n\n` : ''
      const rationale = `AI RATIONALE:\n${r.reason || 'Verified match against ground truth.'}`
      
      return [
        `${r.case_id}\n\n${(r.category || '').replace(/_/g, ' ').toUpperCase()}`,
        `Expected:\n${expectedRoute.toUpperCase()}\n\nActual:\n${actualRoute.toUpperCase()}`,
        scenario + rationale,
        r.status === 'pass' ? 'PASS' : 'FAIL'
      ]
    })

    autoTable(doc, {
      startY: y,
      head: [['Case / Category', 'Routing Match', 'Evaluation Narrative', 'Status']],
      body: tableData,
      theme: 'grid',
      headStyles: { fillColor: [220, 38, 38], textColor: 255, fontStyle: 'bold', fontSize: 10 },
      columnStyles: {
        0: { cellWidth: 80, fontStyle: 'bold', fontSize: 9 },
        1: { cellWidth: 80, fontSize: 8 },
        2: { cellWidth: 'auto', fontSize: 9, cellPadding: 8 },
        3: { cellWidth: 50, fontStyle: 'bold', halign: 'center', valign: 'middle' }
      },
      styles: { cellPadding: 6, overflow: 'linebreak' },
      willDrawCell: function(data) {
        // Color-code the Status column
        if (data.section === 'body' && data.column.index === 3) {
          if (data.cell.raw === 'PASS') {
            doc.setTextColor(16, 185, 129) // Emerald 500
          } else {
            doc.setTextColor(239, 68, 68) // Red 500
          }
        }
        // Bold the "PATIENT SCENARIO:" and "AI RATIONALE:" prefixes? 
        // autoTable doesn't support rich text inside a single string easily without parsing,
        // but adding uppercase prefixes provides enough visual distinction.
      },
      didDrawPage: function (data) {
        // Footer page numbering

        const str = 'Page ' + doc.internal.getNumberOfPages()
        doc.setFontSize(10)
        doc.setTextColor(100)
        doc.text(str, data.settings.margin.left, doc.internal.pageSize.getHeight() - 30)
      }
    })
    
    doc.save(`AI-Triage-Report-${new Date().toISOString().slice(0, 10)}.pdf`)
  }

  // ── Compute Metrics & Display Lists ─────────────────────────────────
  const summary = results?.summary || {}
  const accuracy = summary.accuracy_percent !== undefined ? summary.accuracy_percent : 0
  const isTargetMet = accuracy >= 85.0

  const evaluatedList = results?.results || []
  
  // Filter cases for the explorer table
  const displayCases = useMemo(() => evaluatedList.filter(item => {
    if (selectedCategory !== 'all' && item.category !== selectedCategory) return false
    if (selectedStatus !== 'all' && item.status !== selectedStatus) return false
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      const matchId = item.case_id?.toLowerCase().includes(q)
      const matchTitle = item.title?.toLowerCase().includes(q)
      const matchReason = item.reason?.toLowerCase().includes(q)
      return matchId || matchTitle || matchReason
    }
    return true
  }), [evaluatedList, selectedCategory, selectedStatus, searchQuery])

  const categoriesList = [
    { id: 'all', name: 'All Categories' },
    { id: 'nsa_balance_billing', name: 'No Surprises Act' },
    { id: 'upcoding_billing_error', name: 'Upcoding & Billing Fraud' },
    { id: 'explicit_exclusion', name: 'Explicit Exclusions' },
    { id: 'formulary_exception', name: 'Formulary Exceptions' },
    { id: 'emergency_care', name: 'Emergency Care / EMTALA' },
    { id: 'annual_limit', name: 'Annual Limits & Caps' },
    { id: 'prior_auth', name: 'Prior Auth Disputes' },
  ]

  return (
    <section className="section-white section-pad" style={{ minHeight: '100vh' }}>
      <div className="main">
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }}>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label">
            <span className="line" /> Scientific Proof of Reasoning
          </motion.p>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.55 }} className="section-title">
            200-Case Synthetic <span className="gradient-text">Benchmark Engine</span>
          </motion.h1>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-subtitle" style={{ marginBottom: '2.5rem' }}>
            Real-time verification of multi-agent advocacy reasoning accuracy against ground-truth US medical denial, EMTALA protection, No Surprises Act, and hospital upcoding datasets.
          </motion.p>
        </motion.div>

        {/* ── Top Control Deck & KPI Banner ────────────────────────────── */}
        <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }} style={{ marginBottom: '2.5rem' }}>
          <div className="card" style={{ padding: '2rem', background: 'var(--bg-card)', border: '1px solid var(--border-secondary)' }}>
            <div style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1.5rem', marginBottom: '2rem' }}>
              <div>
                <h3 style={{ fontWeight: 800, fontSize: '1.25rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                  <IconActivity size={22} style={{ color: 'var(--accent)' }} /> 
                  Human-in-the-Loop Automation Triage Rate (Target: ≥ 85.0%)
                </h3>
                <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                  {results ? `Latest Run: ${new Date(summary.timestamp * 1000).toLocaleString()} (${summary.mode === 'quick' ? '21-Case Quick Validation' : '200-Case Full Suite'})` : 'No test report loaded yet. Start an evaluation below.'}
                </p>
              </div>
              
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <button 
                  className="btn btn-outline" 
                  style={{ padding: '0.625rem 1.125rem', fontSize: '0.875rem', fontWeight: 700, borderRadius: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }} 
                  onClick={() => handleStartRun('quick')} 
                  disabled={running}
                >
                  <IconZap size={16} /> Quick Test (21 Cases)
                </button>
                <button 
                  className="btn btn-red" 
                  style={{ padding: '0.625rem 1.25rem', fontSize: '0.875rem', fontWeight: 700, borderRadius: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }} 
                  onClick={() => handleStartRun('full')} 
                  disabled={running}
                >
                  <IconCpu size={16} /> Run Full Suite (200 Cases)
                </button>
                {results && (
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button className="btn btn-outline" style={{ padding: '0.625rem 1rem', fontSize: '0.875rem' }} onClick={handleExportPDF} title="Download Official Evaluation Report (PDF)">
                      <IconFileText size={16} /> Export PDF
                    </button>
                    <button className="btn btn-ghost" style={{ padding: '0.625rem' }} onClick={handleDownloadJSON} title="Download Raw Results JSON">
                      <IconDownload size={18} />
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Live Progress Box during test run */}
            <AnimatePresence>
              {running && progress && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} style={{ overflow: 'hidden', marginBottom: '1.5rem', background: 'var(--accent-subtle)', border: '1px solid var(--accent-border)', borderRadius: '1rem', padding: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                    <span style={{ fontWeight: 800, fontSize: '0.9375rem', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span className="spinner" style={{ width: '16px', height: '16px', borderTopColor: 'var(--accent)' }} />
                      Executing Multi-Agent Evaluation: {progress.currentStep}
                    </span>
                    <span style={{ fontWeight: 800, fontSize: '0.9375rem', color: 'var(--text-primary)' }}>
                      {progress.completed} / {progress.total} Cases ({progress.passed} Passed)
                    </span>
                  </div>
                  <div style={{ width: '100%', height: '10px', background: 'rgba(0,0,0,0.08)', borderRadius: '999px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(100, Math.max(5, (progress.completed / progress.total) * 100))}%`, height: '100%', background: 'var(--accent)', transition: 'width 0.3s ease' }} />
                  </div>

                  {/* Live AI Reasoning Terminal */}
                  {liveStreamLogs.length > 0 && (
                    <div style={{ marginTop: '1rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', animation: 'pulse 1.5s infinite' }} /> Live AI Reasoning Feed
                        </span>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#10b981', fontFamily: 'monospace' }}>
                          Auto-Resolution: {progress.completed > 0 ? ((progress.passed / progress.completed) * 100).toFixed(1) : '0.0'}% ({progress.passed}/{progress.completed})
                        </span>
                      </div>
                      <div 
                        ref={el => { if (el) el.scrollTop = el.scrollHeight }}
                        style={{ 
                          background: '#09090b', borderRadius: '0.75rem', padding: '1rem', 
                          fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace", 
                          fontSize: '0.8125rem', color: '#a1a1aa', 
                          maxHeight: '280px', overflowY: 'auto', 
                          border: '1px solid #27272a',
                          scrollBehavior: 'smooth'
                        }}
                      >
                        {/* Reverse to show oldest first (chronological) for terminal feel */}
                        {[...liveStreamLogs].reverse().map((log, idx) => (
                          <div key={idx} style={{ 
                            padding: '0.375rem 0', 
                            borderBottom: idx < liveStreamLogs.length - 1 ? '1px solid #1a1a1e' : 'none',
                            display: 'flex', alignItems: 'flex-start', gap: '0.625rem'
                          }}>
                            <span style={{ 
                              color: log.status === 'pass' ? '#10b981' : '#ef4444', 
                              fontWeight: 800, flexShrink: 0, width: '70px'
                            }}>
                              {log.status === 'pass' ? '✔ PASS' : '✘ FAIL'}
                            </span>
                            <span style={{ color: '#e4e4e7', fontWeight: 700, flexShrink: 0, width: '90px' }}>
                              {log.case_id}
                            </span>
                            <span style={{ 
                              fontSize: '0.6875rem', fontWeight: 700, padding: '0.125rem 0.5rem', 
                              borderRadius: '999px', flexShrink: 0,
                              background: '#1a1a2e', color: '#818cf8', border: '1px solid #312e81'
                            }}>
                              {(log.category || '').replace(/_/g, ' ')}
                            </span>
                            <span style={{ color: '#71717a', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {log.reason}
                            </span>
                            {log.duration_ms && (
                              <span style={{ color: '#a78bfa', fontWeight: 600, flexShrink: 0, fontSize: '0.75rem' }}>
                                {(log.duration_ms / 1000).toFixed(1)}s
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Error Message */}
            {error && (
              <div style={{ padding: '1rem', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: '0.75rem', color: 'var(--danger)', fontWeight: 600, fontSize: '0.875rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <IconAlertTriangle size={18} /> {error}
              </div>
            )}

            {/* Metric Gauges Grid */}
            <div className="grid-4" style={{ gap: '1rem' }}>
              <div style={{ padding: '1.5rem', background: 'var(--bg-secondary)', borderRadius: '1rem', border: '1px solid var(--border-secondary)', textAlign: 'center' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-tertiary)', letterSpacing: '0.05em', marginBottom: '0.375rem' }}>Auto-Resolution Rate</p>
                <div style={{ fontSize: '2.5rem', fontWeight: 900, color: !results ? 'var(--text-secondary)' : isTargetMet ? '#10b981' : '#ef4444', letterSpacing: '-0.03em' }}>
                  {results ? `${accuracy.toFixed(1)}%` : '-'}
                </div>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: isTargetMet ? '#10b981' : 'var(--text-tertiary)', display: 'inline-flex', alignItems: 'center', gap: '0.25rem', marginTop: '0.25rem' }}>
                  {results ? (isTargetMet ? '✔ Verified Benchmark Standard' : '⚠️ Below Target') : 'Ready to verify'}
                </span>
              </div>

              <div style={{ padding: '1.5rem', background: 'var(--bg-secondary)', borderRadius: '1rem', border: '1px solid var(--border-secondary)', textAlign: 'center' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-tertiary)', letterSpacing: '0.05em', marginBottom: '0.375rem' }}>Total Scenarios</p>
                <div style={{ fontSize: '2.5rem', fontWeight: 900, color: 'var(--text-primary)', letterSpacing: '-0.03em' }}>
                  {results ? summary.total : cases.length || '200'}
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Synthetic US Medical Cases</span>
              </div>

              <div style={{ padding: '1.5rem', background: 'var(--bg-secondary)', borderRadius: '1rem', border: '1px solid var(--border-secondary)', textAlign: 'center' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-tertiary)', letterSpacing: '0.05em', marginBottom: '0.375rem' }}>Passed Validation</p>
                <div style={{ fontSize: '2.5rem', fontWeight: 900, color: '#10b981', letterSpacing: '-0.03em' }}>
                  {results ? summary.passed : '-'}
                </div>
                <span style={{ fontSize: '0.75rem', color: '#10b981' }}>Ground-truth matched</span>
              </div>

              <div style={{ padding: '1.5rem', background: 'var(--bg-secondary)', borderRadius: '1rem', border: '1px solid var(--border-secondary)', textAlign: 'center' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-tertiary)', letterSpacing: '0.05em', marginBottom: '0.375rem' }}>Failed / Ambiguous</p>
                <div style={{ fontSize: '2.5rem', fontWeight: 900, color: results && summary.failed > 0 ? '#ef4444' : 'var(--text-tertiary)', letterSpacing: '-0.03em' }}>
                  {results ? summary.failed : '-'}
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Requires intervention</span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* ── Case Explorer Section ────────────────────────────────────── */}
        <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
          <div className="card" style={{ padding: '2rem', background: 'var(--bg-card)', border: '1px solid var(--border-secondary)' }}>
            <div style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-secondary)', paddingBottom: '1.5rem' }}>
              <div>
                <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)' }}>Interactive Case Explorer</h3>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Inspect individual scenarios, AI multi-agent recommendations, and ground-truth rationale</p>
              </div>

              {/* Filter controls */}
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ position: 'relative', minWidth: '200px' }}>
                  <input 
                    className="input" 
                    style={{ padding: '0.5rem 0.75rem 0.5rem 2.25rem', fontSize: '0.8125rem', width: '100%', borderRadius: '0.5rem' }} 
                    placeholder="Search by ID, title or keyword..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                  />
                  <span style={{ position: 'absolute', left: '0.625rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }}>
                    <IconSearch size={15} />
                  </span>
                </div>

                <select 
                  className="input" 
                  style={{ padding: '0.5rem 0.75rem', fontSize: '0.8125rem', borderRadius: '0.5rem', width: 'auto', background: 'var(--bg-card)' }}
                  value={selectedCategory}
                  onChange={e => setSelectedCategory(e.target.value)}
                >
                  {categoriesList.map(cat => <option key={cat.id} value={cat.id}>{cat.name}</option>)}
                </select>

                <select 
                  className="input" 
                  style={{ padding: '0.5rem 0.75rem', fontSize: '0.8125rem', borderRadius: '0.5rem', width: 'auto', background: 'var(--bg-card)' }}
                  value={selectedStatus}
                  onChange={e => setSelectedStatus(e.target.value)}
                >
                  <option value="all">All Statuses</option>
                  <option value="pass">Passed Only</option>
                  <option value="fail">Failed Only</option>
                </select>
              </div>
            </div>

            {/* Table or Empty State */}
            {loading ? (
              <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-tertiary)' }}>
                <span className="spinner" style={{ width: '32px', height: '32px', borderTopColor: 'var(--accent)', margin: '0 auto 1rem' }} />
                <p style={{ fontWeight: 600 }}>Loading synthetic benchmark library...</p>
              </div>
            ) : !results ? (
              <div style={{ textAlign: 'center', padding: '4rem', background: 'var(--bg-secondary)', borderRadius: '1rem', border: '1px dashed var(--border-secondary)' }}>
                <IconBarChart size={40} style={{ color: 'var(--text-tertiary)', margin: '0 auto 1rem' }} />
                <h4 style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>No Evaluated Reports in Memory</h4>
                <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', maxWidth: '420px', margin: '0 auto 1.5rem' }}>
                  We have loaded {cases.length} synthetic medical denial and upcoding scenarios. Click below to run the Quick Test or Full Suite to calculate live accuracy.
                </p>
                <button className="btn btn-red" onClick={() => handleStartRun('quick')}>
                  <IconZap size={16} /> Run 21-Case Quick Test Now
                </button>
              </div>
            ) : displayCases.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-tertiary)' }}>
                <p style={{ fontWeight: 600 }}>No benchmark cases match your selected filter criteria.</p>
                <button className="btn btn-ghost" style={{ marginTop: '0.75rem', fontSize: '0.8125rem' }} onClick={() => { setSelectedCategory('all'); setSelectedStatus('all'); setSearchQuery('') }}>
                  Reset Filters
                </button>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--border-secondary)', fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-tertiary)', letterSpacing: '0.05em' }}>
                      <th style={{ padding: '0.875rem 1rem' }}>Case ID</th>
                      <th style={{ padding: '0.875rem 1rem' }}>Category</th>
                      <th style={{ padding: '0.875rem 1rem' }}>Scenario Title</th>
                      <th style={{ padding: '0.875rem 1rem' }}>Expected vs Actual</th>
                      <th style={{ padding: '0.875rem 1rem', textAlign: 'center' }}>Result</th>
                      <th style={{ padding: '0.875rem 1rem', textAlign: 'right' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayCases.map((item) => {
                      const isExpanded = expandedCaseId === item.case_id
                      const catLabel = categoriesList.find(c => c.id === item.category)?.name || item.category.replace(/_/g, ' ')
                      const expRec = item.expected?.appeal_recommendation || '-'
                      const actRec = item.actual?.appeal_recommendation || item.actual?.error || '-'
                      
                      return (
                        <Fragment key={item.case_id}>
                          <tr
                            style={{ borderBottom: '1px solid var(--border-secondary)', cursor: 'pointer', background: isExpanded ? 'var(--bg-secondary)' : 'transparent', transition: 'background 0.15s' }}
                            onClick={() => setExpandedCaseId(isExpanded ? null : item.case_id)}
                            onMouseEnter={e => { if (!isExpanded) e.currentTarget.style.background = 'var(--bg-secondary)' }}
                            onMouseLeave={e => { if (!isExpanded) e.currentTarget.style.background = 'transparent' }}
                          >
                            <td style={{ padding: '1rem', fontWeight: 800, fontFamily: 'monospace', fontSize: '0.875rem', color: 'var(--text-primary)' }}>{item.case_id}</td>
                            <td style={{ padding: '1rem' }}>
                              <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.25rem 0.625rem', borderRadius: '999px', background: 'var(--bg-card)', border: '1px solid var(--border-secondary)', color: 'var(--text-secondary)' }}>
                                {catLabel}
                              </span>
                            </td>
                            <td style={{ padding: '1rem', fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)', maxWidth: '300px' }}>{item.title}</td>
                            <td style={{ padding: '1rem', fontSize: '0.8125rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                                <span style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>Exp:</span>
                                <strong style={{ color: 'var(--text-primary)' }}>{expRec}</strong>
                                <span style={{ color: 'var(--text-tertiary)' }}>→</span>
                                <strong style={{ color: item.status === 'pass' ? '#10b981' : '#ef4444' }}>{actRec}</strong>
                              </div>
                            </td>
                            <td style={{ padding: '1rem', textAlign: 'center' }}>
                              <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '0.25rem 0.75rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 800, background: item.status === 'pass' ? 'var(--success-bg)' : 'var(--danger-bg)', color: item.status === 'pass' ? '#10b981' : '#ef4444' }}>
                                {item.status === 'pass' ? <><IconCheckCircle size={14} style={{ marginRight: '0.25rem' }} /> PASS</> : <><IconAlertTriangle size={14} style={{ marginRight: '0.25rem' }} /> FAIL</>}
                              </span>
                            </td>
                            <td style={{ padding: '1rem', textAlign: 'right' }}>
                              <button className="btn btn-ghost" style={{ padding: '0.375rem', color: 'var(--text-tertiary)' }}>
                                {isExpanded ? <IconChevronUp size={18} /> : <IconChevronDown size={18} />}
                              </button>
                            </td>
                          </tr>

                          {/* Expanded detail drop-down row */}
                          {isExpanded && (
                            <tr style={{ background: 'var(--bg-secondary)', borderBottom: '2px solid var(--border-secondary)' }}>
                              <td colSpan={6} style={{ padding: '1.5rem 2rem' }}>
                                <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }}>
                                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
                                    
                                    {/* Ground Truth Rationale */}
                                    <div style={{ background: 'var(--bg-card)', padding: '1.25rem', borderRadius: '0.75rem', border: '1px solid var(--border-secondary)' }}>
                                      <h5 style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-tertiary)', letterSpacing: '0.05em', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                                        <IconShield size={14} /> Ground Truth Rationale (Verified Clinical Standard)
                                      </h5>
                                      <p style={{ fontSize: '0.875rem', color: 'var(--text-primary)', lineHeight: 1.6, fontWeight: 500 }}>
                                        {item.ground_truth_rationale || "No specific rationale text provided in case library."}
                                      </p>
                                      <div style={{ marginTop: '0.875rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-secondary)', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                                        <strong>Expected Route:</strong> {item.expected?.route_decision || 'N/A'} | <strong>Contradiction:</strong> {item.expected?.contradiction_detected ? 'Yes' : 'No'}
                                      </div>
                                    </div>

                                    {/* AI Agent Output & Diagnostics */}
                                    <div style={{ background: 'var(--bg-card)', padding: '1.25rem', borderRadius: '0.75rem', border: '1px solid var(--border-secondary)' }}>
                                      <h5 style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', color: item.status === 'pass' ? '#10b981' : '#ef4444', letterSpacing: '0.05em', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                                        <IconCpu size={14} /> Multi-Agent AI Execution Analysis
                                      </h5>
                                      <p style={{ fontSize: '0.875rem', color: 'var(--text-primary)', lineHeight: 1.6, fontWeight: 600, marginBottom: '0.5rem' }}>
                                        Verification Detail: <span style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>{item.reason}</span>
                                      </p>
                                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                                        <div><strong>Actual Recommendation:</strong> {item.actual?.appeal_recommendation || 'N/A'}</div>
                                        <div><strong>Triage Path:</strong> {item.actual?.triage_path || 'Standard Policy Analysis'}</div>
                                        <div><strong>Execution Duration:</strong> {item.duration_ms ? `${item.duration_ms} ms` : 'N/A'}</div>
                                      </div>
                                    </div>

                                  </div>
                                </motion.div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </motion.div>

      </div>
    </section>
  )
}
