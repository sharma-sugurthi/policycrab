import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { readApiResponse } from '../lib/api'

const AuthContext = createContext({})

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [session, setSession] = useState(null)
  const [isAdmin, setIsAdmin] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true

    // SAFETY NET: If auth initialization takes longer than 5 seconds,
    // forcibly unblock the UI. This prevents blank-screen hangs in production
    // caused by Supabase client issues, network failures, or cold starts.
    const safetyTimeout = setTimeout(() => {
      if (mounted && loading) {
        console.warn('Auth initialization safety timeout reached (5s). Unblocking UI.')
        setLoading(false)
      }
    }, 5000)

    async function checkAdmin(token) {
      if (!token) {
        if (mounted) setIsAdmin(false)
        return
      }
      try {
        const res = await fetch('/api/admin/check', {
          cache: 'no-store',
          headers: { Authorization: 'Bearer ' + token },
        })
        if (!mounted) return
        if (res.ok) {
          const data = await readApiResponse(res)
          setIsAdmin(Boolean(data?.is_admin))
        } else {
          setIsAdmin(false)
        }
      } catch (e) {
        console.error('Admin role verification check failed or backend offline:', e.message || e)
        if (mounted) setIsAdmin(false)
      }
    }

    async function initializeAuth() {
      try {
        const { data, error } = await supabase.auth.getSession()
        if (error) console.warn('Supabase session fetch warning:', error)
        
        const currentSession = data?.session || null
        if (!mounted) return
        
        setSession(currentSession)
        setUser(currentSession?.user ?? null)
        
        // UNBLOCK THE UI IMMEDIATELY! Do not wait for Heroku API cold starts.
        if (mounted) setLoading(false)
        
        // Run role verification after auth initialization settles.
        setTimeout(() => {
          if (mounted) checkAdmin(currentSession?.access_token)
        }, 0)
      } catch (err) {
        console.error('Fatal auth initialization error:', err)
        if (mounted) setLoading(false)
      }
    }

    initializeAuth()

    const { data: authListener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      try {
        if (!mounted) return
        setSession(newSession || null)
        setUser(newSession?.user ?? null)
        
        // UNBLOCK THE UI IMMEDIATELY!
        if (mounted) setLoading(false)

        // Defer any async work that may touch Supabase auth until after the
        // auth state callback completes. Calling auth APIs from this callback
        // can leave operations like updateUser/signOut pending in the browser.
        setTimeout(() => {
          if (mounted) checkAdmin(newSession?.access_token)
        }, 0)
      } catch (err) {
        console.error('Auth state change error:', err)
        if (mounted) setLoading(false)
      }
    })

    return () => {
      mounted = false
      clearTimeout(safetyTimeout)
      authListener?.subscription?.unsubscribe()
    }
  }, [])

  const signUp = (email, password, fullName) => supabase.auth.signUp({ email, password, options: { data: { full_name: fullName } } })
  const verifyOtp = (email, token) => supabase.auth.verifyOtp({ email, token, type: 'signup' })
  const signIn = (email, password) => supabase.auth.signInWithPassword({ email, password })
  const signOut = () => supabase.auth.signOut()

  const updateProfile = async (data) => {
    const { data: result, error } = await supabase.auth.updateUser({ data })
    if (error) throw error
    setUser(result.user)
    return result
  }

  const updatePassword = async (newPassword) => {
    const { error } = await supabase.auth.updateUser({ password: newPassword })
    if (error) throw error
  }

  return (
    <AuthContext.Provider value={{ user, session, isAdmin, loading, signUp, verifyOtp, signIn, signOut, updateProfile, updatePassword }}>
      {!loading && children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
