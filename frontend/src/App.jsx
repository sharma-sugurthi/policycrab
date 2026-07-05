import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { useState } from 'react'
import Home from './pages/Home'
import ClaimEvaluator from './pages/ClaimEvaluator'
import ChatAssistant from './pages/ChatAssistant'
import PolicyUpload from './pages/PolicyUpload'

export default function App() {
  const [policyProfile, setPolicyProfile] = useState(null)
  const [costBreakdown, setCostBreakdown] = useState(null)
  const location = useLocation()

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

          <div className="navbar-status">
            {policyProfile ? (
              <div className="badge badge-success">✅ Policy Loaded</div>
            ) : (
              <div className="badge badge-zinc">No Policy</div>
            )}
          </div>
        </div>
      </header>

      {/* ── Main ──────────────────────────────────── */}
      <Routes>
        <Route path="/" element={<Home policyProfile={policyProfile} costBreakdown={costBreakdown} />} />
        <Route path="/policy" element={<PolicyUpload onPolicyParsed={setPolicyProfile} />} />
        <Route path="/claim" element={<ClaimEvaluator policyProfile={policyProfile} onResult={setCostBreakdown} />} />
        <Route path="/chat" element={<ChatAssistant policyProfile={policyProfile} costBreakdown={costBreakdown} />} />
      </Routes>
    </>
  )
}
