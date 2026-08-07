import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import SEOHead from '../components/SEOHead'

const ARTICLES = [
  {
    slug: "erisa-appeal-letter",
    icon: "🏛️",
    badge: "ERISA",
    badgeColor: "#3b82f6",
    title: "How to Write an ERISA Internal Appeal Letter",
    subtitle: "A step-by-step guide to filing a formal appeal for employer-sponsored plan denials.",
    readTime: "8 min read",
    sections: [
      {
        heading: "What is ERISA and who does it apply to?",
        body: `ERISA (Employee Retirement Income Security Act of 1974) governs employer-sponsored and self-funded health plans in the United States. If your health coverage comes through your employer, there's a high probability your plan is subject to ERISA. ERISA plans are not required to follow state insurance laws, which makes the federal appeals process uniquely important.

Key identifiers that your plan is ERISA-governed: your insurance card lists your employer's name as the plan sponsor, or your Summary Plan Description (SPD) references "ERISA" and the Department of Labor.`,
      },
      {
        heading: "The ERISA Appeals Timeline",
        body: `You must act within specific deadlines or lose your rights permanently:

• **Initial denial:** You have 180 days from the date of the denial to file a Level 1 internal appeal.
• **Plan response:** The plan has 60 days (non-urgent) or 72 hours (urgent/concurrent care) to respond.
• **Exhaustion doctrine:** You MUST exhaust all internal appeal levels before filing a lawsuit in federal court under ERISA § 502(a)(1)(B).`,
      },
      {
        heading: "What your appeal letter must include",
        body: `A legally effective ERISA appeal letter must contain:

1. **Patient identification:** Full name, member ID, date of birth, group plan number.
2. **Claim reference:** Date of service, CPT procedure code, ICD-10 diagnosis code, billed amount.
3. **Denial reference:** The specific denial reason and CARC code from your EOB.
4. **Medical necessity argument:** Cite peer-reviewed clinical guidelines (e.g., MCG, InterQual) that support the necessity of the procedure.
5. **Regulatory citation:** Reference ERISA § 503 (claims and appeals) and DOL Regulation 29 C.F.R. § 2560.503-1.
6. **Relief requested:** State clearly that you request full payment of the claim.
7. **Response deadline:** Request a written decision within 60 days.`,
      },
      {
        heading: "Frequently Asked Questions",
        faq: true,
        items: [
          { q: "Can I sue my health insurer under ERISA?", a: "Yes, but only after exhausting all internal appeals. Under ERISA § 502(a)(1)(B), you can sue to recover benefits owed under the plan terms." },
          { q: "Do I need a lawyer to file an ERISA appeal?", a: "No. You have the right to file an appeal yourself. PolicyCrab's AI can generate a legally grounded appeal letter automatically." },
          { q: "What if my ERISA appeal is denied?", a: "After final internal denial, you can request External Independent Review (if available) or file a federal lawsuit. You can also file a complaint with the Department of Labor's Employee Benefits Security Administration (EBSA)." },
        ]
      }
    ]
  },
  {
    slug: "no-surprises-act-guide",
    icon: "⚡",
    badge: "No Surprises Act",
    badgeColor: "#10b981",
    title: "No Surprises Act: Your Complete Rights Guide",
    subtitle: "How to fight unexpected out-of-network bills from hospitals and emergency providers.",
    readTime: "6 min read",
    sections: [
      {
        heading: "What the No Surprises Act protects you from",
        body: `Effective January 1, 2022, the No Surprises Act (NSA) prohibits surprise medical bills in three key situations:

1. **Emergency care:** You receive emergency services at any facility, in-network or out-of-network. You can only be charged your in-network cost-sharing amount.
2. **Ancillary providers at in-network facilities:** An out-of-network surgeon, anesthesiologist, or radiologist provides services at an in-network hospital without your knowledge or consent.
3. **Air ambulance services:** Out-of-network air ambulance providers cannot bill you beyond your in-network cost-sharing.

The NSA does NOT apply to ground ambulance services, which remains a gap in federal law as of 2024.`,
      },
      {
        heading: "How to identify a No Surprises Act violation",
        body: `A potential NSA violation exists when:

• Your EOB shows an out-of-network provider at an in-network facility for a procedure you didn't specifically choose.
• You received emergency services and are being billed at out-of-network rates.
• You were not given a valid "Good Faith Estimate" (GFE) for a scheduled procedure at least 1 business day in advance.
• You received an air ambulance bill that significantly exceeds your in-network out-of-pocket maximum.`,
      },
      {
        heading: "Filing an NSA complaint",
        body: `To report a No Surprises Act violation:

1. Gather your EOB, the medical bill, and any communications from the provider.
2. File a complaint at **cms.gov/nosurprises** or call 1-800-MEDICARE.
3. You can also submit to your State Insurance Commissioner if your state has adopted additional NSA protections.
4. Request an Independent Dispute Resolution (IDR) through the federal portal if the provider disputes your claim.`,
      },
      {
        heading: "Frequently Asked Questions",
        faq: true,
        items: [
          { q: "Does the No Surprises Act apply to self-pay patients?", a: "Yes. Self-pay patients have the right to a Good Faith Estimate before any scheduled service. If the final bill exceeds the estimate by more than $400, you can initiate a Patient-Provider Dispute Resolution process." },
          { q: "What is an Independent Dispute Resolution (IDR) process?", a: "If your insurer and the provider disagree on payment under the NSA, they must go through a certified federal IDR entity to settle the dispute. You are not responsible for payments during this process." },
          { q: "Can out-of-network providers still balance bill me?", a: "Only if you voluntarily chose an out-of-network provider and signed a valid consent form acknowledging the additional costs at least 72 hours before service. Emergency care always qualifies for NSA protections regardless of consent." },
        ]
      }
    ]
  },
  {
    slug: "state-doi-complaint",
    icon: "📋",
    badge: "State DOI",
    badgeColor: "#a855f7",
    title: "How to File a State DOI Insurance Complaint",
    subtitle: "A step-by-step guide to escalating your denied claim to your State Department of Insurance.",
    readTime: "5 min read",
    sections: [
      {
        heading: "When to escalate to the State DOI",
        body: `File a State Department of Insurance (DOI) complaint when:

• Your insurer has denied your internal Level 1 appeal.
• The insurer failed to respond within the legally required timeframe.
• You believe the insurer is engaging in bad-faith claims handling (e.g., misrepresenting policy terms, unreasonable delays).
• Your plan is NOT governed by ERISA (i.e., individual market, small-group, or state-regulated plans).

Note: ERISA self-funded plans are not subject to state insurance regulation, so DOI complaints may not be effective for employer-sponsored plans. Check your SPD.`,
      },
      {
        heading: "What your DOI complaint should include",
        body: `A complete DOI complaint file includes:

1. Your insurance policy/member ID and the insurer's full legal name.
2. A clear chronological timeline: date of service → claim submission → denial → internal appeal → final denial.
3. Copies of: the EOB, denial letters, your appeal letter, and the insurer's final denial response.
4. A statement of the specific law or regulation you believe the insurer violated (e.g., state prompt payment law, unfair claims settlement practices act).
5. The specific monetary relief you are requesting.`,
      },
      {
        heading: "State-specific filing portals",
        body: `Most states have online complaint portals. Key resources:

• **California:** cdtfa.ca.gov/consumer
• **Texas:** tdi.texas.gov/pubs/consumer/cb020.html
• **New York:** dfs.ny.gov/consumers
• **Florida:** myfloridacfo.com/division/consumers
• **All other states:** Navigate to your state's DOI website and search "file a complaint."

PolicyCrab's Smart Email Routing feature automatically identifies your state's DOI contact based on your carrier and state of residence.`,
      },
      {
        heading: "Frequently Asked Questions",
        faq: true,
        items: [
          { q: "How long does a DOI investigation take?", a: "Most state DOIs aim to resolve complaints within 30-60 days. Complex cases involving bad-faith allegations can take up to 6 months." },
          { q: "Does filing a DOI complaint guarantee I'll get paid?", a: "No, but it creates a formal regulatory record. Insurers are highly motivated to resolve complaints before a DOI investigation escalates to a market conduct examination, which can result in significant fines." },
          { q: "Can I file a DOI complaint and still sue the insurer?", a: "Yes. Filing a DOI complaint does not waive your right to legal action. In fact, the DOI's investigation findings can serve as evidence in a subsequent lawsuit." },
        ]
      }
    ]
  },
  {
    slug: "medicare-appeal-process",
    icon: "🏥",
    badge: "Medicare",
    badgeColor: "#f59e0b",
    title: "Medicare Claim Appeal Process: All 5 Levels",
    subtitle: "A complete guide to challenging Medicare Part A and Part B claim denials through the federal appeals hierarchy.",
    readTime: "7 min read",
    sections: [
      {
        heading: "Overview: The Medicare 5-Level Appeal System",
        body: `Medicare has a formal 5-level appeal hierarchy for denied claims under Part A (hospital) and Part B (medical/outpatient):

1. **Redetermination** by the Medicare Administrative Contractor (MAC)
2. **Reconsideration** by a Qualified Independent Contractor (QIC)
3. **Hearing** before an Administrative Law Judge (ALJ)
4. **Review** by the Medicare Appeals Council (MAC Council)
5. **Federal District Court** judicial review (only if ≥ $1,990 in dispute)

You must complete each level in order before moving to the next.`,
      },
      {
        heading: "Level 1: Redetermination (MAC)",
        body: `**Filing deadline:** 120 days from the date of the initial denial notice.
**Response time:** MAC must decide within 60 days.

File Form CMS-20027 (Part A) or CMS-20011 (Part B), or write a letter to the Medicare Administrative Contractor on your Remittance Advice. Include: the claim number, service dates, and a clear explanation of why the denial is incorrect. Attach any supporting medical records.`,
      },
      {
        heading: "Level 2: Reconsideration (QIC)",
        body: `**Filing deadline:** 180 days from the MAC's Redetermination decision.
**Response time:** QIC must decide within 60 days (non-urgent) or 72 hours (expedited).

If the MAC upholds the denial, escalate to a Qualified Independent Contractor. The QIC is an independent body — they are not affiliated with your insurer. Include any new medical evidence not submitted at Level 1.`,
      },
      {
        heading: "Frequently Asked Questions",
        faq: true,
        items: [
          { q: "What is the minimum dollar amount to request an ALJ hearing?", a: "As of 2024, you need at least $180 in contested amounts to request a Level 3 ALJ hearing. For Federal Court review, the threshold is $1,990." },
          { q: "How long does the entire Medicare appeal process take?", a: "The 5-level process can take 12-24 months in total. Expedited reviews for urgent/ongoing care must be completed within 72 hours at Levels 1 and 2." },
          { q: "Can I get help filing a Medicare appeal?", a: "Yes. Your State Health Insurance Assistance Program (SHIP) provides free counseling. PolicyCrab can also generate your Level 1 and Level 2 appeal letters automatically based on your denial details." },
        ]
      }
    ]
  },
]

