import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useOrg } from '../contexts/OrgContext'
import { apiFetch, formatApiError, readApiResponse } from '../lib/api'
import { ROLE_BADGE, ROLE_HELP, ROLE_LABEL, canManageMember, grantableRoles, roleAtLeast } from '../lib/orgs'
import {
  IconAlertTriangle, IconCheckCircle, IconCopy, IconMail, IconPlus, IconSettings, IconTrash, IconUsers,
} from '../components/Icons'

const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }
const labelStyle = { display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }

async function call(endpoint, options, fallback) {
  const res = await apiFetch(endpoint, options)
  const data = await readApiResponse(res)
  if (!res.ok) throw new Error(formatApiError(data, fallback))
  return data
}

function Status({ status }) {
  if (!status) return null
  const ok = status.type === 'success'
  return (
    <div role={ok ? 'status' : 'alert'} style={{
      padding: '0.75rem 1rem', borderRadius: '0.5rem', fontSize: '0.875rem', display: 'flex', alignItems: 'flex-start', gap: '0.5rem',
      background: ok ? 'var(--success-bg)' : 'var(--danger-bg)', color: ok ? 'var(--success)' : 'var(--danger)',
      border: `1px solid ${ok ? '#a7f3d0' : '#fecaca'}`, lineHeight: 1.5,
    }}>
      {ok ? <IconCheckCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} /> : <IconAlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />}
      <span style={{ wordBreak: 'break-word' }}>{status.message}</span>
    </div>
  )
}

function RoleBadge({ role }) {
  return <span className={`badge ${ROLE_BADGE[role] || 'badge-zinc'}`}>{ROLE_LABEL[role] || role}</span>
}

