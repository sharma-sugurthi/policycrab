import { useEffect, useState } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useOrg } from '../contexts/OrgContext'
import { apiFetch, formatApiError, readApiResponse } from '../lib/api'
import { ROLE_HELP, ROLE_LABEL, stashPendingInvite } from '../lib/orgs'
import { IconAlertTriangle, IconCheckCircle, IconUsers } from '../components/Icons'

const STATUS_COPY = {
  expired: 'This invitation has expired. Ask your workspace administrator to send a new one.',
  revoked: 'This invitation was revoked by a workspace administrator.',
  accepted: 'This invitation has already been used.',
  invalid: 'This invitation link is not valid. Check that you copied the whole link from the email.',
}

export default function AcceptInvitePage() {
  const { user, loading: authLoading } = useAuth()
  const { refresh, setActiveOrgId } = useOrg()
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const navigate = useNavigate()

  const [preview, setPreview] = useState(null)
  const [loadingPreview, setLoadingPreview] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!user || !token) return
    let cancelled = false
    ;(async () => {
      setLoadingPreview(true)
      setError('')
      try {
        const res = await apiFetch(`/orgs/invitations/preview?token=${encodeURIComponent(token)}`)
        const data = await readApiResponse(res)
        if (cancelled) return
        if (!res.ok) {
          setError(res.status === 404 && String(data?.detail || '').includes('not enabled')
            ? 'Team workspaces are not enabled on this deployment.'
            : formatApiError(data, 'Could not load this invitation.'))
          return
        }
        setPreview(data)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load this invitation.')
      } finally {
        if (!cancelled) setLoadingPreview(false)
      }
    })()
    return () => { cancelled = true }
  }, [user, token])

  if (authLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}><span className="spinner" /></div>
  }
  if (!user) {
    // Remember the token; App resumes this page right after sign-in.
    stashPendingInvite(token)
    return <Navigate to="/auth" replace />
  }

  const accept = async () => {
    setBusy(true)
    setError('')
    try {
      const res = await apiFetch('/orgs/invitations/accept', { method: 'POST', body: JSON.stringify({ token }) })
      const data = await readApiResponse(res)
      if (!res.ok) {
        setError(formatApiError(data, 'Could not accept this invitation.'))
        return
      }
      await refresh()
      setActiveOrgId(data.id)
      navigate('/orgs', { replace: true })
    } catch (err) {
      setError(err.message || 'Could not accept this invitation.')
    } finally {
      setBusy(false)
    }
  }

  const invitedEmail = (preview?.email || '').toLowerCase()
  const signedInEmail = (user.email || '').toLowerCase()
  const emailMismatch = Boolean(invitedEmail) && invitedEmail !== signedInEmail

  return (
    <section className="section-white section-pad">
      <div className="main" style={{ maxWidth: '560px', margin: '0 auto' }}>
        <div className="card" style={{ padding: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
            <div className="feature-icon red"><IconUsers size={20} /></div>
            <div>
              <h1 style={{ fontWeight: 800, fontSize: '1.25rem', color: 'var(--text-primary)', margin: 0 }}>Workspace invitation</h1>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', margin: 0 }}>Signed in as {user.email}</p>
            </div>
          </div>

          {!token && <Notice type="error">This invitation link is incomplete. Open the link from your email again.</Notice>}
          {token && loadingPreview && !error && <div style={{ display: 'flex', justifyContent: 'center', padding: '1.5rem' }}><span className="spinner" /></div>}
          {error && <Notice type="error">{error}</Notice>}

          {preview && !loadingPreview && preview.status !== 'valid' && (
            <Notice type="error">{STATUS_COPY[preview.status] || STATUS_COPY.invalid}</Notice>
          )}

          {preview && !loadingPreview && preview.status === 'valid' && (
            <>
              <p style={{ fontSize: '0.9375rem', color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: '1rem' }}>
                {preview.invited_by_email ? <><strong>{preview.invited_by_email}</strong> invited you to join </> : 'You have been invited to join '}
                <strong>{preview.org_name || 'a team workspace'}</strong> as a{' '}
                <span className="badge badge-info">{ROLE_LABEL[preview.role] || preview.role}</span>.
              </p>
              {ROLE_HELP[preview.role] && (
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>{ROLE_HELP[preview.role]}</p>
              )}
              <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '1.25rem' }}>
                Sent to {preview.email}{preview.expires_at ? ` · expires ${new Date(preview.expires_at).toLocaleDateString()}` : ''}
              </p>

              {emailMismatch && (
                <Notice type="error">
                  This invitation was sent to <strong>{preview.email}</strong>, but you are signed in as <strong>{user.email}</strong>.
                  Sign out and sign in with the invited address to accept it.
                </Notice>
              )}

              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <button type="button" className="btn btn-red" onClick={accept} disabled={busy || emailMismatch}>
                  {busy ? <><span className="spinner" /> Joining...</> : <><IconCheckCircle size={16} /> Accept and join</>}
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => navigate('/dashboard')} disabled={busy}>Not now</button>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  )
}

function Notice({ type, children }) {
  const isError = type === 'error'
  return (
    <div role={isError ? 'alert' : 'status'} style={{
      padding: '0.75rem 1rem', borderRadius: '0.5rem', fontSize: '0.875rem', display: 'flex', alignItems: 'flex-start', gap: '0.5rem', marginBottom: '1rem',
      background: isError ? 'var(--danger-bg)' : 'var(--success-bg)', color: isError ? 'var(--danger)' : 'var(--success)',
      border: `1px solid ${isError ? '#fecaca' : '#a7f3d0'}`, lineHeight: 1.5,
    }}>
      {isError ? <IconAlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} /> : <IconCheckCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />}
      <span>{children}</span>
    </div>
  )
}