const FAQS_FOR_SCHEMA = ARTICLES.flatMap(a =>
  a.sections
    .filter(s => s.faq)
    .flatMap(s => s.items.map(item => ({ "@type": "Question", "name": item.q, "acceptedAnswer": { "@type": "Answer", "text": item.a } })))
)

const PAGE_JSON_LD = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "FAQPage",
      "mainEntity": FAQS_FOR_SCHEMA,
    },
    {
      "@type": "Article",
      "headline": "US Health Insurance Appeal Guide — ERISA, No Surprises Act, Medicare, State DOI",
      "description": "Complete guides for fighting denied health insurance claims under ERISA, the No Surprises Act, Medicare, and State DOI complaint processes.",
      "author": { "@type": "Organization", "name": "PolicyCrab" },
      "publisher": { "@type": "Organization", "name": "PolicyCrab", "url": "https://policycrab.tech" },
    }
  ]
}

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

function ArticleCard({ article, onClick }) {
  return (
    <motion.div
      variants={fadeUp}
      transition={{ duration: 0.45 }}
      onClick={() => onClick(article.slug)}
      style={{
        background: 'var(--surface, #18181b)',
        border: '1px solid var(--border, #27272a)',
        borderRadius: '16px',
        padding: '2rem',
        cursor: 'pointer',
        transition: 'transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease',
      }}
      onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.boxShadow = '0 12px 40px rgba(0,0,0,0.3)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'; }}
      onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.borderColor = 'var(--border, #27272a)'; }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '1rem' }}>
        <span style={{ fontSize: '1.75rem' }}>{article.icon}</span>
        <span style={{
          padding: '3px 12px', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 700,
          letterSpacing: '0.08em', textTransform: 'uppercase',
          background: article.badgeColor + '20', color: article.badgeColor,
          border: `1px solid ${article.badgeColor}40`,
        }}>{article.badge}</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#71717a' }}>{article.readTime}</span>
      </div>
      <h3 style={{ fontSize: '1.125rem', fontWeight: 700, color: '#f4f4f5', marginBottom: '0.5rem', lineHeight: 1.3 }}>
        {article.title}
      </h3>
      <p style={{ fontSize: '0.875rem', color: '#a1a1aa', lineHeight: 1.6, marginBottom: '1.25rem' }}>
        {article.subtitle}
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: article.badgeColor, fontSize: '0.875rem', fontWeight: 600 }}>
        Read Guide
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
      </div>
    </motion.div>
  )
}

