import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

export default function ClaimEvaluator({ policyProfile, onResult }) {
  const navigate = useNavigate()
  const [claimText, setClaimText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleEvaluate = async () => {
    if (!policyProfile) { setError('Upload a policy first.'); return }
    if (claimText.trim().length < 20) { setError('Please describe the claim in more detail.'); return }
    setLoading(true); setError(null); setResult(null)
    try {
      const res = await fetch('/api/claim/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ claim_description: claimText, policy_profile: policyProfile }) })
      const data = await res.json()
      if (data.success && data.cost_breakdown) { setResult(data); onResult(data.cost_breakdown) }
      else { setError(data.errors?.join(', ') || 'Evaluation failed') }
    } catch (err) { setError(`Network error: ${err.message}`) }
    finally { setLoading(false) }
  }

  const loadSample = (type) => {
    if (type === 'approved') setClaimText("I went to my in-network doctor for a routine office visit because I had a bad cold. The bill was $250.")
    else if (type === 'nsa') setClaimText("I went to the ER at City Hospital because of severe chest pain. The hospital is out-of-network. They billed $15,000.")
    else setClaimText("I had an MRI on my right knee. My insurance denied it saying it wasn't medically necessary (Code CO-50). The facility billed $3,500. No prior authorization was done.")
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

                    <h4 style={{ fontSize: '0.8125rem', fontWeight: 700, marginBottom: '0.75rem', color: '#71717a', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Formal Appeal Letter</h4>
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
