import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useOrg } from '../contexts/OrgContext'
import { apiFetch, formatApiError, readApiResponse } from '../lib/api'
import { ROLE_BADGE, ROLE_HELP, ROLE_LABEL, canManageMember, grantableRoles, roleAtLeast } from '../lib/orgs'
import {
  IconActivity, IconAlertTriangle, IconCheckCircle, IconCopy, IconLock, IconMail, IconPlus, IconSettings, IconTrash, IconUsers,
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
  const [apiKeyScopes, setApiKeyScopes] = useState(null)   // null = API keys disabled on this deployment

  useEffect(() => {
    let cancelled = false
    apiFetch('/api-keys/scopes').then(readApiResponse)
      .then(d => { if (!cancelled) setApiKeyScopes(d && d.enabled ? d.scopes : null) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

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
                apiKeyScopes={apiKeyScopes}
                isActive={activeOrg?.id === selected.id}
                onChanged={refresh}
                onGone={async () => { if (activeOrg?.id === selected.id) setActiveOrgId(null); setSelectedId(null); await refresh() }}
              />
            )}
          </div>
        )}

        {apiKeyScopes && (
          <div style={{ marginTop: '2rem' }}>
            <ApiKeysCard
              title="Personal API keys"
              subtitle="Call PolicyCrab from your own tools as yourself. Workspace keys live under each workspace above."
              endpoint="/api-keys"
              scopes={apiKeyScopes}
            />
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

function WorkspaceManager({ org, isActive, onChanged, onGone, apiKeyScopes }) {
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

      {isAdmin && apiKeyScopes && (
        <ApiKeysCard
          embedded
          title="Workspace API keys"
          subtitle="For integrations (RCM systems, case-management tools). Requests run as you, inside this workspace, limited to the scopes you grant."
          endpoint={`/orgs/${org.id}/api-keys`}
          scopes={apiKeyScopes}
        />
      )}

      {isAdmin && <WorkspaceActivity org={org} members={members} />}

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

const humanizeAction = (action) => String(action || '').split('.').join(' › ')

function WorkspaceActivity({ org, members }) {
  const [usage, setUsage] = useState(null)
  const [events, setEvents] = useState(null)
  const [loading, setLoading] = useState(true)

  const emailFor = (uid) => {
    if (!uid) return 'system'
    const match = (members || []).find(m => m.user_id === uid)
    return match?.email || `${String(uid).slice(0, 8)}…`
  }

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const [u, a] = await Promise.all([
          apiFetch(`/usage/org/${org.id}?days=30`).then(readApiResponse).catch(() => null),
          apiFetch(`/audit-log/org/${org.id}?days=30&limit=20`).then(readApiResponse).catch(() => null),
        ])
        if (cancelled) return
        setUsage(u && u.enabled ? u : null)
        setEvents(a && a.enabled ? (a.events || []) : null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [org.id])

  const nothingEnabled = !loading && usage === null && events === null
  const muted = { fontSize: '0.8125rem', color: 'var(--text-tertiary)', margin: 0 }
  const panelLabel = { fontSize: '0.6875rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.625rem' }

  return (
    <div style={{ marginBottom: '1.75rem' }}>
      <h4 style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
        <IconActivity size={14} /> Activity &amp; usage · last 30 days
      </h4>
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '1rem' }}><span className="spinner" /></div>
      ) : nothingEnabled ? (
        <p style={muted}>Usage metering and the audit trail are not enabled on this deployment (<code>USAGE_METERING_ENABLED</code>, <code>AUDIT_TRAIL_ENABLED</code>).</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
          <div className="card-zinc" style={{ padding: '1rem 1.125rem' }}>
            <p style={panelLabel}>Usage</p>
            {!usage ? (
              <p style={muted}>Metering is not enabled.</p>
            ) : usage.total === 0 ? (
              <p style={muted}>No billable actions recorded yet.</p>
            ) : (
              <>
                <p style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)', margin: '0 0 0.625rem', lineHeight: 1 }}>
                  {usage.total} <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-tertiary)' }}>actions</span>
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
                  {Object.entries(usage.by_type || {}).map(([type, count]) => (
                    <div key={type}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        <span>{humanizeAction(type)}</span><strong>{count}</strong>
                      </div>
                      <div style={{ height: '4px', background: 'var(--border-secondary)', borderRadius: '2px', overflow: 'hidden' }}>
                        <div style={{ width: `${Math.max(4, Math.round((count / usage.total) * 100))}%`, height: '100%', background: 'var(--accent)' }} />
                      </div>
                    </div>
                  ))}
                </div>
                {usage.by_user && Object.keys(usage.by_user).length > 0 && (
                  <p style={{ ...muted, marginTop: '0.625rem' }}>
                    Most active: {Object.entries(usage.by_user).slice(0, 3).map(([uid, n]) => `${emailFor(uid)} (${n})`).join(', ')}
                  </p>
                )}
              </>
            )}
          </div>

          <div className="card-zinc" style={{ padding: '1rem 1.125rem' }}>
            <p style={panelLabel}>Recent activity</p>
            {!events ? (
              <p style={muted}>The audit trail is not enabled.</p>
            ) : events.length === 0 ? (
              <p style={muted}>No recorded activity yet.</p>
            ) : (
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '260px', overflowY: 'auto' }}>
                {events.map(e => (
                  <li key={e.id} style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    <span style={{ color: 'var(--text-tertiary)' }}>{e.created_at ? new Date(e.created_at).toLocaleString() : ''}</span>
                    {' · '}<strong style={{ color: 'var(--text-primary)' }}>{emailFor(e.user_id)}</strong>{' '}
                    {humanizeAction(e.action)}
                    {e.outcome && e.outcome !== 'success' && (
                      <span className={`badge ${e.outcome === 'denied' ? 'badge-danger' : 'badge-warning'}`} style={{ marginLeft: '0.375rem', fontSize: '0.625rem' }}>{e.outcome}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const ENV_BADGE = { live: 'badge-success', test: 'badge-zinc' }
const EXPIRY_OPTIONS = [['', 'Never expires'], ['30', '30 days'], ['90', '90 days'], ['365', '1 year']]
const EMPTY_KEY_FORM = { name: '', environment: 'live', expires_in_days: '', scopes: [] }

function ApiKeysCard({ title, subtitle, endpoint, scopes, embedded = false }) {
  const scopeNames = Object.keys(scopes || {})
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_KEY_FORM)
  const [creating, setCreating] = useState(false)
  const [revealed, setRevealed] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await call(endpoint, undefined, 'Could not load API keys.')
      setKeys(Array.isArray(rows) ? rows : [])
    } catch (err) {
      setStatus({ type: 'error', message: err.message })
    } finally {
      setLoading(false)
    }
  }, [endpoint])

  useEffect(() => { load() }, [load])

  const toggleScope = (scope) => setForm(f => ({
    ...f, scopes: f.scopes.includes(scope) ? f.scopes.filter(s => s !== scope) : [...f.scopes, scope],
  }))

  const create = async (e) => {
    e.preventDefault()
    setCreating(true)
    setStatus(null)
    try {
      const body = { name: form.name, environment: form.environment, scopes: form.scopes }
      if (form.expires_in_days) body.expires_in_days = Number(form.expires_in_days)
      const res = await call(endpoint, { method: 'POST', body: JSON.stringify(body) }, 'Could not create the API key.')
      setRevealed({ key: res.key, name: res.api_key?.name })
      setForm(EMPTY_KEY_FORM)
      setShowForm(false)
      await load()
    } catch (err) {
      setStatus({ type: 'error', message: err.message })
    } finally {
      setCreating(false)
    }
  }

  const revoke = async (k) => {
    if (!window.confirm(`Revoke "${k.name}"? Anything using this key stops working immediately.`)) return
    try {
      await call(`${endpoint}/${k.id}`, { method: 'DELETE' }, 'Could not revoke the key.')
      setStatus({ type: 'success', message: `"${k.name}" revoked.` })
      await load()
    } catch (err) {
      setStatus({ type: 'error', message: err.message })
    }
  }

  const copyKey = async () => {
    try {
      await navigator.clipboard.writeText(revealed.key)
      setStatus({ type: 'success', message: 'API key copied to the clipboard.' })
    } catch {
      setStatus({ type: 'error', message: 'Copy failed — select the key and copy it manually.' })
    }
  }

  const muted = { fontSize: '0.75rem', color: 'var(--text-tertiary)' }
  const fmt = (v) => (v ? new Date(v).toLocaleDateString() : '—')

  return (
    <div className={embedded ? undefined : 'card'} style={embedded ? { marginBottom: '1.75rem' } : { padding: '2rem' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {!embedded && <div className="feature-icon" style={{ background: '#f3f4f6', color: '#4b5563' }}><IconLock size={20} /></div>}
          <div>
            {embedded
              ? <h4 style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0, display: 'flex', alignItems: 'center', gap: '0.375rem' }}><IconLock size={14} /> {title}</h4>
              : <h3 style={{ fontWeight: 800, fontSize: '1.125rem', color: 'var(--text-primary)' }}>{title}</h3>}
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', margin: embedded ? '0.25rem 0 0' : 0 }}>{subtitle}</p>
          </div>
        </div>
        {!showForm && !revealed && (
          <button type="button" className="btn btn-outline" style={{ padding: '0.375rem 0.875rem', fontSize: '0.8125rem' }} onClick={() => setShowForm(true)}>
            <IconPlus size={14} /> New key
          </button>
        )}
      </div>

      {status && <div style={{ marginBottom: '0.75rem' }}><Status status={status} /></div>}

      {revealed && (
        <div role="alert" style={{ padding: '0.875rem 1rem', borderRadius: '0.75rem', border: '1px solid var(--warning-border)', background: 'var(--warning-bg)', marginBottom: '1rem' }}>
          <p style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 0.375rem' }}>
            Copy your new key “{revealed.name}” now — it will not be shown again.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <input className="input" readOnly value={revealed.key} onFocus={e => e.target.select()} style={{ flex: '1 1 320px', fontFamily: 'monospace', fontSize: '0.75rem' }} aria-label="New API key" />
            <button type="button" className="btn btn-red" onClick={copyKey} style={{ padding: '0.5rem 0.875rem', fontSize: '0.8125rem' }}><IconCopy size={14} /> Copy</button>
            <button type="button" className="btn btn-ghost" onClick={() => setRevealed(null)} style={{ padding: '0.5rem 0.875rem', fontSize: '0.8125rem' }}>Done</button>
          </div>
          <p style={{ ...muted, marginTop: '0.5rem' }}>Send it as <code>Authorization: Bearer {'<key>'}</code>. Workspace keys need no <code>X-Org-Id</code> header.</p>
        </div>
      )}

      {showForm && (
        <form onSubmit={create} style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem', padding: '1rem', borderRadius: '0.75rem', border: '1px solid var(--border-secondary)', background: 'var(--bg-secondary)', marginBottom: '1rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
            <div>
              <label style={labelStyle} htmlFor={`key-name-${endpoint}`}>Name</label>
              <input id={`key-name-${endpoint}`} className="input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Epic RCM bridge" maxLength={80} required />
            </div>
            <div>
              <label style={labelStyle} htmlFor={`key-env-${endpoint}`}>Environment</label>
              <select id={`key-env-${endpoint}`} className="input" value={form.environment} onChange={e => setForm({ ...form, environment: e.target.value })}>
                <option value="live">Live (pc_live_…)</option>
                <option value="test">Test (pc_test_…)</option>
              </select>
            </div>
            <div>
              <label style={labelStyle} htmlFor={`key-exp-${endpoint}`}>Expires</label>
              <select id={`key-exp-${endpoint}`} className="input" value={form.expires_in_days} onChange={e => setForm({ ...form, expires_in_days: e.target.value })}>
                {EXPIRY_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
          </div>
          <div>
            <p style={labelStyle}>Scopes <span style={{ fontWeight: 400, color: 'var(--text-tertiary)' }}>— grant only what the integration needs</span></p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.375rem 1rem' }}>
              {scopeNames.map(scope => (
                <label key={scope} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-primary)', cursor: 'pointer' }}>
                  <input type="checkbox" checked={form.scopes.includes(scope)} onChange={() => toggleScope(scope)} style={{ marginTop: '3px' }} />
                  <span><code style={{ fontSize: '0.75rem' }}>{scope}</code><br /><span style={muted}>{scopes[scope]}</span></span>
                </label>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button type="submit" className="btn btn-red" disabled={creating || !form.name.trim() || form.scopes.length === 0}>
              {creating ? <><span className="spinner" /> Creating...</> : 'Create key'}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => { setShowForm(false); setForm(EMPTY_KEY_FORM) }} disabled={creating}>Cancel</button>
          </div>
        </form>
      )}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '1rem' }}><span className="spinner" /></div>
      ) : keys.length === 0 ? (
        <p style={{ ...muted, fontSize: '0.8125rem' }}>No API keys yet.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {keys.map(k => (
            <div key={k.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap', padding: '0.625rem 0.875rem', borderRadius: '0.625rem', border: '1px solid var(--border-secondary)', opacity: k.active ? 1 : 0.6 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <strong style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>{k.name}</strong>
                  <code style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{k.key_prefix}…</code>
                  <span className={`badge ${ENV_BADGE[k.environment] || 'badge-zinc'}`} style={{ fontSize: '0.625rem' }}>{k.environment}</span>
                  {!k.active && <span className="badge badge-danger" style={{ fontSize: '0.625rem' }}>{k.revoked_at ? 'revoked' : 'expired'}</span>}
                </div>
                <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                  {(k.scopes || []).map(s => <span key={s} className="badge badge-info" style={{ fontSize: '0.625rem' }}>{s}</span>)}
                </div>
                <p style={{ ...muted, marginTop: '0.25rem' }}>
                  Created {fmt(k.created_at)} · Last used {fmt(k.last_used_at)} · Expires {k.expires_at ? fmt(k.expires_at) : 'never'}{k.owner_email ? ` · by ${k.owner_email}` : ''}
                </p>
              </div>
              {k.active && (
                <button type="button" className="btn btn-ghost" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: 'var(--danger)' }} onClick={() => revoke(k)}>
                  <IconTrash size={14} /> Revoke
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
