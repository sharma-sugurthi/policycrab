import { Routes, Route, NavLink, useLocation, Navigate } from 'react-router-dom'
import { useEffect, useState, useRef } from 'react'
import Home from './pages/Home'
import ClaimEvaluator from './pages/ClaimEvaluator'
import ChatAssistant from './pages/ChatAssistant'
import PolicyUpload from './pages/PolicyUpload'
import AuthPage from './pages/AuthPage'
import Dashboard from './pages/Dashboard'
import BillAuditor from './pages/BillAuditor'
import ProfilePage from './pages/ProfilePage'
import BenchmarkDashboard from './pages/BenchmarkDashboard'
import AdminDashboard from './pages/AdminDashboard'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { IconAlertTriangle, IconFileText, IconCheckCircle, IconGavel, IconMoon, IconSun, IconMonitor, IconMenu, IconX, IconLogOut, IconUser, IconChevronDown, IconActivity } from './components/Icons'

// ── Browser storage keys ─────────────────────────────────────
const SS_POLICY_KEY = 'policycrab_policy_profile'
const SS_POLICY_SESSION_KEY = 'policycrab_policy_session'
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

  const ThemeIcon = theme === 'dark' ? IconSun : theme === 'light' ? IconMoon : IconMonitor
  const themeLabel = theme === 'dark' ? 'Switch to system' : theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'

  return { theme, toggleTheme, ThemeIcon, themeLabel }
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
    <div style={{ background: 'var(--warning-bg)', borderBottom: '1px solid var(--warning-border)', padding: '0.625rem 1rem' }} role="alert" aria-live="polite">
      <div className="main" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', padding: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <IconAlertTriangle size={18} style={{ color: 'var(--warning)' }} />
          <p style={{ fontSize: '0.8125rem', color: 'var(--warning)', fontWeight: 500, lineHeight: 1.4 }}>
            <strong style={{ fontWeight: 700 }}>Not legal or medical advice.</strong> PolicyCrab is an informational tool only.
            Always verify calculations with your insurer and consult a licensed professional.
          </p>
        </div>
        <button
          onClick={dismiss}
          style={{ background: 'transparent', border: 'none', color: 'var(--warning)', cursor: 'pointer', padding: '0.25rem', opacity: 0.7 }}
          aria-label="Dismiss disclaimer"
          title="Dismiss"
        >
          <IconX size={16} />
        </button>
      </div>
    </div>
  )
}

