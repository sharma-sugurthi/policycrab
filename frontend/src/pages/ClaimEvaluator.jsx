import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { apiFetch } from '../lib/api'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

export default function ClaimEvaluator({ policyProfile, onResult }) {
  const navigate = useNavigate()
  const [claimText, setClaimText] = useState('')
  const [allowedAmount, setAllowedAmount] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [providerSearch, setProviderSearch] = useState({ city: '', state: '', last_name: '', taxonomy_description: '', is_facility: false })
  const [providerResults, setProviderResults] = useState([])
  const [providerLoading, setProviderLoading] = useState(false)
  const [networkChecks, setNetworkChecks] = useState({})
  const [providerError, setProviderError] = useState(null)
  const [letterActionStatus, setLetterActionStatus] = useState('')

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

  const handleEvaluate = async () => {
    if (!policyProfile) { setError('Upload a policy first.'); return }
    if (claimText.trim().length < 20) { setError('Please describe the claim in more detail.'); return }
    setLoading(true); setError(null); setResult(null); setLetterActionStatus('')
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

              <button className="btn btn-red" onClick={handleEvaluate} disabled={loading || !policyProfile || claimText.trim().length < 20} style={{ width: '100%' }}>
                {loading ? <><span className="spinner" /> Evaluating Pipeline...</> : '⚡ Run Evaluation'}
              </button>

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
                        <button type="button" className="btn btn-red" onClick={handleDownloadAppealLetter}>Download .txt</button>
                      </div>
                    </div>
                    <div className="appeal-letter">{result.appeal_output.appeal_letter}</div>
                  </motion.div>
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
