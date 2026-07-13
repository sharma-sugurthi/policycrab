import { Routes, Route, NavLink, useLocation, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Home from './pages/Home'
import ClaimEvaluator from './pages/ClaimEvaluator'
import ChatAssistant from './pages/ChatAssistant'
import PolicyUpload from './pages/PolicyUpload'
import AuthPage from './pages/AuthPage'
import Dashboard from './pages/Dashboard'
import { AuthProvider, useAuth } from './contexts/AuthContext'

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}><span className="spinner" /></div>
  if (!user) return <Navigate to="/auth" replace />
  return children
}

function AppContent() {
  const [policyProfile, setPolicyProfile] = useState(null)
  const [costBreakdown, setCostBreakdown] = useState(null)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()
  const { user, signOut } = useAuth()

  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

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
      {/* ── Navbar ─────────────────────────────────── */}
      <header className="navbar">
        <div className="navbar-inner">
          <NavLink to="/" className="navbar-brand">
            <img src="/logo.png" alt="PolicyCrab Logo" style={{ width: '32px', height: '32px', objectFit: 'contain' }} />
            <span>PolicyCrab</span>
          </NavLink>

          <nav className="navbar-links" aria-label="Primary navigation">
            {navItems.map(([to, label]) => (
              <NavLink key={to} to={to} className={to === '/' ? (location.pathname === '/' ? 'active' : '') : ({ isActive }) => isActive ? 'active' : ''}>
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="navbar-status" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
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
