import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'

const fadeUp = { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0 } }

export default function Dashboard() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const [policies, setPolicies] = useState([])
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      try {
        const headers = { 'Authorization': `Bearer ${session?.access_token}` }
        const [polRes, claimRes] = await Promise.all([
          fetch('/api/history/policies', { headers }),
          fetch('/api/history/claims', { headers })
        ])
        
        if (polRes.ok) setPolicies(await polRes.json())
        if (claimRes.ok) setClaims(await claimRes.json())
      } catch (err) {
        console.error("Failed to load history", err)
      } finally {
        setLoading(false)
      }
    }
    
    if (session) fetchData()
  }, [session])

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}><span className="spinner" /></div>
  }

  return (
    <section className="section-white section-pad">
      <div className="main">
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.08 } } }} style={{ marginBottom: '3rem' }}>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.55 }} className="section-title">
            My <span className="gradient-text">Dashboard</span>
          </motion.h1>
          <motion.p variants={fadeUp} transition={{ duration: 0.45 }} className="section-subtitle">
            Manage your uploaded policies and past claim evaluations.
          </motion.p>
        </motion.div>

        <div className="grid-2">
          {/* Policies Column */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#09090b' }}>Saved Policies</h2>
              <button className="btn btn-red" style={{ padding: '0.375rem 0.75rem', fontSize: '0.75rem' }} onClick={() => navigate('/policy')}>+ New</button>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {policies.length === 0 ? (
                <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
                  <p style={{ color: '#71717a', fontSize: '0.875rem' }}>No policies uploaded yet.</p>
                </div>
              ) : (
                policies.map(p => (
                  <div key={p.id} className="card" style={{ padding: '1.25rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                      <h3 style={{ fontWeight: 700, color: '#09090b', fontSize: '0.9375rem' }}>{p.policy_profile?.plan_name || 'Unknown Plan'}</h3>
                      <span style={{ fontSize: '0.75rem', color: '#a1a1aa' }}>{new Date(p.created_at).toLocaleDateString()}</span>
                    </div>
                    <p style={{ fontSize: '0.8125rem', color: '#52525b', marginBottom: '0.75rem' }}>
                      {p.policy_profile?.carrier_name} • {p.policy_profile?.plan_type}
                    </p>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <span className="badge badge-zinc">Ded: ${p.policy_profile?.in_network_deductible_individual}</span>
                      <span className="badge badge-zinc">OOP: ${p.policy_profile?.in_network_oop_max_individual}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </motion.div>

          {/* Claims Column */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#09090b' }}>Claim History</h2>
              <button className="btn btn-red" style={{ padding: '0.375rem 0.75rem', fontSize: '0.75rem' }} onClick={() => navigate('/claim')}>+ New</button>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {claims.length === 0 ? (
                <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
                  <p style={{ color: '#71717a', fontSize: '0.875rem' }}>No claims evaluated yet.</p>
                </div>
              ) : (
                claims.map(c => (
                  <div key={c.id} className="card" style={{ padding: '1.25rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                      <span className={`badge ${c.route_decision === 'denied' ? 'badge-danger' : 'badge-success'}`}>
                        {c.route_decision === 'denied' ? 'Denied' : 'Approved'}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: '#a1a1aa' }}>{new Date(c.created_at).toLocaleDateString()}</span>
                    </div>
                    <p style={{ fontSize: '0.8125rem', color: '#3f3f46', marginBottom: '0.75rem', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      "{c.claim_description}"
                    </p>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#fafafa', padding: '0.5rem 0.75rem', borderRadius: '0.5rem' }}>
                      <span style={{ fontSize: '0.75rem', color: '#71717a', fontWeight: 500 }}>Patient Responsibility</span>
                      <span style={{ fontWeight: 700, color: '#dc2626', fontSize: '0.875rem' }}>${c.cost_breakdown?.total_patient_responsibility?.toLocaleString()}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