export default function OrganizationsPage() {
  const { enabled, orgs, activeOrg, setActiveOrgId, refresh, loading, loaded } = useOrg()
  const [selectedId, setSelectedId] = useState(null)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [createStatus, setCreateStatus] = useState(null)

  const selected = orgs.find(o => o.id === selectedId) || activeOrg || orgs[0] || null

  const createOrg = async (e) => {
    e.preventDefault()
    setCreating(true)
    setCreateStatus(null)
    try {
      const org = await call('/orgs', { method: 'POST', body: JSON.stringify({ name: newName }) }, 'Could not create the workspace.')
      setNewName('')
      await refresh()
      setSelectedId(org.id)
      if (!activeOrg) setActiveOrgId(org.id)
      setCreateStatus({ type: 'success', message: `Workspace "${org.name}" created. You are its owner.` })
    } catch (err) {
      setCreateStatus({ type: 'error', message: err.message })
    } finally {
      setCreating(false)
    }
  }

  return (
    <section className="section-white section-pad">
      <div className="main" style={{ maxWidth: '900px', margin: '0 auto' }}>
        <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.1 } } }}>
          <motion.h1 variants={fadeUp} transition={{ duration: 0.5 }} className="section-title" style={{ marginBottom: '0.5rem' }}>
            Team <span className="gradient-text">Workspaces</span>
          </motion.h1>
          <motion.p variants={fadeUp} transition={{ duration: 0.5 }} className="section-subtitle" style={{ marginBottom: '2.5rem', textAlign: 'left' }}>
            Share claims and appeals with your advocacy firm, billing office or benefits team. Pick an active workspace and every
            evaluation you run is saved to it; switch back to personal any time.
          </motion.p>
        </motion.div>

        {!enabled && loaded && (
          <div className="card" style={{ padding: '2rem' }}>
            <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Team workspaces are not enabled here</h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              This deployment runs in single-user mode. An administrator can turn workspaces on by applying database migration 009 and
              setting <code>ORGS_ENABLED=true</code> on the backend.
            </p>
          </div>
        )}

        {enabled && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            {/* ── Your workspaces ─────────────────────────────────────── */}
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }} className="card" style={{ padding: '2rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
                <div className="feature-icon red"><IconUsers size={20} /></div>
                <div>
                  <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)' }}>Your workspaces</h3>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    {activeOrg ? <>Active: <strong>{activeOrg.name}</strong> — new evaluations are saved to this team.</> : 'Active: Personal — evaluations are saved only to your account.'}
                  </p>
                </div>
              </div>

              {loading && orgs.length === 0 ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '1rem' }}><span className="spinner" /></div>
              ) : orgs.length === 0 ? (
                <p style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)', marginBottom: '1.25rem' }}>You are not part of a workspace yet. Create one below or accept an invitation from your team.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.25rem' }}>
                  <WorkspaceRow
                    name="Personal" hint="Only you" isActive={!activeOrg} isSelected={false}
                    onActivate={() => setActiveOrgId(null)}
                  />
                  {orgs.map(org => (
                    <WorkspaceRow
                      key={org.id} name={org.name} role={org.role}
                      isActive={activeOrg?.id === org.id} isSelected={selected?.id === org.id}
                      onActivate={() => setActiveOrgId(org.id)} onManage={() => setSelectedId(org.id)}
                    />
                  ))}
                </div>
              )}

              <form onSubmit={createOrg} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <div style={{ flex: '1 1 240px' }}>
                  <label style={labelStyle} htmlFor="new-org-name">Create a workspace</label>
                  <input id="new-org-name" className="input" value={newName} onChange={e => setNewName(e.target.value)} placeholder="e.g. Riverside Patient Advocates" minLength={2} maxLength={80} required />
                </div>
                <button type="submit" className="btn btn-red" disabled={creating || newName.trim().length < 2}>
                  {creating ? <><span className="spinner" /> Creating...</> : <><IconPlus size={16} /> Create</>}
                </button>
              </form>
              {createStatus && <div style={{ marginTop: '1rem' }}><Status status={createStatus} /></div>}
            </motion.div>

            {selected && (
              <WorkspaceManager
                key={selected.id}
                org={selected}
                isActive={activeOrg?.id === selected.id}
                onChanged={refresh}
                onGone={async () => { if (activeOrg?.id === selected.id) setActiveOrgId(null); setSelectedId(null); await refresh() }}
              />
            )}
          </div>
        )}
      </div>
    </section>
  )
}

function WorkspaceRow({ name, hint, role, isActive, isSelected, onActivate, onManage }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap',
      padding: '0.75rem 1rem', borderRadius: '0.75rem',
      border: `1px solid ${isSelected ? 'var(--accent-border)' : 'var(--border-secondary)'}`,
      background: isSelected ? 'var(--accent-subtle)' : 'var(--bg-secondary)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', minWidth: 0 }}>
        <strong style={{ fontSize: '0.9375rem', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</strong>
        {role ? <RoleBadge role={role} /> : <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{hint}</span>}
        {isActive && <span className="badge badge-success" style={{ fontSize: '0.625rem' }}>Active</span>}
      </div>
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        {!isActive && (
          <button type="button" className="btn btn-outline" style={{ padding: '0.375rem 0.75rem', fontSize: '0.75rem' }} onClick={onActivate}>Use this</button>
        )}
        {onManage && (
          <button type="button" className="btn btn-ghost" style={{ padding: '0.375rem 0.75rem', fontSize: '0.75rem' }} onClick={onManage} aria-pressed={isSelected}>
            <IconSettings size={14} /> Manage
          </button>
        )}
      </div>
    </div>
  )
}

