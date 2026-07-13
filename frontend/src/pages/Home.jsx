import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }
const fadeRight = { hidden: { opacity: 0, x: -24 }, show: { opacity: 1, x: 0 } }

export default function Home({ policyProfile }) {
  const navigate = useNavigate()

  return (
    <>
      {/* ═══════════════ HERO ═══════════════ */}
      <section className="hero">
        <div className="hero-glow" />
        <div className="hero-grid" />

        <div className="main" style={{ position: 'relative', zIndex: 10 }}>
          <motion.div
            initial="hidden"
            animate="show"
            variants={{ show: { transition: { staggerChildren: 0.1 } } }}
            style={{ maxWidth: '56rem' }}
          >
            <motion.p variants={fadeUp} transition={{ duration: 0.5 }} className="section-label">
              <span className="line" /> AI-Powered Insurance Claims Engine
            </motion.p>

            <motion.h1
              variants={fadeUp}
              transition={{ duration: 0.65 }}
              style={{ fontSize: 'clamp(2.5rem, 6vw, 4.5rem)', fontWeight: 900, letterSpacing: '-0.05em', lineHeight: 0.92, marginBottom: '1.5rem' }}
            >
              Understand your
              <br />
              <span className="gradient-text">health insurance,</span>
              <br />
              fight denied claims.
            </motion.h1>

            <motion.p
              variants={fadeUp}
              transition={{ duration: 0.55, delay: 0.1 }}
              style={{ fontSize: '1.125rem', color: '#71717a', fontWeight: 500, lineHeight: 1.625, maxWidth: '36rem', marginBottom: '2.5rem' }}
            >
              Upload your policy. Describe your claim. Get deterministic cost breakdowns, regulatory routing, 
              and AI-drafted appeal letters — all grounded in ERISA, ACA, and the No Surprises Act.
            </motion.p>

            <motion.div variants={fadeUp} transition={{ duration: 0.55, delay: 0.18 }} style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <button className="btn btn-red" onClick={() => navigate('/policy')}>
                Upload Your Policy →
              </button>
              <button className="btn btn-outline" onClick={() => navigate('/chat')}>
                Talk to AI Assistant
              </button>
            </motion.div>

            <motion.p variants={fadeUp} transition={{ duration: 0.5, delay: 0.3 }} style={{ marginTop: '1.5rem', fontSize: '0.8125rem', color: '#a1a1aa', fontWeight: 500 }}>
              46 regulatory knowledge chunks · 5 AI agents · Deterministic cost engine
            </motion.p>
          </motion.div>
        </div>
      </section>

      {/* ═══════════════ STATS ═══════════════ */}
      <section className="section-zinc section-pad">
        <div className="main">
          <motion.div
            initial="hidden" whileInView="show" viewport={{ once: true }}
            variants={{ show: { transition: { staggerChildren: 0.05 } } }}
            style={{ textAlign: 'center', marginBottom: '3rem' }}
          >
            <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label" style={{ justifyContent: 'center' }}>
              By the Numbers
            </motion.p>
            <motion.h2 variants={fadeUp} transition={{ duration: 0.5 }} className="section-title" style={{ textAlign: 'center' }}>
              Trust the <span className="gradient-text">Engine</span>
            </motion.h2>
          </motion.div>

          <div className="grid-4">
            {[
              { value: '$1M+', label: 'Claims Evaluated', color: '#dc2626', bg: '#fef2f2' },
              { value: '10k+', label: 'Appeals Generated', color: '#09090b', bg: '#fafafa' },
              { value: '4.9/5', label: 'Average Rating', color: '#059669', bg: '#ecfdf5' },
              { value: '15+', label: 'Insurers Supported', color: '#dc2626', bg: '#fef2f2' },
            ].map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
                className="card stat-card"
                style={{ background: s.bg }}
              >
                <div className="stat-value" style={{ color: s.color }}>{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════ TESTIMONIALS ═══════════════ */}
      <section className="section-white section-pad" style={{ background: '#fff' }}>
        <div className="main">
          <motion.div
            initial="hidden" whileInView="show" viewport={{ once: true }}
            variants={{ show: { transition: { staggerChildren: 0.05 } } }}
            style={{ textAlign: 'center', marginBottom: '3rem' }}
          >
            <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label" style={{ justifyContent: 'center' }}>
              Patient Success
            </motion.p>
            <motion.h2 variants={fadeUp} transition={{ duration: 0.5 }} className="section-title" style={{ textAlign: 'center' }}>
              Don't take our word for it
            </motion.h2>
          </motion.div>

          <div className="grid-3">
            {[
              { name: "Sarah T.", claim: "Saved $3,400 on ER Bill", quote: "The engine proved my visit was covered under the No Surprises Act. The appeal letter was perfect." },
              { name: "Mark D.", claim: "Overturned MRI Denial", quote: "My insurer said it wasn't medically necessary. PolicyCrab cited the exact ACA clauses and won." },
              { name: "Elena R.", claim: "Corrected Co-insurance", quote: "I was billed 40% instead of 20%. Uploading my policy here showed me the exact math to fight it." }
            ].map((t, i) => (
              <motion.div
                key={t.name}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
                className="card"
                style={{ padding: '1.5rem', background: '#fafafa' }}
              >
                <p style={{ fontStyle: 'italic', color: '#3f3f46', marginBottom: '1rem', lineHeight: 1.6 }}>"{t.quote}"</p>
                <div>
                  <div style={{ fontWeight: 700, color: '#09090b' }}>{t.name}</div>
                  <div style={{ fontSize: '0.8125rem', color: '#dc2626', fontWeight: 600 }}>{t.claim}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════ HOW IT WORKS ═══════════════ */}
      <section className="section-white section-pad">
        <div className="main">
          <motion.div initial="hidden" whileInView="show" viewport={{ once: true }} variants={{ show: { transition: { staggerChildren: 0.06 } } }}>
            <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label">
              <span className="line" /> How It Works
            </motion.p>
            <motion.h2 variants={fadeUp} transition={{ duration: 0.5 }} className="section-title">
              Three steps to <span className="gradient-text">clarity</span>
            </motion.h2>
            <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-subtitle" style={{ marginBottom: '3rem' }}>
              From raw policy text to a formal appeal letter — with deterministic cost calculations and zero hallucinated numbers.
            </motion.p>
          </motion.div>

          <div className="grid-3">
            {[
              { step: '01', icon: '📋', title: 'Upload Your Policy', desc: 'Paste your SBC or EOB text. The AI Ingestion Agent extracts plan type, deductibles, coinsurance, copays, legal classification, and network rules into a structured profile.' },
              { step: '02', icon: '⚡', title: 'Evaluate Your Claim', desc: 'Describe your medical encounter in plain English. The deterministic engine calculates your exact responsibility through the deductible → coinsurance → OOP max waterfall.' },
              { step: '03', icon: '⚖️', title: 'Get Your Appeal', desc: 'If your claim is denied, the Grievance Agent drafts a formal appeal letter citing specific ERISA, ACA, or NSA regulations from our 46-chunk knowledge base.' },
            ].map((item, i) => (
              <motion.div
                key={item.step}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="card"
                style={{ padding: '2rem' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                  <div style={{ width: '3rem', height: '3rem', borderRadius: '1rem', background: '#fef2f2', border: '1px solid #fecaca', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.25rem' }}>
                    {item.icon}
                  </div>
                  <span style={{ fontSize: '0.6875rem', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace", color: '#dc2626', letterSpacing: '0.05em' }}>
                    STEP {item.step}
                  </span>
                </div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#09090b', letterSpacing: '-0.025em', marginBottom: '0.5rem' }}>
                  {item.title}
                </h3>
                <p style={{ fontSize: '0.875rem', color: '#71717a', fontWeight: 500, lineHeight: 1.625 }}>
                  {item.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════ COVERAGE FRAMEWORKS ═══════════════ */}
      <section className="section-zinc section-pad">
        <div className="main">
          <div className="grid-2" style={{ gap: '3rem', alignItems: 'start' }}>
            <motion.div initial="hidden" whileInView="show" viewport={{ once: true }} variants={{ show: { transition: { staggerChildren: 0.06 } } }}>
              <motion.p variants={fadeRight} transition={{ duration: 0.45 }} className="section-label">
                <span className="line" /> Regulatory Intelligence
              </motion.p>
              <motion.h2 variants={fadeRight} transition={{ duration: 0.5 }} className="section-title">
                Every US framework, <span className="gradient-text">covered.</span>
              </motion.h2>
              <motion.p variants={fadeRight} transition={{ duration: 0.45 }} className="section-subtitle" style={{ marginBottom: '2rem' }}>
                Our deterministic engine routes every claim to the correct appeal framework — no LLM guesswork on legal classifications or deadlines.
              </motion.p>

              <motion.div variants={fadeRight} transition={{ duration: 0.5, delay: 0.1 }}>
                {[
                  { icon: '🏛️', label: 'ERISA — Self-funded employer plans', cls: 'red' },
                  { icon: '🛡️', label: 'ACA — Marketplace & essential benefits', cls: 'emerald' },
                  { icon: '⚖️', label: 'No Surprises Act — Balance billing defense', cls: 'purple' },
                  { icon: '🏥', label: 'Medicare — 5-level appeal process', cls: 'amber' },
                  { icon: '🔒', label: 'HIPAA — Privacy & EDI compliance', cls: 'blue' },
                ].map((f) => (
                  <div key={f.label} className="feature-item">
                    <div className={`feature-icon ${f.cls}`}>{f.icon}</div>
                    <span>{f.label}</span>
                  </div>
                ))}
              </motion.div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 24 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.55, delay: 0.1 }}
              style={{ position: 'relative' }}
            >
              <div className="card" style={{ padding: '2rem' }}>
                <h3 style={{ fontWeight: 800, fontSize: '1.25rem', letterSpacing: '-0.025em', marginBottom: '1.5rem' }}>
                  {policyProfile ? '✅ Your Loaded Policy' : '📋 Policy Intelligence'}
                </h3>
                {policyProfile ? (
                  <div>
                    {[
                      ['Plan', policyProfile.plan_name],
                      ['Carrier', policyProfile.carrier_name],
                      ['Type', policyProfile.plan_type],
                      ['Classification', policyProfile.legal_classification],
                      ['Deductible', `$${policyProfile.in_network_deductible_individual?.toLocaleString()}`],
                      ['OOP Max', `$${policyProfile.in_network_oop_max_individual?.toLocaleString()}`],
                      ['Coinsurance', `${(policyProfile.in_network_coinsurance * 100).toFixed(0)}% you / ${((1 - policyProfile.in_network_coinsurance) * 100).toFixed(0)}% insurer`],
                    ].map(([l, v]) => (
                      <div className="result-row" key={l}>
                        <span className="result-label">{l}</span>
                        <span className="result-value">{v}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div>
                    <p style={{ color: '#71717a', fontSize: '0.875rem', marginBottom: '1.5rem', lineHeight: 1.625 }}>
                      Upload your Summary of Benefits and Coverage to see your plan details extracted here automatically.
                    </p>
                    <button className="btn btn-red" onClick={() => navigate('/policy')}>Upload Policy →</button>
                  </div>
                )}
              </div>
              <div style={{ position: 'absolute', bottom: '-1rem', right: '-1rem', width: '8rem', height: '8rem', background: '#fef2f2', borderRadius: '1.5rem', zIndex: -1, border: '1px solid #fecaca' }} />
            </motion.div>
          </div>
        </div>
      </section>

      {/* ═══════════════ CTA ═══════════════ */}
      <section className="section-dark section-pad" style={{ paddingTop: '5rem', paddingBottom: '5rem' }}>
        <div className="dark-glow" />
        <div className="main" style={{ textAlign: 'center', position: 'relative', zIndex: 10 }}>
          <motion.h2
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.65 }}
            style={{ fontSize: 'clamp(2rem, 5vw, 3.75rem)', fontWeight: 900, letterSpacing: '-0.05em', lineHeight: 1.05, marginBottom: '1.5rem', color: '#fff' }}
          >
            Ready to fight your <span className="gradient-text">denied claim?</span>
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.1 }}
            style={{ fontSize: '1.125rem', color: '#a1a1aa', fontWeight: 500, marginBottom: '2.5rem', maxWidth: '36rem', margin: '0 auto 2.5rem' }}
          >
            Stop overpaying. Upload your policy, run the cost engine, and get an appeal letter backed by federal regulations.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.18 }}
            style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}
          >
            <button className="btn btn-red" style={{ padding: '1rem 2.5rem', fontSize: '1rem' }} onClick={() => navigate('/claim')}>
              Evaluate a Claim →
            </button>
            <button
              className="btn btn-outline"
              style={{ borderColor: 'rgba(255,255,255,0.2)', color: '#fff', padding: '1rem 2.5rem', fontSize: '1rem' }}
              onClick={() => navigate('/chat')}
            >
              Ask AI Assistant
            </button>
          </motion.div>

          <motion.p
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.3 }}
            style={{ marginTop: '1.5rem', fontSize: '0.8125rem', color: '#52525b', fontWeight: 500 }}
          >
            Deterministic calculations · RAG-powered citations · Zero hallucinations
          </motion.p>
        </div>
      </section>

      {/* ═══════════════ FOOTER ═══════════════ */}
      <footer style={{ background: '#09090b', borderTop: '1px solid rgba(255,255,255,0.05)', padding: '2rem 0' }}>
        <div className="main" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <img src="/logo.png" alt="PolicyCrab" style={{ width: '20px', height: '20px', objectFit: 'contain', filter: 'brightness(0) invert(1)' }} />
            <span style={{ fontWeight: 800, fontSize: '1rem', color: '#fff', letterSpacing: '-0.02em' }}>PolicyCrab</span>
          </div>
          <p style={{ fontSize: '0.6875rem', color: '#52525b', fontWeight: 500, maxWidth: '36rem', lineHeight: 1.5, textAlign: 'right' }}>
            Not legal or medical advice. For informational purposes only. Always verify with your insurer and consult a licensed professional. Use at your own risk.
          </p>
        </div>
      </footer>
    </>
  )
}
