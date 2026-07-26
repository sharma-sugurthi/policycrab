import { Routes, Route, NavLink, useLocation, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Home from './pages/Home'
import ClaimEvaluator from './pages/ClaimEvaluator'
import ChatAssistant from './pages/ChatAssistant'
import PolicyUpload from './pages/PolicyUpload'
import AuthPage from './pages/AuthPage'
import Dashboard from './pages/Dashboard'
import { AuthProvider, useAuth } from './contexts/AuthContext'

// ── Browser storage keys ─────────────────────────────────────
const SS_POLICY_KEY = 'policycrab_policy_profile'
const LS_DISCLAIMER_KEY = 'policycrab_disclaimer_dismissed'
const LS_ONBOARDED_KEY = 'policycrab_onboarded'
const LS_THEME_KEY = 'policycrab_theme'

// ── Theme Hook (3-state: system / light / dark) ──────────────
function useTheme() {
  const [theme, setThemeState] = useState(() => {
    try {
      const stored = localStorage.getItem(LS_THEME_KEY)
      if (stored === 'dark' || stored === 'light' || stored === 'system') return stored
    } catch {}
    return 'system' // default to system
  })

  // Apply the resolved theme to <html data-theme>
  const applyResolved = (t) => {
    const resolved = t === 'system'
      ? (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : t
    document.documentElement.setAttribute('data-theme', resolved)
  }

  useEffect(() => {
    applyResolved(theme)
    localStorage.setItem(LS_THEME_KEY, theme)

    // When in system mode, listen for OS theme changes
    if (theme === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      const handler = () => applyResolved('system')
      mq.addEventListener('change', handler)
      return () => mq.removeEventListener('change', handler)
    }
  }, [theme])

  // Cycle: system → light → dark → system
  const toggleTheme = () => setThemeState(t => {
    if (t === 'system') return 'light'
    if (t === 'light') return 'dark'
    return 'system'
  })

  const themeIcon = theme === 'dark' ? '☀️' : theme === 'light' ? '🌙' : '🖥️'
  const themeLabel = theme === 'dark' ? 'Switch to system' : theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'

  return { theme, toggleTheme, themeIcon, themeLabel }
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}><span className="spinner" /></div>
  if (!user) return <Navigate to="/auth" replace />
  return children
}

// ── Disclaimer Banner ────────────────────────────────────────
function DisclaimerBanner() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const dismissed = localStorage.getItem(LS_DISCLAIMER_KEY)
    if (!dismissed) setVisible(true)
  }, [])

  const dismiss = () => {
    localStorage.setItem(LS_DISCLAIMER_KEY, '1')
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div className="disclaimer-banner" role="alert" aria-live="polite">
      <span className="disclaimer-icon">⚠️</span>
      <p className="disclaimer-text">
        <strong>Not legal or medical advice.</strong> PolicyCrab is an informational tool only.
        Always verify calculations with your insurer and consult a licensed professional for legal or medical decisions.
        Use at your own risk.
      </p>
      <button
        onClick={dismiss}
        className="disclaimer-close"
        aria-label="Dismiss disclaimer"
        title="Dismiss"
      >
        ✕
      </button>
    </div>
  )
}

// ── Onboarding Tutorial Modal ─────────────────────────────────
const ONBOARDING_SLIDES = [
  {
    icon: '📋',
    step: 'Step 1 of 3',
    title: 'Upload Your Insurance Policy',
    desc: 'Upload your plan summary or paste the text. PolicyCrab extracts the coverage details you need for review.',
    color: '#dc2626',
  },
  {
    icon: '🧾',
    step: 'Step 2 of 3',
    title: 'Describe Your Claim',
    desc: 'Upload your Explanation of Benefits (EOB) or describe what happened — the service, provider, billed amount, and any denial reason. The app can help auto-fill details from your EOB.',
    color: '#d97706',
  },
  {
    icon: '⚖️',
    step: 'Step 3 of 3',
    title: 'Get Your Appeal Letter',
    desc: 'The app drafts a formally written appeal letter using your plan details, denial codes, and the applicable rules. Download it as a PDF and mail it certified.',
    color: '#16a34a',
  },
]

