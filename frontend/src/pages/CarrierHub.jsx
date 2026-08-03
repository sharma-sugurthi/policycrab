import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  IconSearch, IconSend, IconClock, IconPhone, IconGlobe, 
  IconAlertTriangle, IconCheckCircle, IconMap, IconMail, IconCopy, IconDownload, IconPlus, IconX
} from '../components/Icons'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch, readApiResponse } from '../lib/api'

export default function CarrierHub() {
  const { session } = useAuth()
  
  // Carrier Routing States
  const [searchQuery, setSearchQuery] = useState('')
  const [carrierInfo, setCarrierInfo] = useState(null)
  const [routingPackage, setRoutingPackage] = useState(null)
  const [customAddress, setCustomAddress] = useState('')
  
  // Deadline States
  const [deadlines, setDeadlines] = useState([])
  const [showDeadlineForm, setShowDeadlineForm] = useState(false)
  const [form, setForm] = useState({
    carrier_name: '',
    appeal_level: 'Level 1: Internal Appeal',
    appeal_framework: 'STATE_DOI_COMPLAINT',
    state_code: 'XX',
    date_denial_received: new Date().toISOString().split('T')[0],
    statutory_days: 180,
    insurer_response_days: 30,
    claim_summary: ''
  })
  
  // Async states
  const [loadingSearch, setLoadingSearch] = useState(false)
  const [loadingRouting, setLoadingRouting] = useState(false)
  const [loadingDeadlines, setLoadingDeadlines] = useState(false)
  const [loadingBreach, setLoadingBreach] = useState(null) // ID of deadline
  const [error, setError] = useState(null)

  useEffect(() => {
    if (session) fetchDeadlines()
  }, [session])

  const fetchDeadlines = async () => {
    setLoadingDeadlines(true)
    try {
      const res = await apiFetch('/deadlines')
      if (res.ok) {
        const data = await readApiResponse(res)
        if (data?.success) setDeadlines(data.deadlines || [])
      }
    } catch (err) {
      console.error('Failed to fetch deadlines:', err)
    } finally {
      setLoadingDeadlines(false)
    }
  }

  const handleSearchCarrier = async (e) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    
    setLoadingSearch(true)
    setError(null)
    setCarrierInfo(null)
    setRoutingPackage(null)
    
    try {
      const res = await apiFetch(`/carrier/lookup?q=${encodeURIComponent(searchQuery)}`)
      if (res.ok) {
        const data = await readApiResponse(res)
        if (data?.success) {
          setCarrierInfo(data.carrier)
        } else {
          setError("Carrier not found in directory. Try a different name.")
        }
      } else {
        setError("Carrier not found in directory. Try a different name.")
      }
    } catch (err) {
      setError("Carrier not found in directory. Try a different name.")
    } finally {
      setLoadingSearch(false)
    }
  }

  const handleGetRouting = async () => {
    if (!carrierInfo) return
    setLoadingRouting(true)
    try {
      // Default to the user's state or XX if unknown
      const res = await apiFetch('/carrier/routing', {
        method: 'POST',
        body: JSON.stringify({
          carrier_name: carrierInfo.display_name,
          state: 'XX', // This could be pulled from user's policy if integrated
          framework: 'STATE_DOI_COMPLAINT' // Default fallback
        })
      })
      if (res.ok) {
        const data = await readApiResponse(res)
        if (data?.success) {
          setRoutingPackage(data)
        }
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoadingRouting(false)
    }
  }

  const handleSaveDeadline = async (e) => {
    e.preventDefault()
    
    // Calculate dates
    const denialDate = new Date(form.date_denial_received)
    const deadlineDate = new Date(denialDate)
    deadlineDate.setDate(denialDate.getDate() + parseInt(form.statutory_days))
    
    const payload = {
      ...form,
      deadline_date: deadlineDate.toISOString().split('T')[0]
    }
    
    try {
      const res = await apiFetch('/deadlines', {
        method: 'POST',
        body: JSON.stringify(payload)
      })
      if (res.ok) {
        const data = await readApiResponse(res)
        if (data?.success) {
          setShowDeadlineForm(false)
          fetchDeadlines()
        }
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const handleMarkFiled = async (id) => {
    const filedDate = new Date().toISOString().split('T')[0]
    // find deadline to get response days
    const d = deadlines.find(x => x.id === id)
    if (!d) return
    
    const responseDeadline = new Date()
    responseDeadline.setDate(responseDeadline.getDate() + (d.insurer_response_days || 30))
    
    try {
      await apiFetch(`/deadlines/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          status: 'filed',
          date_appeal_filed: filedDate,
          insurer_response_deadline: responseDeadline.toISOString().split('T')[0]
        })
      })
      fetchDeadlines()
    } catch (err) {
      console.error(err)
    }
  }

  const handleMarkResponded = async (id) => {
    try {
      await apiFetch(`/deadlines/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'response_received' })
      })
      fetchDeadlines()
    } catch (err) {
      console.error(err)
    }
  }

  const handleDeleteDeadline = async (id) => {
    if (!window.confirm("Delete this deadline?")) return
    try {
      await apiFetch(`/deadlines/${id}`, { method: 'DELETE' })
      fetchDeadlines()
    } catch (err) {
      console.error(err)
    }
  }

  const handleGenerateBreachLetter = async (id) => {
    setLoadingBreach(id)
    try {
      const res = await apiFetch(`/deadlines/${id}/breach-letter`, {
        method: 'POST'
      })
      if (res.ok) {
        const data = await readApiResponse(res)
        if (data?.success) {
          // Save the generated letter in notes or download it
          const blob = new Blob([data.letter], { type: 'text/plain' })
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `DOI_Complaint_${id.substring(0,8)}.txt`
          a.click()
          URL.revokeObjectURL(url)
        }
      }
    } catch (err) {
      alert("Failed to generate breach letter: " + err.message)
    } finally {
      setLoadingBreach(null)
    }
  }

  const checkBreach = (deadline) => {
    if (deadline.status !== 'filed' || !deadline.insurer_response_deadline) return false
    const today = new Date()
    const target = new Date(deadline.insurer_response_deadline)
    return today > target
  }

  const finalAddress = customAddress || carrierInfo?.appeal_mailing_address

  return (
    <section className="section-white section-pad">
      <div className="main">
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }} style={{ marginBottom: '2rem' }}>
          <motion.p variants={{ hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }} transition={{ duration: 0.45 }} className="section-label">
            <span className="line" /> Routing Workspace
          </motion.p>
          <motion.h1 variants={{ hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }} transition={{ duration: 0.55 }} className="section-title">
            Carrier <span className="gradient-text">Routing Hub</span>
          </motion.h1>
          <motion.p variants={{ hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }} transition={{ duration: 0.45 }} className="section-subtitle">
            Find submission addresses, track statutory deadlines, and enforce your rights.
          </motion.p>
        </motion.div>

        {error && (
          <div style={{ marginBottom: '2rem', padding: '1rem', background: 'var(--danger-bg)', color: 'var(--danger)', borderRadius: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <IconAlertTriangle size={18} /> {error}
          </div>
        )}

        <div className="grid-2" style={{ gap: '2rem', alignItems: 'start' }}>
        
        {/* ── Section 1: Carrier Lookup & Routing ── */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="card" style={{ padding: '2rem', background: 'var(--bg-card)', border: '1px solid var(--border-secondary)' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
              <IconSearch size={20} /> Smart Carrier Lookup
            </h3>
            
            <form onSubmit={handleSearchCarrier} style={{ display: 'flex', gap: '0.5rem' }}>
              <input 
                type="text" 
                className="input" 
                placeholder="e.g. UnitedHealthcare, Aetna..." 
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{ flex: 1 }}
              />
              <button type="submit" className="btn btn-red" style={{ padding: '0.75rem 1.5rem', fontSize: '0.9rem' }} disabled={loadingSearch}>
                {loadingSearch ? 'Searching...' : 'Search'}
              </button>
            </form>

            {carrierInfo && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} style={{ marginTop: '2rem' }}>
                <h4 style={{ fontWeight: 800, fontSize: '1.5rem', color: 'var(--accent)', marginBottom: '1rem' }}>
                  {carrierInfo.display_name}
                </h4>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ background: 'var(--bg-secondary)', padding: '1rem', borderRadius: '0.75rem', border: '1px solid var(--border-secondary)' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Default Mailing Address</label>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginTop: '0.5rem' }}>
                      <pre style={{ margin: 0, fontFamily: 'inherit', fontSize: '0.875rem', color: 'var(--text-primary)', lineHeight: 1.6 }}>
                        {carrierInfo.appeal_mailing_address}
                      </pre>
                      <button className="btn btn-outline" style={{ padding: '0.25rem 0.5rem' }} onClick={() => navigator.clipboard.writeText(carrierInfo.appeal_mailing_address)}>
                        <IconCopy size={14} />
                      </button>
                    </div>
                  </div>

                  <div className="grid-2" style={{ gap: '1rem' }}>
                    <div style={{ background: 'var(--bg-secondary)', padding: '1rem', borderRadius: '0.75rem', border: '1px solid var(--border-secondary)' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}><IconPhone size={14} style={{display:'inline', verticalAlign:'middle'}}/> Fax</span>
                      <strong style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>{carrierInfo.appeal_fax_number || 'Not available'}</strong>
                    </div>
                    <div style={{ background: 'var(--bg-secondary)', padding: '1rem', borderRadius: '0.75rem', border: '1px solid var(--border-secondary)' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}><IconGlobe size={14} style={{display:'inline', verticalAlign:'middle'}}/> Portal</span>
                      <a href={carrierInfo.appeal_portal_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.875rem', color: 'var(--accent)', textDecoration: 'none', fontWeight: 600 }}>Open Portal ↗</a>
                    </div>
                  </div>

                  {carrierInfo.special_notes && (
                    <div style={{ background: 'var(--accent-subtle)', border: '1px solid var(--accent-border)', padding: '1rem', borderRadius: '0.75rem', fontSize: '0.875rem', color: 'var(--text-primary)', lineHeight: 1.6 }}>
                      <strong>Note: </strong>{carrierInfo.special_notes}
                    </div>
                  )}

                  {!routingPackage && (
                    <button className="btn btn-red" style={{ marginTop: '1rem', width: '100%' }} onClick={handleGetRouting} disabled={loadingRouting}>
                      {loadingRouting ? 'Generating Routing Package...' : 'Get Full Routing Package'}
                    </button>
                  )}
                </div>
              </motion.div>
            )}
          </div>

          {routingPackage && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="card" style={{ padding: '2rem', border: '1px solid var(--accent-border)', boxShadow: 'var(--shadow-card)', background: 'var(--bg-card)' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
                <IconSend size={20} /> Submission Routing
              </h3>
              
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem', display: 'block' }}>Custom Address Override (Optional)</label>
                <textarea 
                  className="input" 
                  value={customAddress} 
                  onChange={e => setCustomAddress(e.target.value)}
                  placeholder={carrierInfo.appeal_mailing_address}
                  style={{ width: '100%', minHeight: '80px', fontFamily: 'monospace', fontSize: '0.875rem' }}
                />
              </div>

              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <button 
                  className="btn btn-red"
                  onClick={() => {
                    const subject = encodeURIComponent("Member Appeal Submission")
                    const body = encodeURIComponent(`Please find attached my appeal letter.\n\nCarrier: ${carrierInfo.display_name}`)
                    window.location.href = `mailto:${carrierInfo.appeal_email || ''}?subject=${subject}&body=${body}`
                  }}
                >
                  <IconMail size={16} /> Open in My Email
                </button>
                <button 
                  className="btn btn-outline"
                  onClick={() => {
                    const blob = new Blob([finalAddress], { type: 'text/plain' })
                    const a = document.createElement('a')
                    a.href = URL.createObjectURL(blob)
                    a.download = 'Mailing_Label.txt'
                    a.click()
                  }}
                >
                  <IconDownload size={16} /> Download Label
                </button>
              </div>
              
              <div style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-secondary)' }}>
                <h4 style={{ fontSize: '1rem', fontWeight: 800, marginBottom: '0.75rem', color: 'var(--text-primary)' }}>State Context ({routingPackage.state_context.state_name})</h4>
                <ul style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingLeft: '1.25rem', lineHeight: 1.6 }}>
                  <li><strong>External Review Org:</strong> {routingPackage.state_context.external_review_org}</li>
                  <li><strong>Deadline:</strong> {routingPackage.state_context.external_review_deadline_days} days</li>
                  {routingPackage.state_context.erisa_preempted && (
                    <li style={{ color: 'var(--danger)', fontWeight: 600 }}>ERISA Preempted: State law does not apply.</li>
                  )}
                </ul>
              </div>
            </motion.div>
          )}
        </section>

        {/* ── Section 2: Deadline Tracker ── */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-primary)' }}>
              <IconClock size={24} /> Deadline Tracker
            </h2>
            <button className="btn btn-red" style={{ padding: '0.625rem 1.25rem', fontSize: '0.875rem' }} onClick={() => setShowDeadlineForm(true)}>
              <IconPlus size={16} /> Add
            </button>
          </div>

          <AnimatePresence>
            {showDeadlineForm && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} style={{ overflow: 'hidden' }}>
                <div className="card" style={{ padding: '1.5rem', background: 'var(--bg-card)', border: '1px solid var(--border-secondary)', marginBottom: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <h3 style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--text-primary)' }}>New Deadline</h3>
                    <button className="btn btn-outline" style={{ padding: '0.25rem', border: 'none' }} onClick={() => setShowDeadlineForm(false)}>
                      <IconX size={20} />
                    </button>
                  </div>
                  <form onSubmit={handleSaveDeadline} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div className="grid-2" style={{ gap: '1rem' }}>
                      <div>
                        <label className="label">Carrier Name</label>
                        <input className="input" required value={form.carrier_name} onChange={e => setForm({...form, carrier_name: e.target.value})} />
                      </div>
                      <div>
                        <label className="label">Denial Date</label>
                        <input type="date" className="input" required value={form.date_denial_received} onChange={e => setForm({...form, date_denial_received: e.target.value})} />
                      </div>
                    </div>
                    <div className="grid-2" style={{ gap: '1rem' }}>
                      <div>
                        <label className="label">Statutory Filing Days</label>
                        <input type="number" className="input" required value={form.statutory_days} onChange={e => setForm({...form, statutory_days: e.target.value})} />
                      </div>
                      <div>
                        <label className="label">Insurer Response Days</label>
                        <input type="number" className="input" required value={form.insurer_response_days} onChange={e => setForm({...form, insurer_response_days: e.target.value})} />
                      </div>
                    </div>
                    <div>
                      <label className="label">Claim Summary (Optional)</label>
                      <input className="input" value={form.claim_summary} onChange={e => setForm({...form, claim_summary: e.target.value})} placeholder="e.g., ER Visit on Jan 1" />
                    </div>
                    <button type="submit" className="btn btn-red" style={{ alignSelf: 'flex-start' }}>Save Deadline</button>
                  </form>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {loadingDeadlines ? (
            <div style={{ textAlign: 'center', padding: '2rem' }}><div className="spinner" /></div>
          ) : deadlines.length === 0 ? (
            <div className="card" style={{ padding: '3rem 2rem', textAlign: 'center', color: 'var(--text-tertiary)', background: 'var(--bg-card)' }}>
              <IconClock size={48} style={{ opacity: 0.5, marginBottom: '1rem' }} />
              <p>No active deadlines.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {deadlines.map(d => {
                const isBreached = checkBreach(d)
                return (
                  <div key={d.id} className="card" style={{ padding: '1.25rem', borderLeft: isBreached ? '4px solid var(--danger)' : d.status === 'filed' ? '4px solid var(--warning)' : d.status === 'response_received' ? '4px solid var(--success)' : '4px solid var(--accent)', background: 'var(--bg-card)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <h4 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)' }}>{d.carrier_name}</h4>
                        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{d.appeal_level} • {d.claim_summary}</p>
                      </div>
                      <span className={`badge badge-${isBreached ? 'danger' : d.status === 'filed' ? 'warning' : d.status === 'response_received' ? 'success' : 'info'}`}>
                        {isBreached ? 'BREACHED' : d.status.replace('_', ' ').toUpperCase()}
                      </span>
                    </div>

                    <div className="grid-2" style={{ gap: '1rem', marginTop: '1rem', background: 'var(--bg-secondary)', padding: '1rem', borderRadius: '0.5rem' }}>
                      <div>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontWeight: 700, textTransform: 'uppercase' }}>Filing Deadline</span>
                        <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{d.deadline_date}</div>
                      </div>
                      <div>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', fontWeight: 700, textTransform: 'uppercase' }}>Insurer Response Due</span>
                        <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{d.insurer_response_deadline || 'Not filed yet'}</div>
                      </div>
                    </div>

                    <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {d.status === 'pending' && (
                        <button className="btn btn-outline" style={{ padding: '0.375rem 0.75rem', fontSize: '0.8125rem' }} onClick={() => handleMarkFiled(d.id)}>
                          Mark as Filed
                        </button>
                      )}
                      {d.status === 'filed' && (
                        <button className="btn btn-outline" style={{ padding: '0.375rem 0.75rem', fontSize: '0.8125rem' }} onClick={() => handleMarkResponded(d.id)}>
                          Mark Response Received
                        </button>
                      )}
                      <button className="btn" style={{ padding: '0.375rem 0.75rem', fontSize: '0.8125rem', color: 'var(--danger)', background: 'transparent' }} onClick={() => handleDeleteDeadline(d.id)}>
                        Delete
                      </button>
                    </div>

                    {isBreached && (
                      <div style={{ marginTop: '1rem', padding: '1rem', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--danger)', fontWeight: 700, marginBottom: '0.5rem' }}>
                          <IconAlertTriangle size={18} /> Statutory Deadline Breached
                        </div>
                        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                          The insurer is legally overdue. Generate a formal complaint to your state's Department of Insurance.
                        </p>
                        <button 
                          className="btn btn-red" 
                          onClick={() => handleGenerateBreachLetter(d.id)}
                          disabled={loadingBreach === d.id}
                        >
                          {loadingBreach === d.id ? 'Drafting...' : 'Generate DOI Complaint Letter'}
                        </button>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </section>
      </div>
      </div>
    </section>
  )
}
