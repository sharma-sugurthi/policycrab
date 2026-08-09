import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '../contexts/AuthContext'
import { IconShield, IconCheckCircle } from '../components/Icons'

export default function AuthPage() {
  const { user, signIn, signUp, verifyOtp } = useAuth()
  const [isLogin, setIsLogin] = useState(false) // Default to Sign Up
  const [showOtp, setShowOtp] = useState(false)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [msg, setMsg] = useState(null)

  if (user) {
    return <Navigate to="/" replace />
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setMsg(null)

    try {
      if (showOtp) {
        const { error } = await verifyOtp(email, otp)
        if (error) throw error
      } else if (isLogin) {
        const { error } = await signIn(email, password)
        if (error) throw error
      } else {
        const { error } = await signUp(email, password, fullName)
        if (error) throw error

        // Trigger backend welcome email (fire-and-forget)
        import('../lib/api').then(({ apiFetch }) => {
          apiFetch('/email/welcome', { method: 'POST' }).catch(console.error)
        })

        // OTP logic bypassed - Supabase "Confirm email" must be disabled for this to work
        // setShowOtp(true)
        // setMsg('A verification code has been sent to your email.')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: 'calc(100vh - 72px)', display: 'flex', background: 'var(--bg-primary)' }}>
      {/* ── Left Side: Brand & Testimonial ── */}
      <div style={{ flex: 1, display: 'none', flexDirection: 'column', padding: '4rem', background: '#0a0b0e', position: 'relative', overflow: 'hidden' }} className="auth-left-panel" id="auth-left-panel">
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'radial-gradient(circle at top left, rgba(225,29,72,0.15) 0%, rgba(10,11,14,0) 60%)' }} />
        
        <div style={{ position: 'relative', zIndex: 10, flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: 'auto' }}>
            <img src="/logo.png" alt="PolicyCrab" style={{ width: '32px', height: '32px', filter: 'brightness(0) invert(1)' }} />
            <span style={{ fontWeight: 800, fontSize: '1.25rem', color: '#fff', fontFamily: "'Outfit', sans-serif" }}>PolicyCrab</span>
          </div>

          <div style={{ maxWidth: '480px' }}>
            <div style={{ display: 'flex', gap: '0.25rem', color: '#f59e0b', marginBottom: '1.5rem' }}>
              {'★★★★★'}
            </div>
            <h2 style={{ fontSize: '2.5rem', fontWeight: 800, color: '#fff', lineHeight: 1.1, marginBottom: '1.5rem', letterSpacing: '-0.03em' }}>
              "The engine proved my visit was covered under the No Surprises Act."
            </h2>
            <p style={{ fontSize: '1.125rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: '2.5rem' }}>
              Stop overpaying for healthcare. PolicyCrab cross-references your bills against ERISA, ACA, and your specific plan documents to fight unfair denials.
            </p>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
               <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#cbd5e1' }}>
                 <IconCheckCircle size={20} style={{ color: '#10b981' }} /> Document intelligence and extraction
               </div>
               <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#cbd5e1' }}>
                 <IconCheckCircle size={20} style={{ color: '#10b981' }} /> Automated out-of-pocket calculations
               </div>
               <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#cbd5e1' }}>
                 <IconCheckCircle size={20} style={{ color: '#10b981' }} /> Drafts legally-sound appeal letters
               </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Right Side: Auth Form ── */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem', position: 'relative' }} className="auth-right-panel">
        <div className="hero-grid" style={{ opacity: 0.3 }} />
        
        <motion.div 
          initial={{ opacity: 0, y: 20 }} 
          animate={{ opacity: 1, y: 0 }} 
          transition={{ duration: 0.5 }}
          className="card auth-form-card" 
          style={{ width: '100%', maxWidth: '440px', padding: '3rem 2.5rem', position: 'relative', zIndex: 10, borderTop: '4px solid var(--accent)' }}
        >
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.03em', fontFamily: "'Outfit', sans-serif" }}>
              {isLogin ? 'Welcome back' : 'Create an account'}
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem', marginTop: '0.5rem' }}>
              {isLogin ? 'Sign in to access your claims and policies' : 'Start fighting denied claims today'}
            </p>
          </div>

          {!showOtp && (
            <div style={{ display: 'flex', background: 'var(--bg-secondary)', borderRadius: '0.75rem', padding: '0.25rem', marginBottom: '2rem', border: '1px solid var(--border-secondary)' }}>
              <button 
                type="button"
                style={{ flex: 1, padding: '0.625rem', fontSize: '0.875rem', fontWeight: 600, border: 'none', background: isLogin ? 'var(--bg-card)' : 'transparent', color: isLogin ? 'var(--text-primary)' : 'var(--text-tertiary)', borderRadius: '0.5rem', boxShadow: isLogin ? 'var(--shadow-sm)' : 'none', cursor: 'pointer', transition: 'all 0.2s' }}
                onClick={() => { setIsLogin(true); setError(null); setMsg(null); }}
              >
                Log In
              </button>
              <button 
                type="button"
                style={{ flex: 1, padding: '0.625rem', fontSize: '0.875rem', fontWeight: 600, border: 'none', background: !isLogin ? 'var(--bg-card)' : 'transparent', color: !isLogin ? 'var(--text-primary)' : 'var(--text-tertiary)', borderRadius: '0.5rem', boxShadow: !isLogin ? 'var(--shadow-sm)' : 'none', cursor: 'pointer', transition: 'all 0.2s' }}
                onClick={() => { setIsLogin(false); setError(null); setMsg(null); }}
              >
                Sign Up
              </button>
            </div>
          )}

          {error && (
            <div style={{ padding: '0.75rem 1rem', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: '0.5rem', color: 'var(--danger)', fontSize: '0.875rem', fontWeight: 500, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconShield size={16} /> {error}
            </div>
          )}
          
          {msg && (
            <div style={{ padding: '0.75rem 1rem', background: 'var(--success-bg)', border: '1px solid var(--success-border)', borderRadius: '0.5rem', color: 'var(--success)', fontSize: '0.875rem', fontWeight: 500, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconCheckCircle size={16} /> {msg}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {showOtp ? (
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Verification Code</label>
                <input 
                  type="text" 
                  className="input" 
                  value={otp} 
                  onChange={e => setOtp(e.target.value)} 
                  placeholder="00000000"
                  required 
                  maxLength={8}
                  style={{ textAlign: 'center', letterSpacing: '0.5em', fontSize: '1.5rem', fontWeight: 800, padding: '1rem' }}
                />
              </div>
            ) : (
              <>
                {!isLogin && (
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Full Name</label>
                    <input
                      type="text"
                      className="input"
                      value={fullName}
                      onChange={e => setFullName(e.target.value)}
                      placeholder="Jane Smith"
                      required
                    />
                  </div>
                )}
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Email address</label>
                  <input 
                    type="email" 
                    className="input" 
                    value={email} 
                    onChange={e => setEmail(e.target.value)} 
                    placeholder="you@example.com"
                    required 
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Password</label>
                  <input 
                    type="password" 
                    className="input" 
                    value={password} 
                    onChange={e => setPassword(e.target.value)} 
                    placeholder="••••••••"
                    required 
                    minLength={6}
                  />
                </div>
              </>
            )}

            <button type="submit" className="btn btn-red" style={{ width: '100%', marginTop: '1rem', padding: '1rem', fontSize: '1rem' }} disabled={loading}>
              {loading ? <span className="spinner" /> : showOtp ? 'Verify Code' : isLogin ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </motion.div>
      </div>

      <style>{`
        @media (min-width: 1024px) {
          .auth-left-panel { display: flex !important; }
        }
      `}</style>
    </div>
  )
}