function OnboardingTutorial() {
  const [visible, setVisible] = useState(false)
  const [slide, setSlide] = useState(0)

  useEffect(() => {
    const done = localStorage.getItem(LS_ONBOARDED_KEY)
    if (!done) setVisible(true)
  }, [])

  const finish = () => {
    localStorage.setItem(LS_ONBOARDED_KEY, '1')
    setVisible(false)
  }

  if (!visible) return null

  const current = ONBOARDING_SLIDES[slide]
  const isLast = slide === ONBOARDING_SLIDES.length - 1

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(9,9,11,0.82)', backdropFilter: 'blur(6px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '1.5rem',
    }} role="dialog" aria-modal="true" aria-label="Welcome to PolicyCrab">
      <div style={{
        background: '#fff', borderRadius: '1.5rem', width: '100%', maxWidth: '420px',
        padding: '2.5rem 2rem 2rem', boxShadow: '0 24px 80px rgba(0,0,0,0.28)',
        position: 'relative', textAlign: 'center',
      }}>
        {/* Skip */}
        <button onClick={finish} aria-label="Skip tutorial" style={{
          position: 'absolute', top: '1rem', right: '1rem',
          background: 'none', border: 'none', color: '#a1a1aa',
          fontSize: '0.75rem', cursor: 'pointer', fontWeight: 600,
        }}>Skip tour</button>

        {/* Icon */}
        <div style={{
          width: '64px', height: '64px', borderRadius: '50%',
          background: `${current.color}15`, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          fontSize: '2rem', margin: '0 auto 1.25rem',
          border: `2px solid ${current.color}30`,
        }}>
          {current.icon}
        </div>

        {/* Step label */}
        <p style={{ fontSize: '0.6875rem', fontWeight: 700, color: current.color,
          textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.375rem' }}>
          {current.step}
        </p>

        {/* Title */}
        <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#09090b',
          marginBottom: '0.75rem', lineHeight: 1.3 }}>
          {current.title}
        </h2>

        {/* Description */}
        <p style={{ fontSize: '0.9rem', color: '#52525b', lineHeight: 1.65,
          marginBottom: '2rem' }}>
          {current.desc}
        </p>

        {/* Dot indicators */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: '0.375rem', marginBottom: '1.5rem' }}>
          {ONBOARDING_SLIDES.map((_, i) => (
            <button key={i} onClick={() => setSlide(i)} aria-label={`Go to slide ${i + 1}`} style={{
              width: i === slide ? '20px' : '8px', height: '8px',
              borderRadius: '999px', border: 'none', cursor: 'pointer',
              background: i === slide ? current.color : '#e4e4e7',
              transition: 'all 0.25s ease',
              padding: 0,
            }} />
          ))}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          {slide > 0 && (
            <button onClick={() => setSlide(s => s - 1)} className="btn btn-ghost" style={{ flex: 1 }}>
              ← Back
            </button>
          )}
          <button
            onClick={isLast ? finish : () => setSlide(s => s + 1)}
            style={{
              flex: 1, padding: '0.75rem', borderRadius: '0.75rem',
              background: current.color, color: '#fff', border: 'none',
              fontWeight: 700, fontSize: '0.9375rem', cursor: 'pointer',
              transition: 'opacity 0.2s',
            }}
          >
            {isLast ? 'Get Started →' : 'Next →'}
          </button>
        </div>
      </div>
    </div>
  )
}

