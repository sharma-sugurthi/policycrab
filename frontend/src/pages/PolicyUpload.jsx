import { useState } from 'react'
import { motion } from 'framer-motion'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

export default function PolicyUpload({ onPolicyParsed }) {
  const [policyText, setPolicyText] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleUpload = async () => {
    if (!selectedFile && policyText.trim().length < 50) { 
      setError('Please upload a PDF or paste at least 50 characters of policy text.')
      return 
    }
    
    setLoading(true); setError(null); setResult(null)
    
    try {
      let res;
      if (selectedFile) {
        const formData = new FormData()
        formData.append('file', selectedFile)
        res = await fetch('/api/policy/upload-pdf', { 
          method: 'POST', 
          body: formData 
        })
      } else {
        res = await fetch('/api/policy/upload', { 
          method: 'POST', 
          headers: { 'Content-Type': 'application/json' }, 
          body: JSON.stringify({ policy_text: policyText }) 
        })
      }
      
      const data = await res.json()
      if (data.success && data.policy_profile) { 
        setResult(data)
        onPolicyParsed(data.policy_profile)
        if (data.extracted_text) setPolicyText(data.extracted_text)
      }
      else { setError(data.errors?.join(', ') || 'Failed to parse policy') }
    } catch (err) { setError(`Network error: ${err.message}`) }
    finally { setLoading(false) }
  }

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
            Upload your Summary of Benefits and Coverage (SBC) PDF or paste the text. The AI Ingestion Agent will extract all plan details automatically.
          </motion.p>
        </motion.div>

        <div className="grid-2" style={{ alignItems: 'start' }}>
          {/* ── Input ─────────────────── */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
            <div className="card" style={{ padding: '2rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                <div className="feature-icon red">📋</div>
                <div>
                  <h3 style={{ fontWeight: 700, fontSize: '1rem', color: '#09090b' }}>Policy Document</h3>
                  <p style={{ fontSize: '0.8125rem', color: '#a1a1aa' }}>Upload a PDF or paste your SBC/EOB text</p>
                </div>
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

          {/* ── Results ────────────────── */}
          <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.55, delay: 0.3 }} style={{ position: 'relative' }}>
            {result ? (
              <>
                <div className="results-panel" style={{ marginBottom: '1.5rem' }}>
                  <div className="results-header">
                    <h3 style={{ fontWeight: 700, fontSize: '1rem' }}>Extracted Policy Profile</h3>
                    <span className="badge badge-success">✅ Parsed</span>
                  </div>
                  <div className="results-body">
                    {[
                      ['Plan Name', result.policy_profile.plan_name],
                      ['Carrier', result.policy_profile.carrier_name],
                      ['Plan Type', result.policy_profile.plan_type],
                      ['Classification', result.policy_profile.legal_classification],
                      ['State', result.policy_profile.state],
                      ['Deductible', `$${result.policy_profile.in_network_deductible_individual?.toLocaleString()}`],
                      ['OOP Max', `$${result.policy_profile.in_network_oop_max_individual?.toLocaleString()}`],
                      ['Coinsurance', `${(result.policy_profile.in_network_coinsurance * 100).toFixed(0)}%`],
                      ['PCP Referral', result.policy_profile.requires_pcp_referral ? 'Yes' : 'No'],
                      ['HSA Eligible', result.policy_profile.is_hsa_eligible ? 'Yes' : 'No'],
                    ].map(([l, v]) => (
                      <div className="result-row" key={l}>
                        <span className="result-label">{l}</span>
                        <span className="result-value">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {result.explanation && (
                  <div className="explanation-box">
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
            {!result && <div style={{ position: 'absolute', bottom: '-1rem', right: '-1rem', width: '6rem', height: '6rem', background: '#fef2f2', borderRadius: '1.5rem', zIndex: -1, border: '1px solid #fecaca' }} />}
          </motion.div>
        </div>
      </div>
    </section>
  )
}
