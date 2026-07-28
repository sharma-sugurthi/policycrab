import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch, readApiResponse } from '../lib/api'
import { IconAlertTriangle, IconUser, IconFileText, IconCheckCircle, IconActivity } from '../components/Icons'

const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }

export default function AdminDashboard() {
  const { isAdmin, loading: authLoading, user } = useAuth()
  
  // State
  const [stats, setStats] = useState(null)
  const [activity, setActivity] = useState([])
  const [users, setUsers] = useState([])
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState('overview') // 'overview' | 'users'
  const [fetching, setFetching] = useState(true)
  const [error, setError] = useState(null)
  const [currentPage, setCurrentPage] = useState(1)
  const usersPerPage = 15

  useEffect(() => {
    if (authLoading || !user) return

    async function loadAdminData() {
      setFetching(true)
      setError(null)
      try {
        const [statsRes, actRes, usersRes] = await Promise.all([
          apiFetch('/admin/stats'),
          apiFetch('/admin/activity?days=30'),
          apiFetch('/admin/users')
        ])

        if (statsRes.status === 403 || actRes.status === 403 || usersRes.status === 403) {
          setError('403')
          setFetching(false)
          return
        }

        if (statsRes.ok && actRes.ok && usersRes.ok) {
          const statsData = await readApiResponse(statsRes)
          const actData = await readApiResponse(actRes)
          const usersData = await readApiResponse(usersRes)

          setStats(statsData)
          setActivity(actData?.activity_timeline || [])
          setUsers(usersData?.users || [])
        } else {
          setError('Failed to load admin telemetry. Verify server connection and admin privileges.')
        }
      } catch (err) {
        setError(`Error fetching analytics: ${err.message}`)
      } finally {
        setFetching(false)
      }
    }

    loadAdminData()
  }, [authLoading, user, isAdmin])

  if (authLoading) {
    return (
      <section className="section" style={{ minHeight: '80vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span className="spinner" style={{ width: '3rem', height: '3rem' }} />
      </section>
    )
  }

  // 403 Forbidden Screen for non-admins
  if (error === '403' || (!isAdmin && !fetching && !stats)) {
    return (
      <section className="section" style={{ minHeight: '80vh', display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '2rem' }}>
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-primary)', borderRadius: '1.5rem', padding: '3rem', maxWidth: '480px', boxShadow: 'var(--shadow-lg)' }}>
          <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'var(--danger-bg)', color: 'var(--danger)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem', border: '1px solid var(--danger-border)' }}>
            <IconAlertTriangle size={32} />
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 900, color: 'var(--text-primary)', marginBottom: '0.75rem' }}>Access Denied (403)</h1>
          <p style={{ fontSize: '0.9375rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '2rem' }}>
            This platform intelligence console is strictly restricted to authorized system administrators. Your account ({user?.email}) does not currently possess admin permissions.
          </p>
          <NavLink to="/" className="btn btn-red" style={{ display: 'inline-flex', padding: '0.75rem 2rem', fontWeight: 700 }}>
            Return to Homepage
          </NavLink>
        </div>
      </section>
    )
  }

  // Filter users by search
  const filteredUsers = users.filter(u => 
    (u.email || '').toLowerCase().includes(search.toLowerCase()) ||
    (u.full_name || '').toLowerCase().includes(search.toLowerCase())
  )

  const indexOfLast = currentPage * usersPerPage
  const indexOfFirst = indexOfLast - usersPerPage
  const currentUsers = filteredUsers.slice(indexOfFirst, indexOfLast)
  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / usersPerPage))

  // Find max value in activity timeline for bar chart scaling
  const maxActivityVal = activity.reduce((max, d) => Math.max(max, d.documents + d.audits + d.claims + (d.new_users || 0)), 5)

  return (
    <section className="section" style={{ paddingBottom: '6rem' }}>
      <div className="container" style={{ maxWidth: '1280px', margin: '0 auto' }}>
        {/* Header */}
        <motion.div initial="hidden" animate="show" variants={fadeUp} transition={{ duration: 0.4 }} style={{ marginBottom: '2.5rem', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-end', gap: '1rem' }}>
          <div>
            <span style={{ display: 'inline-block', padding: '0.35rem 0.85rem', background: '#e0e7ff', color: '#3730a3', borderRadius: '9999px', fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem', border: '1px solid #c7d2fe' }}>
              ⚡ Platform Telemetry Console
            </span>
            <h1 style={{ fontSize: '2.5rem', fontWeight: 900, color: 'var(--text-primary)', letterSpacing: '-0.03em' }}>
              Admin Intelligence
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', marginTop: '0.5rem' }}>
              Real-time usage metrics, AI workload ingestion, and user activity overview.
            </p>
          </div>
          
          <div style={{ display: 'flex', gap: '0.5rem', background: 'var(--bg-secondary)', padding: '0.375rem', borderRadius: '1rem', border: '1px solid var(--border-secondary)' }}>
            <button
              onClick={() => setActiveTab('overview')}
              style={{
                padding: '0.5rem 1.25rem', borderRadius: '0.75rem', border: 'none',
                fontWeight: 700, fontSize: '0.875rem', cursor: 'pointer', transition: 'all 0.2s',
                background: activeTab === 'overview' ? 'var(--bg-card)' : 'transparent',
                color: activeTab === 'overview' ? 'var(--text-primary)' : 'var(--text-tertiary)',
                boxShadow: activeTab === 'overview' ? 'var(--shadow-sm)' : 'none'
              }}
            >
              📊 Overview & Activity
            </button>
            <button
              onClick={() => setActiveTab('users')}
              style={{
                padding: '0.5rem 1.25rem', borderRadius: '0.75rem', border: 'none',
                fontWeight: 700, fontSize: '0.875rem', cursor: 'pointer', transition: 'all 0.2s',
                background: activeTab === 'users' ? 'var(--bg-card)' : 'transparent',
                color: activeTab === 'users' ? 'var(--text-primary)' : 'var(--text-tertiary)',
                boxShadow: activeTab === 'users' ? 'var(--shadow-sm)' : 'none'
              }}
            >
              👥 Registered Users ({users.length})
            </button>
          </div>
        </motion.div>

        {fetching && !stats ? (
          <div style={{ textAlign: 'center', padding: '5rem 0' }}>
            <span className="spinner" style={{ width: '2.5rem', height: '2.5rem' }} />
            <p style={{ color: 'var(--text-tertiary)', marginTop: '1rem', fontWeight: 600 }}>Aggregating platform intelligence...</p>
          </div>
        ) : error ? (
          <div style={{ background: 'var(--danger-bg)', color: 'var(--danger)', padding: '1.5rem', borderRadius: '1rem', border: '1px solid var(--danger-border)', textAlign: 'center' }}>
            <p style={{ fontWeight: 700 }}>{error}</p>
            <button onClick={() => window.location.reload()} className="btn btn-outline" style={{ marginTop: '1rem', borderColor: 'var(--danger)', color: 'var(--danger)' }}>Retry</button>
          </div>
        ) : activeTab === 'overview' ? (
          <motion.div initial="hidden" animate="show" variants={fadeUp} transition={{ duration: 0.4, delay: 0.1 }}>
            {/* Metric Cards Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem', marginBottom: '3rem' }}>
              <div style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '1.25rem', border: '1px solid var(--border-primary)', boxShadow: 'var(--shadow-card)', position: 'relative', overflow: 'hidden' }}>
                <div style={{ position: 'absolute', top: 0, right: 0, width: '90px', height: '90px', background: 'radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%)' }} />
                <p style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Registered Users</p>
                <h3 style={{ fontSize: '2.25rem', fontWeight: 900, color: 'var(--text-primary)', marginTop: '0.5rem' }}>{stats?.total_users ?? 0}</h3>
                <p style={{ fontSize: '0.75rem', color: '#059669', fontWeight: 700, marginTop: '0.25rem' }}>✓ Active Accounts</p>
              </div>

              <div style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '1.25rem', border: '1px solid var(--border-primary)', boxShadow: 'var(--shadow-card)' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Policies Ingested</p>
                <h3 style={{ fontSize: '2.25rem', fontWeight: 900, color: 'var(--text-primary)', marginTop: '0.5rem' }}>{stats?.total_policies ?? 0}</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600, marginTop: '0.25rem' }}>Plan Summaries & PDFs</p>
              </div>

              <div style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '1.25rem', border: '1px solid var(--border-primary)', boxShadow: 'var(--shadow-card)' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Document Vault Items</p>
                <h3 style={{ fontSize: '2.25rem', fontWeight: 900, color: 'var(--text-primary)', marginTop: '0.5rem' }}>{stats?.total_documents ?? 0}</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600, marginTop: '0.25rem' }}>EOB Extractions & Scans</p>
              </div>

              <div style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '1.25rem', border: '1px solid var(--border-primary)', boxShadow: 'var(--shadow-card)' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Bill Audits Executed</p>
                <h3 style={{ fontSize: '2.25rem', fontWeight: 900, color: 'var(--text-primary)', marginTop: '0.5rem' }}>{stats?.total_audits ?? 0}</h3>
                <p style={{ fontSize: '0.75rem', color: '#dc2626', fontWeight: 700, marginTop: '0.25rem' }}>⚠️ Fraud & Error Scans</p>
              </div>

              <div style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '1.25rem', border: '1px solid var(--border-primary)', boxShadow: 'var(--shadow-card)' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Claims Evaluated</p>
                <h3 style={{ fontSize: '2.25rem', fontWeight: 900, color: 'var(--text-primary)', marginTop: '0.5rem' }}>{stats?.total_claims ?? 0}</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600, marginTop: '0.25rem' }}>Disputes & Appeals</p>
              </div>

              <div style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '1.25rem', border: '1px solid var(--border-primary)', boxShadow: 'var(--shadow-card)' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>AI Assistant Chats</p>
                <h3 style={{ fontSize: '2.25rem', fontWeight: 900, color: 'var(--text-primary)', marginTop: '0.5rem' }}>{stats?.total_chats ?? 0}</h3>
                <p style={{ fontSize: '0.75rem', color: '#2563eb', fontWeight: 700, marginTop: '0.25rem' }}>💬 Patient Guidance</p>
              </div>
            </div>

            {/* 30-Day Activity Chart */}
            <div style={{ background: 'var(--bg-card)', padding: '2rem', borderRadius: '1.5rem', border: '1px solid var(--border-primary)', boxShadow: 'var(--shadow-card)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>30-Day Activity Breakdown</h3>
                  <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>Daily aggregation of uploads, scans, claim analyses, and new registrations.</p>
                </div>
                <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem', fontWeight: 700 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: '#6366f1' }}>
                    <span style={{ width: '10px', height: '10px', background: '#6366f1', borderRadius: '2px' }} /> Documents
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: '#ef4444' }}>
                    <span style={{ width: '10px', height: '10px', background: '#ef4444', borderRadius: '2px' }} /> Audits & Scans
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: '#10b981' }}>
                    <span style={{ width: '10px', height: '10px', background: '#10b981', borderRadius: '2px' }} /> New Signups
                  </span>
                </div>
              </div>

              {/* Bar Chart Container */}
              <div style={{ display: 'flex', alignItems: 'flex-end', height: '220px', gap: '0.5rem', paddingTop: '1rem', borderBottom: '1px solid var(--border-secondary)', paddingBottom: '0.5rem' }}>
                {activity.map((item, idx) => {
                  const total = item.documents + item.audits + item.claims + (item.new_users || 0)
                  const heightPct = Math.max(8, (total / maxActivityVal) * 100)
                  return (
                    <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end', group: 'true' }} title={`${item.date}: ${total} total actions (${item.documents} docs, ${item.audits} audits, ${item.claims} claims, ${item.new_users || 0} signups)`}>
                      <div style={{ width: '100%', maxWidth: '24px', height: `${heightPct}%`, borderRadius: '4px', background: total > 0 ? 'linear-gradient(to top, #4f46e5, #818cf8)' : 'var(--border-secondary)', transition: 'height 0.3s ease', display: 'flex', flexDirection: 'column-reverse', overflow: 'hidden' }}>
                        {item.documents > 0 && <div style={{ background: '#6366f1', flex: item.documents }} />}
                        {item.audits > 0 && <div style={{ background: '#ef4444', flex: item.audits }} />}
                        {item.claims > 0 && <div style={{ background: '#f59e0b', flex: item.claims }} />}
                        {(item.new_users || 0) > 0 && <div style={{ background: '#10b981', flex: item.new_users }} />}
                      </div>
                      <span style={{ fontSize: '0.625rem', color: 'var(--text-tertiary)', marginTop: '0.5rem', transform: 'rotate(-45deg)', transformOrigin: 'top center', whiteSpace: 'nowrap' }}>
                        {idx % 3 === 0 ? item.date.slice(5) : ''}
                      </span>
                    </div>
                  )
                })}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '1rem' }}>
                <span>{activity[0]?.date}</span>
                <span>{activity[activity.length - 1]?.date}</span>
              </div>
            </div>
          </motion.div>
        ) : (
          <motion.div initial="hidden" animate="show" variants={fadeUp} transition={{ duration: 0.4, delay: 0.1 }}>
            {/* Users Tab */}
            <div style={{ background: 'var(--bg-card)', padding: '2rem', borderRadius: '1.5rem', border: '1px solid var(--border-primary)', boxShadow: 'var(--shadow-card)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>User Directory & Feature Usage</h3>
                  <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Inspect individual adoption across policies, claims, documents, and bill audits.</p>
                </div>
                <input
                  type="text"
                  placeholder="Search email or name..."
                  value={search}
                  onChange={e => { setSearch(e.target.value); setCurrentPage(1) }}
                  style={{
                    padding: '0.625rem 1rem', borderRadius: '0.75rem', border: '1px solid var(--border-secondary)',
                    background: 'var(--bg-primary)', color: 'var(--text-primary)', width: '280px', fontSize: '0.875rem'
                  }}
                />
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--border-secondary)', fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      <th style={{ padding: '0.75rem 1rem' }}>User / Account</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Joined Date</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Policies</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Documents</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Bill Audits</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Claims</th>
                      <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Activity Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {currentUsers.map(u => {
                      const totalActions = (u.documents_count || 0) + (u.audits_count || 0) + (u.claims_count || 0) + (u.policies_count || 0)
                      return (
                        <tr key={u.id} style={{ borderBottom: '1px solid var(--border-secondary)', transition: 'background 0.2s', fontSize: '0.875rem' }}>
                          <td style={{ padding: '1rem' }}>
                            <p style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{u.full_name}</p>
                            <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{u.email}</p>
                          </td>
                          <td style={{ padding: '1rem', color: 'var(--text-secondary)' }}>
                            {u.created_at ? new Date(u.created_at).toLocaleDateString() : 'N/A'}
                          </td>
                          <td style={{ padding: '1rem', textAlign: 'center', fontWeight: 700, color: u.policies_count > 0 ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>
                            {u.policies_count || 0}
                          </td>
                          <td style={{ padding: '1rem', textAlign: 'center', fontWeight: 700, color: u.documents_count > 0 ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>
                            {u.documents_count || 0}
                          </td>
                          <td style={{ padding: '1rem', textAlign: 'center', fontWeight: 700, color: u.audits_count > 0 ? '#dc2626' : 'var(--text-tertiary)' }}>
                            {u.audits_count || 0}
                          </td>
                          <td style={{ padding: '1rem', textAlign: 'center', fontWeight: 700, color: u.claims_count > 0 ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>
                            {u.claims_count || 0}
                          </td>
                          <td style={{ padding: '1rem', textAlign: 'right' }}>
                            {totalActions > 0 ? (
                              <span style={{ padding: '0.25rem 0.625rem', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 800, background: '#dcfce7', color: '#166534' }}>
                                Active User
                              </span>
                            ) : (
                              <span style={{ padding: '0.25rem 0.625rem', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 700, background: 'var(--bg-secondary)', color: 'var(--text-tertiary)' }}>
                                No Activity Yet
                              </span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                    {currentUsers.length === 0 && (
                      <tr>
                        <td colSpan={7} style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-tertiary)' }}>
                          No users found matching your query "{search}".
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border-secondary)' }}>
                  <button
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage(p => p - 1)}
                    className="btn btn-outline"
                    style={{ padding: '0.4rem 1rem', fontSize: '0.8rem', opacity: currentPage === 1 ? 0.5 : 1 }}
                  >
                    ← Previous
                  </button>
                  <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                    Page {currentPage} of {totalPages}
                  </span>
                  <button
                    disabled={currentPage === totalPages}
                    onClick={() => setCurrentPage(p => p + 1)}
                    className="btn btn-outline"
                    style={{ padding: '0.4rem 1rem', fontSize: '0.8rem', opacity: currentPage === totalPages ? 0.5 : 1 }}
                  >
                    Next →
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </section>
  )
}