function AppContent() {
  // ── Restore loaded policy for this browser session only ─────
  const [policyProfile, setPolicyProfileState] = useState(() => {
    try {
      const stored = sessionStorage.getItem(SS_POLICY_KEY)
      return stored ? JSON.parse(stored) : null
    } catch {
      return null
    }
  })
  const [costBreakdown, setCostBreakdown] = useState(null)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()
  const { user, signOut } = useAuth()
  const { theme, toggleTheme, themeIcon, themeLabel } = useTheme()

  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

  // Keep loaded policy session-scoped to avoid persistent browser storage of plan details
  const setPolicyProfile = (profile) => {
    setPolicyProfileState(profile)
    if (profile) {
      try { sessionStorage.setItem(SS_POLICY_KEY, JSON.stringify(profile)) } catch {}
    } else {
      sessionStorage.removeItem(SS_POLICY_KEY)
    }
  }

  const clearPolicy = () => {
    setPolicyProfile(null)
    setCostBreakdown(null)
  }

  const navItems = [
    ['/', 'Home'],
    ['/dashboard', 'Dashboard'],
    ['/policy', 'Policy Upload'],
    ['/claim', 'Claim Evaluator'],
    ['/chat', 'AI Assistant'],
  ]

  const handleSignOut = async () => {
    setMobileMenuOpen(false)
    await signOut()
  }

  return (
    <>
      {/* ── Onboarding Tutorial ──────────────────────────────── */}
      <OnboardingTutorial />

      {/* ── Disclaimer Banner ───────────────────────────────── */}
      <DisclaimerBanner />

      {/* ── Navbar ─────────────────────────────────── */}
      <header className="navbar">
        <div className="navbar-inner">
          <NavLink to="/" className="navbar-brand">
            <img src="/logo.png" alt="PolicyCrab Logo" style={{ width: '32px', height: '32px', objectFit: 'contain' }} />
            <span>PolicyCrab</span>
          </NavLink>

          {/* Loaded policy pill */}
          {policyProfile && (
            <div className="navbar-policy-pill" title={`${policyProfile.carrier_name} — ${policyProfile.plan_type}`}>
              <span className="navbar-policy-dot" />
              <span className="navbar-policy-name">{policyProfile.plan_name || 'Policy Loaded'}</span>
              <button
                onClick={clearPolicy}
                className="navbar-policy-clear"
                aria-label="Clear loaded policy"
                title="Clear policy"
              >✕</button>
            </div>
          )}

          <nav className="navbar-links" aria-label="Primary navigation">
            {navItems.map(([to, label]) => (
              <NavLink key={to} to={to} className={to === '/' ? (location.pathname === '/' ? 'active' : '') : ({ isActive }) => isActive ? 'active' : ''}>
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="navbar-status" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {user ? (
              <>
                <span className="navbar-email">{user.email}</span>
                <button onClick={handleSignOut} className="btn btn-ghost" style={{ padding: '0.375rem 0.75rem', fontSize: '0.75rem' }}>Sign Out</button>
              </>
            ) : (
              <NavLink to="/auth" className="btn btn-red" style={{ padding: '0.5rem 1.25rem', fontSize: '0.8125rem' }}>
                Sign In
              </NavLink>
            )}
            <button
              type="button"
              className="theme-toggle"
              onClick={toggleTheme}
              aria-label={themeLabel}
              title={themeLabel}
            >
              {themeIcon}
            </button>
            <button
              type="button"
              className={`mobile-menu-button${mobileMenuOpen ? ' active' : ''}`}
              aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-navigation"
              onClick={() => setMobileMenuOpen(open => !open)}
            >
              <span />
              <span />
              <span />
            </button>
          </div>
        </div>

        <div id="mobile-navigation" className={`mobile-nav${mobileMenuOpen ? ' open' : ''}`}>
          <nav className="mobile-nav-links" aria-label="Mobile navigation">
            {navItems.map(([to, label]) => (
              <NavLink key={to} to={to} className={to === '/' ? (location.pathname === '/' ? 'active' : '') : ({ isActive }) => isActive ? 'active' : ''}>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="mobile-nav-account">
            {user ? (
              <>
                <span>{user.email}</span>
                <button onClick={handleSignOut} className="btn btn-ghost">Sign Out</button>
              </>
            ) : (
              <NavLink to="/auth" className="btn btn-red">
                Sign In
              </NavLink>
            )}
          </div>
        </div>
      </header>

      {/* ── Main ──────────────────────────────────── */}
      <Routes>
        <Route path="/" element={<Home policyProfile={policyProfile} costBreakdown={costBreakdown} />} />
        <Route path="/auth" element={<AuthPage />} />
        
        {/* Protected Routes */}
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <Dashboard policyProfile={policyProfile} onPolicySelected={setPolicyProfile} />
          </ProtectedRoute>
        } />
        <Route path="/policy" element={
          <ProtectedRoute>
            <PolicyUpload onPolicyParsed={setPolicyProfile} />
          </ProtectedRoute>
        } />
        <Route path="/claim" element={
          <ProtectedRoute>
            <ClaimEvaluator policyProfile={policyProfile} onResult={setCostBreakdown} />
          </ProtectedRoute>
        } />
        <Route path="/chat" element={
          <ProtectedRoute>
            <ChatAssistant policyProfile={policyProfile} costBreakdown={costBreakdown} />
          </ProtectedRoute>
        } />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}