// ── Onboarding Tutorial Modal ─────────────────────────────────
const ONBOARDING_SLIDES = [
  {
    icon: <IconFileText size={32} />,
    step: 'Step 1 of 3',
    title: 'Upload Your Insurance Policy',
    desc: 'Upload your plan summary or paste the text. PolicyCrab extracts the coverage details you need for review.',
    color: '#0ea5e9', // Using premium blue instead of flat red
  },
  {
    icon: <IconCheckCircle size={32} />,
    step: 'Step 2 of 3',
    title: 'Describe Your Claim',
    desc: 'Upload your Explanation of Benefits (EOB) or describe what happened. The app can help auto-fill details from your EOB.',
    color: '#d97706',
  },
  {
    icon: <IconGavel size={32} />,
    step: 'Step 3 of 3',
    title: 'Get Your Appeal Letter',
    desc: 'The app drafts a formally written appeal letter using your plan details, denial codes, and the applicable rules.',
    color: '#10b981',
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
      background: 'rgba(9,9,11,0.82)', backdropFilter: 'blur(12px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '1.5rem',
    }} role="dialog" aria-modal="true" aria-label="Welcome to PolicyCrab">
      <div style={{
        background: 'var(--bg-primary)', borderRadius: '1.5rem', width: '100%', maxWidth: '440px',
        padding: '2.5rem 2.5rem 2rem', boxShadow: 'var(--shadow-card)',
        position: 'relative', textAlign: 'center', border: '1px solid var(--border-primary)'
      }}>
        {/* Skip */}
        <button onClick={finish} aria-label="Skip tutorial" style={{
          position: 'absolute', top: '1.25rem', right: '1.25rem',
          background: 'none', border: 'none', color: 'var(--text-tertiary)',
          fontSize: '0.75rem', cursor: 'pointer', fontWeight: 600,
        }}>Skip tour</button>

        {/* Icon */}
        <div style={{
          width: '72px', height: '72px', borderRadius: '50%',
          background: `${current.color}15`, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          color: current.color, margin: '0 auto 1.25rem',
          border: `2px solid ${current.color}30`,
        }}>
          {current.icon}
        </div>

        {/* Step label */}
        <p style={{ fontSize: '0.6875rem', fontWeight: 800, color: current.color,
          textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.5rem', fontFamily: "'JetBrains Mono', monospace" }}>
          {current.step}
        </p>

        {/* Title */}
        <h2 style={{ fontSize: '1.375rem', fontWeight: 800, color: 'var(--text-primary)',
          marginBottom: '0.75rem', lineHeight: 1.3, letterSpacing: '-0.02em' }}>
          {current.title}
        </h2>

        {/* Description */}
        <p style={{ fontSize: '0.9375rem', color: 'var(--text-secondary)', lineHeight: 1.65,
          marginBottom: '2rem' }}>
          {current.desc}
        </p>

        {/* Dot indicators */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: '0.375rem', marginBottom: '1.5rem' }}>
          {ONBOARDING_SLIDES.map((_, i) => (
            <button key={i} onClick={() => setSlide(i)} aria-label={`Go to slide ${i + 1}`} style={{
              width: i === slide ? '24px' : '8px', height: '8px',
              borderRadius: '999px', border: 'none', cursor: 'pointer',
              background: i === slide ? current.color : 'var(--border-primary)',
              transition: 'all 0.3s ease',
              padding: 0,
            }} />
          ))}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          {slide > 0 && (
            <button onClick={() => setSlide(s => s - 1)} className="btn btn-ghost" style={{ flex: 1, height: '44px' }}>
              Back
            </button>
          )}
          <button
            onClick={isLast ? finish : () => setSlide(s => s + 1)}
            style={{
              flex: 1, height: '44px', borderRadius: '999px',
              background: current.color, color: '#fff', border: 'none',
              fontWeight: 700, fontSize: '0.9375rem', cursor: 'pointer',
              transition: 'transform 0.2s, box-shadow 0.2s',
              boxShadow: `0 4px 14px ${current.color}40`,
            }}
          >
            {isLast ? 'Get Started' : 'Next'}
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
  const [policySession, setPolicySessionState] = useState(() => {
    try {
      const stored = sessionStorage.getItem(SS_POLICY_SESSION_KEY)
      return stored ? JSON.parse(stored) : null
    } catch {
      return null
    }
  })
  const [costBreakdown, setCostBreakdown] = useState(null)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()
  const { user, signOut, isAdmin } = useAuth()
  const { theme, toggleTheme, ThemeIcon, themeLabel } = useTheme()

  // User Dropdown State
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

  // Keep loaded policy session-scoped to avoid persistent browser storage of plan details
  const setPolicyProfile = (profile, session = null) => {
    setPolicyProfileState(profile)
    if (profile) {
      try { sessionStorage.setItem(SS_POLICY_KEY, JSON.stringify(profile)) } catch {}
      setPolicySessionState(session)
      try {
        if (session) sessionStorage.setItem(SS_POLICY_SESSION_KEY, JSON.stringify(session))
        else sessionStorage.removeItem(SS_POLICY_SESSION_KEY)
      } catch {}
    } else {
      sessionStorage.removeItem(SS_POLICY_KEY)
      setPolicySessionState(null)
      sessionStorage.removeItem(SS_POLICY_SESSION_KEY)
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
    ['/audit', 'Bill Auditor'],
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
            <img src="/logo.png" alt="PolicyCrab Logo" className="navbar-brand-logo" />
            <span>PolicyCrab</span>
          </NavLink>

          {/* Loaded policy pill */}
          {policyProfile && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.25rem 0.375rem 0.25rem 0.75rem', background: 'var(--accent-subtle)', borderRadius: '999px', border: '1px solid var(--accent-border)' }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent)', animation: 'pulseRed 2s infinite' }} />
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent)', maxWidth: '120px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {policyProfile.plan_name || 'Policy Loaded'}
              </span>
              <button
                onClick={clearPolicy}
                style={{ background: 'transparent', border: 'none', color: 'var(--accent)', cursor: 'pointer', padding: '0.25rem', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                aria-label="Clear loaded policy"
                title="Clear policy"
              ><IconX size={12} /></button>
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
            <button
              type="button"
              className="theme-toggle"
              onClick={toggleTheme}
              aria-label={themeLabel}
              title={themeLabel}
            >
              <ThemeIcon size={16} />
            </button>
            
            {user ? (
              <div style={{ position: 'relative' }} ref={dropdownRef}>
                <button 
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  style={{ 
                    display: 'flex', alignItems: 'center', gap: '0.5rem', 
                    background: 'var(--bg-secondary)', border: '1px solid var(--border-secondary)', 
                    padding: '0.25rem 0.75rem 0.25rem 0.25rem', borderRadius: '999px', cursor: 'pointer',
                    transition: 'border-color 0.2s', color: 'var(--text-primary)'
                  }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                  onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-secondary)'}
                >
                  <div style={{ 
                    width: '32px', height: '32px', borderRadius: '50%', 
                    background: 'var(--accent)', color: 'white', 
                    display: 'flex', alignItems: 'center', justifyContent: 'center', 
                    fontSize: '0.875rem', fontWeight: 800 
                  }}>
                    {user.user_metadata?.full_name ? user.user_metadata.full_name.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}
                  </div>
                  <span style={{ fontSize: '0.875rem', fontWeight: 600, maxWidth: '100px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {user.user_metadata?.full_name ? user.user_metadata.full_name.split(' ')[0] : 'Account'}
                  </span>
                  <IconChevronDown size={14} style={{ color: 'var(--text-tertiary)' }} />
                </button>
                
                {dropdownOpen && (
                  <div style={{ 
                    position: 'absolute', top: '100%', right: 0, marginTop: '0.5rem', 
                    background: 'var(--bg-card)', border: '1px solid var(--border-secondary)', 
                    borderRadius: '0.75rem', padding: '0.5rem', minWidth: '200px',
                    boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1)', zIndex: 50
                  }}>
                    <div style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border-secondary)', marginBottom: '0.5rem' }}>
                      <p style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.user_metadata?.full_name || 'User'}</p>
                      <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.email}</p>
                    </div>
                    <NavLink to="/profile" onClick={() => setDropdownOpen(false)} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', fontSize: '0.875rem', color: 'var(--text-primary)', borderRadius: '0.375rem', textDecoration: 'none' }} className="dropdown-item">
                      <IconUser size={16} /> Profile
                    </NavLink>
                    {isAdmin && (
                      <NavLink to="/admin" onClick={() => setDropdownOpen(false)} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', fontSize: '0.875rem', color: '#4f46e5', fontWeight: 700, borderRadius: '0.375rem', textDecoration: 'none' }} className="dropdown-item">
                        <IconActivity size={16} /> Admin Console
                      </NavLink>
                    )}
                    <button onClick={() => { setDropdownOpen(false); handleSignOut(); }} style={{ width: '100%', textAlign: 'left', display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', fontSize: '0.875rem', color: 'var(--danger)', borderRadius: '0.375rem', background: 'transparent', border: 'none', cursor: 'pointer' }} className="dropdown-item">
                      <IconLogOut size={16} /> Sign Out
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <NavLink to="/auth" className="btn btn-red" style={{ padding: '0.5rem 1.25rem', fontSize: '0.875rem' }}>
                Sign In
              </NavLink>
            )}
            
            <button
              type="button"
              className={`mobile-menu-button${mobileMenuOpen ? ' active' : ''}`}
              aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-navigation"
              onClick={() => setMobileMenuOpen(open => !open)}
            >
              {mobileMenuOpen ? <IconX size={20} /> : <IconMenu size={20} />}
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
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <span style={{ fontSize: '0.9375rem', fontWeight: 600 }}>{user.user_metadata?.full_name || user.email}</span>
                <NavLink to="/profile" className="btn btn-outline" style={{ display: 'flex', justifyContent: 'center' }} onClick={() => setMobileMenuOpen(false)}><IconUser size={16} /> Profile</NavLink>
                {isAdmin && (
                  <NavLink to="/admin" className="btn btn-outline" style={{ display: 'flex', justifyContent: 'center', color: '#4f46e5', borderColor: '#818cf8', fontWeight: 700 }} onClick={() => setMobileMenuOpen(false)}><IconActivity size={16} /> Admin Console</NavLink>
                )}
                <button onClick={handleSignOut} className="btn btn-ghost" style={{ display: 'flex', justifyContent: 'center' }}><IconLogOut size={16} /> Sign Out</button>
              </div>
            ) : (
              <NavLink to="/auth" className="btn btn-red" style={{ display: 'flex', justifyContent: 'center' }}>
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
            <ClaimEvaluator policyProfile={policyProfile} policySession={policySession} onResult={setCostBreakdown} />
          </ProtectedRoute>
        } />
        <Route path="/audit" element={
          <ProtectedRoute>
            <BillAuditor />
          </ProtectedRoute>
        } />
        <Route path="/profile" element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        } />
        <Route path="/chat" element={
          <ProtectedRoute>
            <ChatAssistant policyProfile={policyProfile} costBreakdown={costBreakdown} />
          </ProtectedRoute>
        } />
        <Route path="/admin" element={
          <ProtectedRoute>
            <AdminDashboard />
          </ProtectedRoute>
        } />
        <Route path="/benchmarks" element={<BenchmarkDashboard />} />
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