function ArticleView({ article, onBack }) {
  const [openFaq, setOpenFaq] = useState(null)

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <button
        onClick={onBack}
        style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'none', border: 'none', color: '#a1a1aa', cursor: 'pointer', fontSize: '0.875rem', marginBottom: '2rem', padding: 0 }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
        Back to Resources
      </button>

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '1rem' }}>
        <span style={{ fontSize: '2rem' }}>{article.icon}</span>
        <span style={{
          padding: '3px 14px', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          background: article.badgeColor + '20', color: article.badgeColor, border: `1px solid ${article.badgeColor}40`,
        }}>{article.badge}</span>
      </div>

      <h1 style={{ fontSize: '2.25rem', fontWeight: 800, color: '#f4f4f5', lineHeight: 1.2, marginBottom: '0.75rem' }}>
        {article.title}
      </h1>
      <p style={{ fontSize: '1.125rem', color: '#a1a1aa', marginBottom: '2.5rem', lineHeight: 1.6 }}>
        {article.subtitle}
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '2.5rem' }}>
        {article.sections.map((section, si) =>
          section.faq ? (
            <div key={si}>
              <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f4f4f5', marginBottom: '1rem' }}>
                Frequently Asked Questions
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {section.items.map((item, ii) => (
                  <div key={ii}
                    style={{ background: '#27272a', borderRadius: '12px', overflow: 'hidden', border: '1px solid #3f3f46' }}
                  >
                    <button
                      onClick={() => setOpenFaq(openFaq === `${si}-${ii}` ? null : `${si}-${ii}`)}
                      style={{ width: '100%', padding: '1rem 1.25rem', background: 'none', border: 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', gap: '1rem' }}
                    >
                      <span style={{ fontWeight: 600, color: '#f4f4f5', fontSize: '0.9375rem', textAlign: 'left' }}>{item.q}</span>
                      <span style={{ color: '#71717a', fontSize: '1.25rem', flexShrink: 0, transition: 'transform 0.2s', transform: openFaq === `${si}-${ii}` ? 'rotate(45deg)' : 'none' }}>+</span>
                    </button>
                    <AnimatePresence>
                      {openFaq === `${si}-${ii}` && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                          style={{ overflow: 'hidden' }}
                        >
                          <p style={{ padding: '0 1.25rem 1rem', color: '#a1a1aa', fontSize: '0.9rem', lineHeight: 1.65 }}>{item.a}</p>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div key={si}>
              <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f4f4f5', marginBottom: '0.75rem' }}>
                {section.heading}
              </h2>
              <div style={{ background: '#18181b', border: '1px solid #27272a', borderRadius: '12px', padding: '1.5rem' }}>
                {section.body.split('\n\n').map((para, pi) => (
                  <p key={pi} style={{ color: '#a1a1aa', lineHeight: 1.75, fontSize: '0.9375rem', marginBottom: pi < section.body.split('\n\n').length - 1 ? '1rem' : 0 }}
                    dangerouslySetInnerHTML={{ __html: para.replace(/\*\*(.*?)\*\*/g, '<strong style="color:#f4f4f5">$1</strong>').replace(/\n/g, '<br/>') }}
                  />
                ))}
              </div>
            </div>
          )
        )}
      </div>
    </motion.div>
  )
}

export default function ResourcesHub() {
  const navigate = useNavigate()
  const [activeSlug, setActiveSlug] = useState(null)

  const activeArticle = ARTICLES.find(a => a.slug === activeSlug)

  const pageTitle = activeArticle
    ? `${activeArticle.title} | PolicyCrab Resources`
    : "Insurance Appeal Resources & Guides | PolicyCrab"
  const pageDesc = activeArticle
    ? activeArticle.subtitle
    : "Free guides on ERISA appeals, the No Surprises Act, State DOI complaints, and Medicare claim appeals. Learn how to fight denied health insurance claims."

  return (
    <div style={{ minHeight: '100vh', background: '#09090b', color: '#f4f4f5', fontFamily: "'Outfit', 'Inter', sans-serif" }}>
      <SEOHead
        title={pageTitle}
        description={pageDesc}
        canonicalUrl={`https://policycrab.tech/resources${activeSlug ? '/' + activeSlug : ''}`}
        ogType="article"
        jsonLd={PAGE_JSON_LD}
      />

      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '80px 24px 100px' }}>

        {!activeArticle ? (
          <>
            <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.07 } } }}>
              <motion.div variants={fadeUp} transition={{ duration: 0.4 }} style={{ marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#3b82f6' }}>
                  📚 Knowledge Base
                </span>
              </motion.div>
              <motion.h1 variants={fadeUp} transition={{ duration: 0.5 }} style={{ fontSize: '2.75rem', fontWeight: 800, lineHeight: 1.15, marginBottom: '1rem', background: 'linear-gradient(to right, #f4f4f5, #a1a1aa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                Insurance Appeal Resources
              </motion.h1>
              <motion.p variants={fadeUp} transition={{ duration: 0.45 }} style={{ fontSize: '1.125rem', color: '#71717a', lineHeight: 1.65, marginBottom: '3.5rem', maxWidth: '600px' }}>
                Free, expert-level guides on how to fight denied health insurance claims. Written for patients — no legal jargon.
              </motion.p>
            </motion.div>

            <motion.div
              initial="hidden" animate="show"
              variants={{ show: { transition: { staggerChildren: 0.09 } } }}
              style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '20px', marginBottom: '4rem' }}
            >
              {ARTICLES.map(article => (
                <ArticleCard key={article.slug} article={article} onClick={setActiveSlug} />
              ))}
            </motion.div>

            <div style={{ textAlign: 'center', padding: '3rem', background: 'linear-gradient(135deg, rgba(59,130,246,0.1), rgba(168,85,247,0.1))', borderRadius: '20px', border: '1px solid rgba(59,130,246,0.2)' }}>
              <h2 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: '0.75rem' }}>Ready to fight your denied claim?</h2>
              <p style={{ color: '#a1a1aa', marginBottom: '1.5rem' }}>Upload your policy and let the AI generate a legally grounded appeal letter in under 60 seconds.</p>
              <button
                onClick={() => navigate('/claim')}
                style={{ padding: '0.875rem 2.5rem', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: '10px', fontSize: '1rem', fontWeight: 600, cursor: 'pointer' }}
              >
                Evaluate My Claim →
              </button>
            </div>
          </>
        ) : (
          <ArticleView article={activeArticle} onBack={() => setActiveSlug(null)} />
        )}
      </div>
    </div>
  )
}
