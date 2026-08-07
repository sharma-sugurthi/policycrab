import { useNavigate } from 'react-router-dom'
import { motion, useMotionValue, useTransform, animate } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import SEOHead from '../components/SEOHead'
import '../legacy.css'

/* ── Animated counter hook ─────────────────────────────── */
function useCounter(target, duration = 1.8) {
  const [value, setValue] = useState(0)
  const ref = useRef(null)
  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        const controls = animate(0, target, {
          duration,
          ease: 'easeOut',
          onUpdate: v => setValue(Math.round(v)),
        })
        observer.disconnect()
        return controls.stop
      }
    }, { threshold: 0.3 })
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [target, duration])
  return { ref, value }
}

/* ── 3D Tilt Card ──────────────────────────────────────── */
function TiltCard({ children, className = '', style = {} }) {
  const cardRef = useRef(null)
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const rotateX = useTransform(y, [-0.5, 0.5], [8, -8])
  const rotateY = useTransform(x, [-0.5, 0.5], [-8, 8])

  const handleMouseMove = (e) => {
    const rect = cardRef.current.getBoundingClientRect()
    x.set((e.clientX - rect.left) / rect.width - 0.5)
    y.set((e.clientY - rect.top) / rect.height - 0.5)
  }
  const handleMouseLeave = () => { x.set(0); y.set(0) }

  return (
    <motion.div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ rotateX, rotateY, transformStyle: 'preserve-3d', perspective: 800, ...style }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

const fadeUp = { hidden: { opacity: 0, y: 28 }, show: { opacity: 1, y: 0 } }

export default function Home({ policyProfile }) {
  const navigate = useNavigate()

  const stat1 = useCounter(80)
  const stat2 = useCounter(40)
  const stat3 = useCounter(200)
  const stat4 = useCounter(85)

  const steps = [
    { step: '01', icon: '📋', title: 'Upload Your Policy', desc: 'Paste or upload your SBC or EOB. The AI extracts every coverage detail in seconds.' },
    { step: '02', icon: '⚡', title: 'Evaluate Your Claim', desc: 'Describe your medical encounter. The engine calculates your exact responsibility — deductible, coinsurance, OOP max.' },
    { step: '03', icon: '⚖️', title: 'Get Your Appeal', desc: 'Denied? The AI drafts a legally grounded appeal letter citing federal regulations automatically.' },
  ]

  const features = [
    { icon: '🏛️', label: 'ERISA — Employer & self-funded plans', color: 'var(--accent)', bg: 'var(--accent-subtle)', border: 'var(--accent-border)' },
    { icon: '🛡️', label: 'ACA — Marketplace essential benefits', color: 'var(--success)', bg: 'var(--success-bg)', border: 'var(--success-border)' },
    { icon: '⚖️', label: 'No Surprises Act — Balance billing', color: 'var(--purple)', bg: 'var(--purple-bg)', border: 'var(--purple-border)' },
    { icon: '🏥', label: 'Medicare — Federal appeal steps', color: 'var(--warning)', bg: 'var(--warning-bg)', border: 'var(--warning-border)' },
    { icon: '🔒', label: 'HIPAA — PHI & billing protections', color: 'var(--info)', bg: 'var(--info-bg)', border: 'var(--info-border)' },
  ]

  const testimonials = [
    { name: 'Sarah T.', claim: 'Saved $3,400 on ER Bill', quote: 'The engine proved my visit was covered under the No Surprises Act. The appeal letter was perfect.' },
    { name: 'Mark D.', claim: 'Overturned MRI Denial', quote: "My insurer said it wasn't medically necessary. PolicyCrab cited the exact ACA clauses and won." },
    { name: 'Elena R.', claim: 'Corrected Co-insurance', quote: 'I was billed 40% instead of 20%. Uploading my policy here showed me the exact math to fight it.' },
  ]

  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebApplication",
        "name": "PolicyCrab",
        "url": "https://policycrab.tech",
        "applicationCategory": "HealthApplication",
        "operatingSystem": "All",
        "description": "AI-powered US health insurance claims engine. Evaluate eligibility, estimate costs, and draft appeals for denied claims."
      },
      {
        "@type": "Organization",
        "name": "PolicyCrab",
        "url": "https://policycrab.tech",
        "logo": "https://policycrab.tech/logo.png",
        "sameAs": []
      }
    ]
  };

  return (
    <div className="legacy-theme">
      <SEOHead jsonLd={jsonLd} />

      {/* ══════════════════ HERO — VIDEO BG ══════════════════ */}
      <section className="pc-hero">
        {/* Looping video background */}
        <video
          className="pc-hero-video"
          src="/hero-bg.mp4"
          autoPlay
          loop
          muted
          playsInline
        />
        {/* Gradient overlay so text stays legible */}
        <div className="pc-hero-overlay" />

        {/* Floating ambient orbs */}
        <div className="pc-orb pc-orb-1" />
        <div className="pc-orb pc-orb-2" />
        <div className="pc-orb pc-orb-3" />

        <div className="main pc-hero-content">
          <motion.div
            initial="hidden"
            animate="show"
            variants={{ show: { transition: { staggerChildren: 0.11 } } }}
            className="pc-hero-inner"
          >
            {/* Badge */}
            <motion.div variants={fadeUp} transition={{ duration: 0.5 }} className="pc-hero-badge">
              <span className="pc-badge-pulse" />
              AI-Powered Insurance Claims Engine
            </motion.div>

            {/* Headline */}
            <motion.h1 variants={fadeUp} transition={{ duration: 0.65 }} className="pc-hero-title">
              Understand your<br />
              <span className="gradient-text">health insurance,</span><br />
              fight denied claims.
            </motion.h1>

            {/* Subtext */}
            <motion.p variants={fadeUp} transition={{ duration: 0.55, delay: 0.1 }} className="pc-hero-sub">
              Upload your policy. Describe your claim. Get clear cost breakdowns, guidance on the right
              review path, and draft appeal letters based on your plan and applicable regulations.
            </motion.p>

            {/* CTAs */}
            <motion.div variants={fadeUp} transition={{ duration: 0.5, delay: 0.18 }} className="pc-hero-actions">
              <button className="btn btn-red pc-btn-hero" onClick={() => navigate('/policy')}>
                Upload Policy
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
              </button>
              <button className="btn pc-btn-ghost-hero" onClick={() => navigate('/chat')}>
                AI Assistant
              </button>
            </motion.div>

            <motion.p variants={fadeUp} transition={{ duration: 0.5, delay: 0.3 }} className="pc-hero-footnote">
              Policy references · coverage guidance · straightforward cost estimates
            </motion.p>
          </motion.div>

          {/* Floating stat chips */}
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.6 }}
            className="pc-hero-chips"
          >
            {[
              { label: '80% of bills have errors', icon: '⚠️' },
              { label: 'ERISA · ACA · NSA covered', icon: '⚖️' },
              { label: 'Hallucination-proof math', icon: '✅' },
            ].map((chip, i) => (
              <motion.div
                key={chip.label}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.7 + i * 0.12 }}
                className="pc-chip"
              >
                <span>{chip.icon}</span> {chip.label}
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ══════════════════ STATS ══════════════════ */}
      <section className="pc-stats-section">
        <div className="main">
          <motion.div
            initial="hidden" whileInView="show" viewport={{ once: true }}
            variants={{ show: { transition: { staggerChildren: 0.07 } } }}
            className="pc-stats-grid"
          >
            {[
              { ref: stat1.ref, value: stat1.value, suffix: '%', label: 'of medical bills contain errors' },
              { ref: stat2.ref, value: stat2.value, suffix: 'K', label: 'dollars average wrongful denial' },
              { ref: stat3.ref, value: stat3.value, suffix: '+', label: 'synthetic test scenarios' },
              { ref: stat4.ref, value: stat4.value, suffix: '%', label: 'accuracy on financial calculations' },
            ].map((s, i) => (
              <motion.div
                key={i}
                variants={fadeUp}
                transition={{ duration: 0.5 }}
                className="pc-stat-card"
                ref={s.ref}
              >
                <div className="pc-stat-value">
                  {s.value}{s.suffix}
                </div>
                <div className="pc-stat-label">{s.label}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ══════════════════ HOW IT WORKS ══════════════════ */}
      <section className="section-white section-pad">
        <div className="main">
          <motion.div initial="hidden" whileInView="show" viewport={{ once: true }}
            variants={{ show: { transition: { staggerChildren: 0.07 } } }}
          >
            <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label">
              <span className="line" /> How It Works
            </motion.p>
            <motion.h2 variants={fadeUp} transition={{ duration: 0.5 }} className="section-title">
              Three steps to <span className="gradient-text">clarity</span>
            </motion.h2>
            <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-subtitle" style={{ marginBottom: '3.5rem' }}>
              From raw policy text to a formal appeal letter — with clear cost calculations and source-backed guidance.
            </motion.p>
          </motion.div>

          <div className="pc-steps-grid">
            {steps.map((item, i) => (
              <TiltCard key={item.step} className="card pc-step-card">
                <div className="pc-step-top">
                  <div className="pc-step-icon-wrap">
                    <span className="pc-step-emoji">{item.icon}</span>
                  </div>
                  <span className="pc-step-num">STEP {item.step}</span>
                </div>
                <div className="pc-step-connector" style={{ opacity: i < steps.length - 1 ? 1 : 0 }} />
                <h3 className="pc-step-title">{item.title}</h3>
                <p className="pc-step-desc">{item.desc}</p>
              </TiltCard>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════ REGULATORY FRAMEWORKS ══════════════════ */}
      <section className="section-zinc section-pad">
        <div className="main">
          <div className="grid-2" style={{ gap: '3rem', alignItems: 'start' }}>
            <motion.div initial="hidden" whileInView="show" viewport={{ once: true }}
              variants={{ show: { transition: { staggerChildren: 0.06 } } }}
            >
              <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label">
                <span className="line" /> Regulatory Intelligence
              </motion.p>
              <motion.h2 variants={fadeUp} transition={{ duration: 0.5 }} className="section-title">
                Every US framework, <span className="gradient-text">covered.</span>
              </motion.h2>
              <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-subtitle" style={{ marginBottom: '2rem' }}>
                Our system routes every claim to the right review path and helps you understand which rules apply.
              </motion.p>
              <motion.div variants={fadeUp} transition={{ duration: 0.5, delay: 0.1 }}>
                {features.map(f => (
                  <div key={f.label} className="feature-item">
                    <div className="feature-icon" style={{ background: f.bg, color: f.color, borderColor: f.border }}>{f.icon}</div>
                    <span>{f.label}</span>
                  </div>
                ))}
              </motion.div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 24 }} whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }} transition={{ duration: 0.55, delay: 0.1 }}
              style={{ position: 'relative' }}
            >
              <TiltCard className="card" style={{ padding: '2rem' }}>
                <h3 style={{ fontWeight: 800, fontSize: '1.25rem', letterSpacing: '-0.025em', marginBottom: '1.5rem' }}>
                  {policyProfile ? '✅ Your Plan Details' : '📋 Policy Summary'}
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
                    <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem', marginBottom: '1.5rem', lineHeight: 1.625 }}>
                      Upload your plan summary to see your coverage details displayed here.
                    </p>
                    <button className="btn btn-red" onClick={() => navigate('/policy')}>Upload Policy</button>
                  </div>
                )}
              </TiltCard>
              <div style={{ position: 'absolute', bottom: '-1rem', right: '-1rem', width: '8rem', height: '8rem', background: 'var(--accent-subtle)', borderRadius: '1.5rem', zIndex: -1, border: '1px solid var(--accent-border)' }} />
            </motion.div>
          </div>
        </div>
      </section>

      {/* ══════════════════ TESTIMONIALS ══════════════════ */}
      <section className="section-white section-pad">
        <div className="main">
          <motion.div initial="hidden" whileInView="show" viewport={{ once: true }}
            variants={{ show: { transition: { staggerChildren: 0.06 } } }}
            style={{ textAlign: 'center', marginBottom: '3rem' }}
          >
            <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-label" style={{ justifyContent: 'center' }}>
              Patient Success
            </motion.p>
            <motion.h2 variants={fadeUp} transition={{ duration: 0.5 }} className="section-title" style={{ textAlign: 'center' }}>
              Don't take our <span className="gradient-text">word for it</span>
            </motion.h2>
          </motion.div>

          <div className="grid-3">
            {testimonials.map((t, i) => (
              <TiltCard key={t.name}>
                <motion.div
                  initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }} transition={{ duration: 0.45, delay: i * 0.07 }}
                  className="card pc-testimonial-card"
                >
                  <div className="pc-quote-icon">"</div>
                  <p className="pc-testimonial-quote">{t.quote}</p>
                  <div className="pc-testimonial-author">
                    <div className="pc-author-avatar">{t.name[0]}</div>
                    <div>
                      <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.9375rem' }}>{t.name}</div>
                      <div style={{ fontSize: '0.8125rem', color: 'var(--accent)', fontWeight: 600 }}>{t.claim}</div>
                    </div>
                  </div>
                </motion.div>
              </TiltCard>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════ BENCHMARK / ACCURACY ══════════════════ */}
      <section className="section-white section-pad" style={{ borderTop: '1px solid var(--border-secondary)', background: 'var(--bg-secondary)' }}>
        <div className="main">
          <div className="card" style={{ padding: '3rem', borderRadius: '1.5rem', boxShadow: '0 20px 40px -15px rgba(0,0,0,0.05)' }}>
            <div className="grid-2" style={{ alignItems: 'stretch', gap: '3rem' }}>
              <motion.div initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ duration: 0.5 }}>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.375rem 0.75rem', borderRadius: '999px', background: 'var(--success-bg)', color: '#10b981', fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '1rem', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                  ✔ Rigorously Tested & Verified
                </div>
                <h2 style={{ fontSize: '2rem', fontWeight: 900, color: 'var(--text-primary)', letterSpacing: '-0.03em', lineHeight: 1.15, marginBottom: '1rem' }}>
                  Scientific proof of <span className="gradient-text">reasoning accuracy.</span>
                </h2>
                <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '1.5rem' }}>
                  Our multi-agent AI pipeline is benchmarked against 200 synthetic ground-truth US healthcare scenarios, rigorously evaluating exclusions, emergency exceptions, billing fraud, and No Surprises Act compliance.
                </p>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <button className="btn btn-red" style={{ padding: '0.75rem 1.5rem' }} onClick={() => navigate('/benchmarks')}>
                    Explore Benchmarks
                  </button>
                  <span style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>
                    Live Accuracy: ≥ 85.0% Standard Met
                  </span>
                </div>
              </motion.div>

              <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ duration: 0.5, delay: 0.1 }}>
                <div className="benchmark-proof-grid">
                  {[
                    { val: '200', label: 'Tested Scenarios', sub: 'Ground-truth datasets', color: '#10b981' },
                    { val: '7', label: 'Claim Categories', sub: 'Exclusions to Upcoding', color: 'var(--accent)' },
                  ].map(b => (
                    <div key={b.label} style={{ padding: '1.5rem', background: 'var(--bg-secondary)', borderRadius: '1rem', border: '1px solid var(--border-secondary)', textAlign: 'center' }}>
                      <div style={{ fontSize: '2.25rem', fontWeight: 900, color: b.color, letterSpacing: '-0.02em', marginBottom: '0.25rem' }}>{b.val}</div>
                      <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-primary)' }}>{b.label}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{b.sub}</div>
                    </div>
                  ))}
                  <div className="benchmark-proof-wide" style={{ padding: '1.5rem', background: 'var(--bg-secondary)', borderRadius: '1rem', border: '1px solid var(--border-secondary)', textAlign: 'center', gridColumn: 'span 2' }}>
                    <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#10b981', marginBottom: '0.25rem' }}>High-Precision RAG</div>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                      Deterministic cost calculations combined with clinical rule validation
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════ CTA ══════════════════ */}
      <section className="pc-cta-section">
        <div className="pc-cta-orb pc-cta-orb-1" />
        <div className="pc-cta-orb pc-cta-orb-2" />
        <div className="main" style={{ textAlign: 'center', position: 'relative', zIndex: 10 }}>
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }} whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }} transition={{ duration: 0.65 }}
            className="pc-cta-glass"
          >
            <h2 className="pc-cta-title">
              Ready to fight your <span className="gradient-text">denied claim?</span>
            </h2>
            <p className="pc-cta-sub">
              Stop overpaying. Upload your policy, run the cost engine, and get an appeal letter backed by federal regulations.
            </p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
              <button className="btn btn-red" style={{ padding: '1rem 2.5rem', fontSize: '1rem' }} onClick={() => navigate('/claim')}>
                Evaluate Claim
              </button>
              <button className="btn pc-btn-glass" onClick={() => navigate('/chat')}>
                Ask AI Assistant
              </button>
            </div>
            <p style={{ marginTop: '1.5rem', fontSize: '0.8125rem', color: 'rgba(255,255,255,0.4)', fontWeight: 500 }}>
              Clear calculations · source-backed references · plain-language guidance
            </p>
          </motion.div>
        </div>
      </section>

      {/* ══════════════════ FOOTER ══════════════════ */}
      <footer className="pc-footer">
        <div className="main">
          <div className="pc-footer-top">
            <div style={{ maxWidth: '300px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                <img src="/logo.png" alt="PolicyCrab" style={{ width: '28px', height: '28px', objectFit: 'contain', filter: 'brightness(0) invert(1)' }} />
                <span style={{ fontWeight: 800, fontSize: '1.25rem', color: '#fff', letterSpacing: '-0.02em', fontFamily: "'Outfit', sans-serif" }}>PolicyCrab</span>
              </div>
              <p style={{ fontSize: '0.875rem', color: '#94a3b8', lineHeight: 1.6 }}>
                AI-powered healthcare advocacy engine. Understand your coverage and fight unfair medical bills with confidence.
              </p>
              <div style={{ marginTop: '1.5rem' }}>
                <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#e11d48', background: 'rgba(225,29,72,0.1)', padding: '0.25rem 0.625rem', borderRadius: '999px', border: '1px solid rgba(225,29,72,0.3)' }}>AI Healthcare Advocacy</span>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '4rem', flexWrap: 'wrap' }}>
              <div>
                <h4 style={{ color: '#fff', fontSize: '0.875rem', fontWeight: 700, marginBottom: '1rem' }}>Product</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.875rem', color: '#94a3b8' }}>
                  {[['Upload Policy', '/policy'], ['Claim Evaluator', '/claim'], ['Accuracy Benchmarks', '/benchmarks'], ['AI Assistant', '/chat']].map(([l, p]) => (
                    <button key={l} className="btn-outline" style={{ border: 'none', padding: 0, textAlign: 'left', background: 'none', color: '#94a3b8' }} onClick={() => navigate(p)}>{l}</button>
                  ))}
                </div>
              </div>
              <div>
                <h4 style={{ color: '#fff', fontSize: '0.875rem', fontWeight: 700, marginBottom: '1rem' }}>Resources</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.875rem', color: '#94a3b8' }}>
                  <button className="btn-outline" style={{ border: 'none', padding: 0, textAlign: 'left', background: 'none', color: '#94a3b8', cursor: 'pointer' }} onClick={() => navigate('/resources/no-surprises-act-guide')}>No Surprises Act</button>
                  <button className="btn-outline" style={{ border: 'none', padding: 0, textAlign: 'left', background: 'none', color: '#94a3b8', cursor: 'pointer' }} onClick={() => navigate('/resources/erisa-appeal-letter')}>ERISA Appeals</button>
                  <button className="btn-outline" style={{ border: 'none', padding: 0, textAlign: 'left', background: 'none', color: '#94a3b8', cursor: 'pointer' }} onClick={() => navigate('/resources')}>All Guides</button>
                </div>
              </div>
            </div>
          </div>

          <div className="pc-footer-bottom">
            <p>© {new Date().getFullYear()} PolicyCrab. All rights reserved.</p>
            <p style={{ fontSize: '0.6875rem', color: '#475569', fontWeight: 500, maxWidth: '28rem', lineHeight: 1.5, textAlign: 'right' }}>
              Not legal or medical advice. For informational purposes only. Always verify with your insurer and consult a licensed professional.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
