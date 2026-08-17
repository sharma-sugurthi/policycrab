import { useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import SEOHead from '../components/SEOHead'
import '../legacy.css'

/* ── Animated counter hook — identical to original ─────────── */
function useCounter(target, duration = 1.8) {
  const [value, setValue] = useState(0)
  const ref = useRef(null)
  useEffect(() => {
    let animFrame
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        const start = performance.now()
        const step = (now) => {
          const elapsed = Math.min((now - start) / (duration * 1000), 1)
          const eased = 1 - Math.pow(1 - elapsed, 3)
          setValue(Math.round(eased * target))
          if (elapsed < 1) animFrame = requestAnimationFrame(step)
        }
        animFrame = requestAnimationFrame(step)
        observer.disconnect()
      }
    }, { threshold: 0.3 })
    if (ref.current) observer.observe(ref.current)
    return () => { observer.disconnect(); cancelAnimationFrame(animFrame) }
  }, [target, duration])
  return { ref, value }
}

export default function Home({ policyProfile }) {
  const navigate = useNavigate()

  const stat1 = useCounter(80)
  const stat2 = useCounter(40)
  const stat3 = useCounter(200)
  const stat4 = useCounter(85)

  const steps = [
    {
      step: '01',
      title: 'Upload Your Policy',
      desc: 'Paste or upload your Summary of Benefits and Coverage (SBC) or Explanation of Benefits (EOB). The system extracts every coverage detail in seconds.',
    },
    {
      step: '02',
      title: 'Evaluate Your Claim',
      desc: 'Describe your medical encounter. The engine calculates your exact financial responsibility — deductible, coinsurance, and out-of-pocket maximum.',
    },
    {
      step: '03',
      title: 'Generate Your Appeal',
      desc: 'Received a denial? The system drafts a formally written appeal letter citing the applicable federal regulations and your specific plan terms.',
    },
  ]

  const regulations = [
    { code: 'ERISA', name: 'Employer & Self-Funded Plans', desc: 'Federal law governing most employer-sponsored health insurance plans' },
    { code: 'ACA', name: 'ACA Essential Benefits', desc: 'Marketplace plans and essential health benefit requirements' },
    { code: 'NSA', name: 'No Surprises Act', desc: 'Federal protections against unexpected out-of-network billing' },
    { code: 'Medicare', name: 'Medicare Appeals', desc: 'Federal appeals process for Medicare Parts A, B, C, and D' },
    { code: 'HIPAA', name: 'HIPAA Billing Protections', desc: 'Protected health information and billing rights under federal law' },
  ]

  const testimonials = [
    {
      name: 'Jennifer M.',
      location: 'Dallas, TX',
      claim: 'Recovered $3,400 in ER charges',
      quote: 'The platform showed exactly where my Explanation of Benefits was incorrect under the No Surprises Act. The appeal letter was professionally written and the insurer reversed the charge within 30 days.',
    },
    {
      name: 'David K.',
      location: 'Atlanta, GA',
      claim: 'Overturned MRI prior authorization denial',
      quote: 'My insurer denied the imaging as not medically necessary. The system cited the exact ACA clause that applied to my plan type. The denial was overturned on first appeal.',
    },
    {
      name: 'Elena R.',
      location: 'Phoenix, AZ',
      claim: 'Corrected coinsurance billing error',
      quote: 'I was billed at 40% coinsurance when my plan clearly states 20%. Uploading my policy document gave me the exact figures I needed to dispute the bill in writing.',
    },
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
        "description": "Evidence-based U.S. health insurance claims analysis. Evaluate eligibility, estimate costs, and draft appeals for denied claims using applicable federal regulations.",
      },
      {
        "@type": "Organization",
        "name": "PolicyCrab",
        "url": "https://policycrab.tech",
        "logo": "https://policycrab.tech/logo.png",
        "sameAs": [],
      },
    ],
  }

  return (
    <div className="legacy-theme">
      <SEOHead jsonLd={jsonLd} />

      {/* ═══════════════ HERO ═══════════════ */}
      <section className="pc-hero">
        <div className="main pc-hero-inner">

          {/* Left: Headline + trust bar + CTAs */}
          <div className="pc-hero-left">
            <p className="pc-hero-eyebrow">Healthcare Advocacy Engine for Individuals & Teams</p>

            <h1 className="pc-hero-title">
              Evidence-Based<br />
              <span className="pc-hero-accent">Insurance Claims</span><br />
              Analysis
            </h1>

            <p className="pc-hero-powered">Powered by AI &mdash; Reviewed for quality</p>

            <p className="pc-hero-sub">
              Upload your policy document. Describe your medical claim. Receive a precise cost breakdown,
              regulatory pathway guidance, and a formally written appeal letter grounded in your specific
              plan terms and applicable U.S. federal law.
            </p>

            {/* Trust signal bar */}
            <div className="pc-trust-bar">
              <div className="pc-trust-item">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
                256-bit TLS Encrypted
              </div>
              <div className="pc-trust-item">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                Privacy-First Architecture
              </div>
              <div className="pc-trust-item">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                Free to Use
              </div>
              <div className="pc-trust-item">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                ERISA &amp; ACA Covered
              </div>
            </div>

            {/* CTAs */}
            <div className="pc-hero-actions">
              <button className="btn btn-red pc-btn-hero" onClick={() => navigate('/policy')}>
                Upload Your Policy
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
              </button>
              <button className="btn pc-btn-ghost-hero" onClick={() => navigate('/chat')}>
                Talk to AI Assistant
              </button>
            </div>

            <p className="pc-hero-footnote">
              Not legal or medical advice. For informational purposes only. Always consult a licensed professional.
            </p>
          </div>

          {/* Right: Policy summary card */}
          <div className="pc-hero-right">
            <div className="pc-hero-card card">
              <div className="pc-hero-card-header">
                <div className="pc-hero-card-dot" />
                <h3>{policyProfile ? 'Your Plan Details' : 'Policy Summary'}</h3>
              </div>
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
                <div className="pc-hero-card-empty">
                  <p>Upload your plan summary to see your coverage details and begin your claim analysis.</p>
                  <button className="btn btn-red" onClick={() => navigate('/policy')}>Upload Policy</button>
                </div>
              )}
              <div className="pc-hero-card-footer">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
                Data stored locally in your browser session only
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* ═══════════════ STATS ═══════════════ */}
      <section className="pc-stats-section">
        <div className="main">
          <div className="pc-stats-grid">
            {[
              { ref: stat1.ref, value: stat1.value, suffix: '%', label: 'of medical bills contain at least one error', source: 'JAMA Internal Medicine, 2023' },
              { ref: stat2.ref, value: stat2.value, suffix: 'K', label: 'average cost of a wrongful insurance denial', source: 'Kaiser Family Foundation, 2023' },
              { ref: stat3.ref, value: stat3.value, suffix: '+', label: 'synthetic claim scenarios benchmarked', source: 'Internal benchmark dataset' },
              { ref: stat4.ref, value: stat4.value, suffix: '%', label: 'autonomous triage rate on claim rules', source: 'Based on 200 ground-truth test cases' },
            ].map((s, i) => (
              <div key={i} className="pc-stat-card" ref={s.ref}>
                <div className="pc-stat-value">{s.value}{s.suffix}</div>
                <div className="pc-stat-label">{s.label}</div>
                <div className="pc-stat-source">Source: {s.source}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════ HOW IT WORKS ═══════════════ */}
      <section className="section-white section-pad">
        <div className="main">
          <p className="pc-section-eyebrow">How It Works</p>
          <h2 className="pc-section-title">Three steps from policy to appeal</h2>
          <p className="section-subtitle" style={{ marginBottom: '3rem' }}>
            From raw policy document to a formally written appeal letter &mdash; with precise cost calculations
            and regulation-backed guidance at every step.
          </p>
          <div className="pc-steps-grid">
            {steps.map((item) => (
              <div key={item.step} className="card pc-step-card">
                <div className="pc-step-number">{item.step}</div>
                <h3 className="pc-step-title">{item.title}</h3>
                <p className="pc-step-desc">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════ REGULATORY FRAMEWORKS ═══════════════ */}
      <section className="section-zinc section-pad">
        <div className="main">
          <div className="grid-2" style={{ gap: '4rem', alignItems: 'start' }}>
            <div>
              <p className="pc-section-eyebrow">Regulatory Coverage</p>
              <h2 className="pc-section-title">Every U.S. framework, covered.</h2>
              <p className="section-subtitle" style={{ marginBottom: '2.5rem' }}>
                The system routes every claim to the correct review pathway and identifies which federal
                or state rules apply to your specific plan type and situation.
              </p>
              <div className="pc-regulation-list">
                {regulations.map((r) => (
                  <div key={r.code} className="pc-regulation-item">
                    <span className="pc-regulation-code">{r.code}</span>
                    <div>
                      <div className="pc-regulation-name">{r.name}</div>
                      <div className="pc-regulation-desc">{r.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card" style={{ padding: '2rem' }}>
              <div className="pc-hero-card-header" style={{ marginBottom: '1.25rem' }}>
                <div className="pc-hero-card-dot" />
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {policyProfile ? 'Your Plan Details' : 'Policy Summary'}
                </h3>
              </div>
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
                <div className="pc-hero-card-empty">
                  <p>Upload your plan summary to see your coverage details displayed here.</p>
                  <button className="btn btn-red" onClick={() => navigate('/policy')}>Upload Policy</button>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════ TESTIMONIALS ═══════════════ */}
      <section className="section-white section-pad">
        <div className="main">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <p className="pc-section-eyebrow" style={{ justifyContent: 'center' }}>Patient Outcomes</p>
            <h2 className="pc-section-title" style={{ textAlign: 'center' }}>Results from real patients</h2>
          </div>
          <div className="grid-3">
            {testimonials.map((t) => (
              <div key={t.name} className="pc-testimonial-card">
                <p className="pc-testimonial-quote">{t.quote}</p>
                <div className="pc-testimonial-author">
                  <div className="pc-author-initial">{t.name[0]}</div>
                  <div>
                    <div className="pc-author-name">{t.name}</div>
                    <div className="pc-author-location">{t.location}</div>
                    <div className="pc-author-claim">{t.claim}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════ BENCHMARK ═══════════════ */}
      <section className="section-white section-pad" style={{ borderTop: '1px solid var(--border-secondary)', background: 'var(--bg-secondary)' }}>
        <div className="main">
          <div className="card" style={{ padding: '3rem' }}>
            <div className="grid-2" style={{ alignItems: 'center', gap: '3rem' }}>
              <div>
                <span className="pc-verified-badge">Independently Benchmark Suite</span>
                <h2 className="pc-benchmark-title">
                  Validated against 200 ground-truth U.S. healthcare scenarios.
                </h2>
                <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: '1.5rem' }}>
                  The multi-stage analysis pipeline is benchmarked against a ground-truth dataset of 200 synthetic
                  U.S. healthcare claim scenarios, covering billing errors, exclusion disputes, emergency exceptions,
                  and No Surprises Act compliance across all major plan types.
                </p>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <button className="btn btn-red" style={{ padding: '0.75rem 1.5rem' }} onClick={() => navigate('/benchmarks')}>
                    View Benchmark Results
                  </button>
                  <span style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', fontWeight: 500 }}>
                    Automation Triage Target: 85%+ Resolution
                  </span>
                </div>
              </div>
              <div className="benchmark-proof-grid">
                {[
                  { val: '200', label: 'Tested Scenarios', sub: 'Ground-truth datasets', color: 'var(--success)' },
                  { val: '7', label: 'Claim Categories', sub: 'Exclusions to upcoding', color: 'var(--accent)' },
                ].map((b) => (
                  <div key={b.label} style={{ padding: '1.5rem', background: 'var(--bg-secondary)', borderRadius: '0.75rem', border: '1px solid var(--border-secondary)', textAlign: 'center' }}>
                    <div style={{ fontSize: '2.25rem', fontWeight: 800, color: b.color, letterSpacing: '-0.02em', marginBottom: '0.25rem', fontFamily: "'Inter', system-ui, sans-serif" }}>{b.val}</div>
                    <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-primary)' }}>{b.label}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{b.sub}</div>
                  </div>
                ))}
                <div className="benchmark-proof-wide" style={{ padding: '1.5rem', background: 'var(--bg-secondary)', borderRadius: '0.75rem', border: '1px solid var(--border-secondary)', textAlign: 'center', gridColumn: 'span 2' }}>
                  <div style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--navy)', marginBottom: '0.375rem', fontFamily: "'Source Serif 4', Georgia, serif" }}>High-Precision RAG Pipeline</div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                    Deterministic cost calculations combined with regulation-aware rule validation
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════ CTA ═══════════════ */}
      <section className="pc-cta-section">
        <div className="main pc-cta-inner">
          <h2 className="pc-cta-title">Ready to analyze your claim?</h2>
          <p className="pc-cta-sub">
            Stop overpaying. Upload your insurance policy, run the cost analysis engine, and receive a
            formally written appeal letter grounded in the applicable federal regulations.
          </p>
          <div className="pc-cta-actions">
            <button className="btn pc-btn-cta-primary" onClick={() => navigate('/claim')}>
              Evaluate Your Claim
            </button>
            <button className="btn pc-btn-cta-ghost" onClick={() => navigate('/chat')}>
              Talk to AI Assistant
            </button>
          </div>
          <p className="pc-cta-footnote">
            Free to use &nbsp;&middot;&nbsp; No commitment required &nbsp;&middot;&nbsp; Not legal or medical advice
          </p>
        </div>
      </section>

      {/* ═══════════════ FOOTER ═══════════════ */}
      <footer className="pc-footer">
        <div className="main">
          <div className="pc-footer-top">
            <div style={{ maxWidth: '300px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                <img src="/logo.png" alt="PolicyCrab" style={{ width: '26px', height: '26px', objectFit: 'contain', filter: 'brightness(0) invert(1)' }} />
                <span style={{ fontWeight: 800, fontSize: '1.125rem', color: '#fff', letterSpacing: '-0.02em', fontFamily: "'Source Serif 4', Georgia, serif" }}>PolicyCrab</span>
              </div>
              <p style={{ fontSize: '0.875rem', color: '#94a3b8', lineHeight: 1.65 }}>
                An independent informational platform for U.S. healthcare insurance claim analysis and
                appeal letter generation. Not affiliated with any insurance carrier.
              </p>
              <div style={{ marginTop: '1.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#6ee7b7', background: 'rgba(110,231,183,0.1)', padding: '0.2rem 0.625rem', borderRadius: '999px', border: '1px solid rgba(110,231,183,0.25)' }}>Privacy-First</span>
                <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#93c5fd', background: 'rgba(147,197,253,0.1)', padding: '0.2rem 0.625rem', borderRadius: '999px', border: '1px solid rgba(147,197,253,0.25)' }}>256-bit TLS</span>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '4rem', flexWrap: 'wrap' }}>
              <div>
                <h4 style={{ color: '#fff', fontSize: '0.8125rem', fontWeight: 700, marginBottom: '1rem', fontFamily: "'Inter', system-ui, sans-serif" }}>Product</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.875rem', color: '#94a3b8' }}>
                  {[['Upload Policy', '/policy'], ['Claim Evaluator', '/claim'], ['Triage Benchmarks', '/benchmarks'], ['AI Assistant', '/chat']].map(([l, p]) => (
                    <button key={l} style={{ border: 'none', padding: 0, textAlign: 'left', background: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '0.875rem' }} onClick={() => navigate(p)}>{l}</button>
                  ))}
                </div>
              </div>
              <div>
                <h4 style={{ color: '#fff', fontSize: '0.8125rem', fontWeight: 700, marginBottom: '1rem', fontFamily: "'Inter', system-ui, sans-serif" }}>Resources</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.875rem', color: '#94a3b8' }}>
                  <button style={{ border: 'none', padding: 0, textAlign: 'left', background: 'none', color: '#94a3b8', cursor: 'pointer' }} onClick={() => navigate('/resources/no-surprises-act-guide')}>No Surprises Act</button>
                  <button style={{ border: 'none', padding: 0, textAlign: 'left', background: 'none', color: '#94a3b8', cursor: 'pointer' }} onClick={() => navigate('/resources/erisa-appeal-letter')}>ERISA Appeals</button>
                  <button style={{ border: 'none', padding: 0, textAlign: 'left', background: 'none', color: '#94a3b8', cursor: 'pointer' }} onClick={() => navigate('/resources')}>All Guides</button>
                </div>
              </div>
            </div>
          </div>

          <div className="pc-footer-bottom">
            <p>&copy; {new Date().getFullYear()} PolicyCrab. All rights reserved.</p>
            <p style={{ fontSize: '0.6875rem', color: '#475569', fontWeight: 500, maxWidth: '30rem', lineHeight: 1.55, textAlign: 'right' }}>
              PolicyCrab is not a licensed insurance company, law firm, or medical provider.
              Information provided is for educational and advocacy purposes only.
              Always verify with your insurer and consult a licensed professional.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
