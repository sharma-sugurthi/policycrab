import { Routes, Route, NavLink, useLocation, Navigate } from 'react-router-dom'
import { useState } from 'react'
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
  const location = useLocation()
  const { user, signOut } = useAuth()

  return (
    <>
      {/* ── Navbar ─────────────────────────────────── */}
      <header className="navbar">
        <div className="navbar-inner">
          <NavLink to="/" className="navbar-brand">
            <img src="/logo.png" alt="PolicyCrab Logo" style={{ width: '32px', height: '32px', objectFit: 'contain' }} />
            <span>PolicyCrab</span>
          </NavLink>

          <nav className="navbar-links">
            <NavLink to="/" className={location.pathname === '/' ? 'active' : ''}>
              Home
            </NavLink>
            <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'active' : ''}>
              Dashboard
            </NavLink>
            <NavLink to="/policy" className={({ isActive }) => isActive ? 'active' : ''}>
              Policy Upload
            </NavLink>
            <NavLink to="/claim" className={({ isActive }) => isActive ? 'active' : ''}>
              Claim Evaluator
            </NavLink>
            <NavLink to="/chat" className={({ isActive }) => isActive ? 'active' : ''}>
              AI Assistant
            </NavLink>
          </nav>

          <div className="navbar-status" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {user ? (
              <>
                <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#3f3f46' }}>{user.email}</span>
                <button onClick={signOut} className="btn btn-ghost" style={{ padding: '0.375rem 0.75rem', fontSize: '0.75rem' }}>Sign Out</button>
              </>
            ) : (
              <NavLink to="/auth" className="btn btn-red" style={{ padding: '0.5rem 1.25rem', fontSize: '0.8125rem' }}>
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
            <Dashboard />
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