function WorkspaceManager({ org, isActive, onChanged, onGone }) {
  const myRole = org.role
  const isAdmin = roleAtLeast(myRole, 'admin')
  const isOwner = myRole === 'owner'
  const roles = grantableRoles(myRole)

  const [members, setMembers] = useState([])
  const [invitations, setInvitations] = useState([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState(null)
  const [inviteForm, setInviteForm] = useState({ email: '', role: roles.includes('member') ? 'member' : roles[0] || 'viewer' })
  const [inviting, setInviting] = useState(false)
  const [inviteStatus, setInviteStatus] = useState(null)
  const [pendingLink, setPendingLink] = useState(null)
  const [renameValue, setRenameValue] = useState(org.name)
  const [renaming, setRenaming] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const m = await call(`/orgs/${org.id}/members`, undefined, 'Could not load members.')
      setMembers(Array.isArray(m) ? m : [])
      if (isAdmin) {
        const inv = await call(`/orgs/${org.id}/invitations`, undefined, 'Could not load invitations.')
        setInvitations(Array.isArray(inv) ? inv : [])
      }
    } catch (err) {
      setStatus({ type: 'error', message: err.message })
    } finally {
      setLoading(false)
    }
  }, [org.id, isAdmin])

  useEffect(() => { load() }, [load])

  const flash = (type, message) => {
    setStatus({ type, message })
    if (type === 'success') setTimeout(() => setStatus(null), 4000)
  }

  const changeRole = async (member, role) => {
    try {
      await call(`/orgs/${org.id}/members/${member.user_id}`, { method: 'PATCH', body: JSON.stringify({ role }) }, 'Could not change the role.')
      flash('success', `${member.email || 'Member'} is now ${ROLE_LABEL[role]}.`)
      await load()
    } catch (err) {
      flash('error', err.message)
    }
  }

  const removeMember = async (member) => {
    const leaving = member.is_you
    const ok = window.confirm(leaving ? `Leave "${org.name}"? You will lose access to its claims.` : `Remove ${member.email || 'this member'} from "${org.name}"?`)
    if (!ok) return
    try {
      await call(`/orgs/${org.id}/members/${member.user_id}`, { method: 'DELETE' }, 'Could not remove the member.')
      if (leaving) { await onGone(); return }
      flash('success', `${member.email || 'Member'} removed.`)
      await load()
      await onChanged()
    } catch (err) {
      flash('error', err.message)
    }
  }

  const invite = async (e) => {
    e.preventDefault()
    setInviting(true)
    setInviteStatus(null)
    setPendingLink(null)
    try {
      const inv = await call(`/orgs/${org.id}/invitations`, { method: 'POST', body: JSON.stringify(inviteForm) }, 'Could not send the invitation.')
      setInviteForm(f => ({ ...f, email: '' }))
      if (inv.email_sent) {
        setInviteStatus({ type: 'success', message: `Invitation emailed to ${inv.email}. It expires ${inv.expires_at ? new Date(inv.expires_at).toLocaleDateString() : 'in 7 days'}.` })
      } else {
        setInviteStatus({ type: 'success', message: `Invitation created for ${inv.email}. Email is not configured on this server, so share the link below with them directly — it works once and only for that address.` })
        setPendingLink(inv.accept_url)
      }
      await load()
    } catch (err) {
      setInviteStatus({ type: 'error', message: err.message })
    } finally {
      setInviting(false)
    }
  }

  const revoke = async (inv) => {
    try {
      await call(`/orgs/${org.id}/invitations/${inv.id}`, { method: 'DELETE' }, 'Could not revoke the invitation.')
      flash('success', `Invitation to ${inv.email} revoked.`)
      await load()
    } catch (err) {
      flash('error', err.message)
    }
  }

  const rename = async (e) => {
    e.preventDefault()
    setRenaming(true)
    try {
      await call(`/orgs/${org.id}`, { method: 'PATCH', body: JSON.stringify({ name: renameValue }) }, 'Could not rename the workspace.')
      flash('success', 'Workspace renamed.')
      await onChanged()
    } catch (err) {
      flash('error', err.message)
    } finally {
      setRenaming(false)
    }
  }

  const destroy = async () => {
    const typed = window.prompt(`Delete "${org.name}" for everyone? Members lose access; saved claims stay with their authors.\n\nType the workspace name to confirm:`)
    if (typed !== org.name) return
    try {
      await call(`/orgs/${org.id}`, { method: 'DELETE' }, 'Could not delete the workspace.')
      await onGone()
    } catch (err) {
      flash('error', err.message)
    }
  }

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(pendingLink)
      setInviteStatus({ type: 'success', message: 'Invitation link copied.' })
    } catch {
      setInviteStatus({ type: 'error', message: 'Copy failed — select the link and copy it manually.' })
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="card" style={{ padding: '2rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div className="feature-icon" style={{ background: '#f3f4f6', color: '#4b5563' }}><IconSettings size={20} /></div>
          <div>
            <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)' }}>{org.name}</h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              You are <RoleBadge role={myRole} />{isActive ? ' · active workspace' : ''}
            </p>
          </div>
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{members.length} member{members.length === 1 ? '' : 's'}</span>
      </div>

      {status && <div style={{ marginBottom: '1rem' }}><Status status={status} /></div>}

      {/* ── Members ─────────────────────────────────────────────── */}
      <h4 style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.75rem' }}>Members</h4>
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '1rem' }}><span className="spinner" /></div>
      ) : (
        <div style={{ overflowX: 'auto', marginBottom: '1.75rem' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
                <th style={{ padding: '0.5rem 0.5rem 0.5rem 0', fontWeight: 600 }}>Email</th>
                <th style={{ padding: '0.5rem', fontWeight: 600 }}>Role</th>
                <th style={{ padding: '0.5rem', fontWeight: 600 }}>Joined</th>
                <th style={{ padding: '0.5rem 0 0.5rem 0.5rem', fontWeight: 600, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {members.map(m => {
                const manageable = canManageMember(myRole, m.role) && !m.is_you
                return (
                  <tr key={m.user_id} style={{ borderTop: '1px solid var(--border-secondary)' }}>
                    <td style={{ padding: '0.625rem 0.5rem 0.625rem 0', color: 'var(--text-primary)', wordBreak: 'break-all' }}>
                      {m.email || <span style={{ color: 'var(--text-tertiary)' }}>unknown</span>}
                      {m.is_you && <span className="badge badge-zinc" style={{ marginLeft: '0.5rem', fontSize: '0.625rem' }}>you</span>}
                    </td>
                    <td style={{ padding: '0.625rem 0.5rem' }}>
                      {manageable && roles.length ? (
                        <select className="input" aria-label={`Role for ${m.email || 'member'}`} value={m.role} onChange={e => changeRole(m, e.target.value)} style={{ padding: '0.375rem 0.5rem', fontSize: '0.8125rem', width: 'auto' }}>
                          {!roles.includes(m.role) && <option value={m.role}>{ROLE_LABEL[m.role]}</option>}
                          {roles.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                        </select>
                      ) : <RoleBadge role={m.role} />}
                    </td>
                    <td style={{ padding: '0.625rem 0.5rem', color: 'var(--text-tertiary)', whiteSpace: 'nowrap' }}>{m.created_at ? new Date(m.created_at).toLocaleDateString() : '—'}</td>
                    <td style={{ padding: '0.625rem 0 0.625rem 0.5rem', textAlign: 'right' }}>
                      {manageable && (
                        <button type="button" className="btn btn-ghost" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: 'var(--danger)' }} onClick={() => removeMember(m)} aria-label={`Remove ${m.email || 'member'}`}>
                          <IconTrash size={14} /> Remove
                        </button>
                      )}
                      {m.is_you && !isOwner && (
                        <button type="button" className="btn btn-ghost" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }} onClick={() => removeMember(m)}>Leave</button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Invitations (admins) ────────────────────────────────── */}
      {isAdmin && (
        <>
          <h4 style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.75rem' }}>Invite someone</h4>
          <form onSubmit={invite} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: '0.75rem' }}>
            <div style={{ flex: '2 1 240px' }}>
              <label style={labelStyle} htmlFor={`invite-email-${org.id}`}>Email address</label>
              <input id={`invite-email-${org.id}`} type="email" className="input" value={inviteForm.email} onChange={e => setInviteForm({ ...inviteForm, email: e.target.value })} placeholder="colleague@yourfirm.com" required />
            </div>
            <div style={{ flex: '1 1 140px' }}>
              <label style={labelStyle} htmlFor={`invite-role-${org.id}`}>Role</label>
              <select id={`invite-role-${org.id}`} className="input" value={inviteForm.role} onChange={e => setInviteForm({ ...inviteForm, role: e.target.value })}>
                {roles.map(r => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
              </select>
            </div>
            <button type="submit" className="btn btn-red" disabled={inviting}>
              {inviting ? <><span className="spinner" /> Sending...</> : <><IconMail size={16} /> Send invitation</>}
            </button>
          </form>
          {ROLE_HELP[inviteForm.role] && <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '1rem' }}>{ROLE_LABEL[inviteForm.role]}: {ROLE_HELP[inviteForm.role]}</p>}
          {inviteStatus && <div style={{ marginBottom: '0.75rem' }}><Status status={inviteStatus} /></div>}
          {pendingLink && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
              <input className="input" readOnly value={pendingLink} onFocus={e => e.target.select()} style={{ flex: '1 1 280px', fontSize: '0.75rem' }} aria-label="Invitation link" />
              <button type="button" className="btn btn-outline" onClick={copyLink} style={{ padding: '0.5rem 0.875rem', fontSize: '0.8125rem' }}><IconCopy size={14} /> Copy link</button>
            </div>
          )}

          {invitations.length > 0 && (
            <div style={{ marginBottom: '1.75rem' }}>
              <h4 style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.75rem' }}>Pending invitations</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {invitations.map(inv => (
                  <div key={inv.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap', padding: '0.625rem 0.875rem', borderRadius: '0.625rem', border: '1px solid var(--border-secondary)', fontSize: '0.8125rem' }}>
                    <span style={{ color: 'var(--text-primary)', wordBreak: 'break-all' }}>
                      {inv.email} <RoleBadge role={inv.role} />
                      <span style={{ color: 'var(--text-tertiary)', marginLeft: '0.5rem' }}>expires {inv.expires_at ? new Date(inv.expires_at).toLocaleDateString() : 'soon'}</span>
                    </span>
                    <button type="button" className="btn btn-ghost" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: 'var(--danger)' }} onClick={() => revoke(inv)}>Revoke</button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Settings ────────────────────────────────────────── */}
          <h4 style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.75rem' }}>Settings</h4>
          <form onSubmit={rename} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: isOwner ? '1.75rem' : 0 }}>
            <div style={{ flex: '1 1 240px' }}>
              <label style={labelStyle} htmlFor={`rename-${org.id}`}>Workspace name</label>
              <input id={`rename-${org.id}`} className="input" value={renameValue} onChange={e => setRenameValue(e.target.value)} minLength={2} maxLength={80} required />
            </div>
            <button type="submit" className="btn btn-outline" disabled={renaming || renameValue.trim() === org.name || renameValue.trim().length < 2}>
              {renaming ? <><span className="spinner" /> Saving...</> : 'Rename'}
            </button>
          </form>
        </>
      )}

      {isOwner && (
        <div style={{ padding: '1rem 1.25rem', borderRadius: '0.75rem', border: '1px solid var(--danger-border)', background: 'var(--danger-bg)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div>
            <strong style={{ fontSize: '0.875rem', color: 'var(--danger)' }}>Delete workspace</strong>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: 0 }}>Removes every member and pending invitation. Saved claims stay with the people who created them.</p>
          </div>
          <button type="button" className="btn btn-outline" style={{ color: 'var(--danger)', borderColor: 'var(--danger-border)' }} onClick={destroy}><IconTrash size={14} /> Delete</button>
        </div>
      )}
    </motion.div>
  )
}
