import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '../contexts/AuthContext'

export default function AuthPage() {
  const { user, signIn, signUp, verifyOtp } = useAuth()
  const [isLogin, setIsLogin] = useState(true)
  const [showOtp, setShowOtp] = useState(false)
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
        
        // Trigger backend welcome email (fire-and-forget)
        import('../lib/api').then(({ apiFetch }) => {
          apiFetch('/email/welcome', { method: 'POST' }).catch(console.error)
        })
      } else if (isLogin) {
        const { error } = await signIn(email, password)
        if (error) throw error
      } else {
        const { error } = await signUp(email, password)
        if (error) throw error
        setShowOtp(true)
        setMsg('A 6-digit verification code has been sent to your email.')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: 'calc(100vh - 72px)', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fafafa', padding: '2rem' }}>
      <div className="hero-grid" />
      <motion.div 
        initial={{ opacity: 0, y: 20 }} 
        animate={{ opacity: 1, y: 0 }} 
        transition={{ duration: 0.5 }}
        className="card" 
        style={{ width: '100%', maxWidth: '400px', padding: '2.5rem', position: 'relative', zIndex: 10, background: '#fff' }}
      >
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <img src="/logo.png" alt="PolicyCrab" style={{ width: '48px', height: '48px', margin: '0 auto 1rem' }} />
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#09090b', letterSpacing: '-0.025em' }}>
            {isLogin ? 'Welcome back' : 'Create an account'}
          </h2>
          <p style={{ color: '#71717a', fontSize: '0.875rem', marginTop: '0.5rem' }}>
            {isLogin ? 'Sign in to access your claims and policies' : 'Start fighting denied claims today'}
          </p>
        </div>

        {!showOtp && (
          <div style={{ display: 'flex', background: '#f4f4f5', borderRadius: '0.75rem', padding: '0.25rem', marginBottom: '1.5rem' }}>
            <button 
              type="button"
              style={{ flex: 1, padding: '0.5rem', fontSize: '0.875rem', fontWeight: 600, border: 'none', background: isLogin ? '#fff' : 'transparent', color: isLogin ? '#09090b' : '#71717a', borderRadius: '0.5rem', boxShadow: isLogin ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', cursor: 'pointer', transition: 'all 0.2s' }}
              onClick={() => { setIsLogin(true); setError(null); setMsg(null); }}
            >
              Log In
            </button>
            <button 
              type="button"
              style={{ flex: 1, padding: '0.5rem', fontSize: '0.875rem', fontWeight: 600, border: 'none', background: !isLogin ? '#fff' : 'transparent', color: !isLogin ? '#09090b' : '#71717a', borderRadius: '0.5rem', boxShadow: !isLogin ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', cursor: 'pointer', transition: 'all 0.2s' }}
              onClick={() => { setIsLogin(false); setError(null); setMsg(null); }}
            >
              Sign Up
            </button>
          </div>
        )}

        {error && (
          <div style={{ padding: '0.75rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.5rem', color: '#dc2626', fontSize: '0.8125rem', fontWeight: 500, marginBottom: '1rem' }}>
            {error}
          </div>
        )}
        
        {msg && (
          <div style={{ padding: '0.75rem', background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '0.5rem', color: '#059669', fontSize: '0.8125rem', fontWeight: 500, marginBottom: '1rem' }}>
            {msg}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {showOtp ? (
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#3f3f46', marginBottom: '0.5rem', textTransform: 'uppercase' }}>6-Digit Verification Code</label>
              <input 
                type="text" 
                className="input" 
                value={otp} 
                onChange={e => setOtp(e.target.value)} 
                placeholder="000000"
                required 
                maxLength={6}
                style={{ textAlign: 'center', letterSpacing: '0.5em', fontSize: '1.25rem', fontWeight: 'bold' }}
              />
            </div>
          ) : (
            <>
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#3f3f46', marginBottom: '0.5rem', textTransform: 'uppercase' }}>Email address</label>
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
                <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: '#3f3f46', marginBottom: '0.5rem', textTransform: 'uppercase' }}>Password</label>
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

          <button type="submit" className="btn btn-red" style={{ width: '100%', marginTop: '0.5rem', padding: '0.875rem' }} disabled={loading}>
            {loading ? <span className="spinner" /> : showOtp ? 'Verify Code' : isLogin ? 'Sign In' : 'Create Account'}
          </button>
        </form>
      </motion.div>
    </div>
  )
}
