/**
 * Team-workspace helpers shared by OrgContext, apiFetch and the pages.
 * Pure functions only; every storage access is wrapped so a blocked
 * localStorage never breaks the app.
 */

export const ACTIVE_ORG_KEY = 'policycrab_active_org'
export const PENDING_INVITE_KEY = 'policycrab_pending_invite'

export const ROLE_RANK = { owner: 4, admin: 3, member: 2, viewer: 1 }
export const ROLE_LABEL = { owner: 'Owner', admin: 'Admin', member: 'Member', viewer: 'Viewer' }
export const ROLE_BADGE = { owner: 'badge-purple', admin: 'badge-info', member: 'badge-success', viewer: 'badge-zinc' }
export const ROLE_HELP = {
  admin: 'Invites and removes members, changes roles, renames the workspace.',
  member: 'Runs evaluations inside the workspace and sees team claims.',
  viewer: 'Read-only access to workspace claims.',
}

export function roleAtLeast(role, minimum) {
  return (ROLE_RANK[role] || 0) >= (ROLE_RANK[minimum] || 0)
}

/** Roles an actor may hand out when inviting or changing someone's role. */
export function grantableRoles(actorRole) {
  if (actorRole === 'owner') return ['admin', 'member', 'viewer']
  if (actorRole === 'admin') return ['member', 'viewer']
  return []
}

/** Whether actor may change or remove a member holding targetRole. */
export function canManageMember(actorRole, targetRole) {
  if (targetRole === 'owner') return false
  if (actorRole === 'owner') return true
  if (actorRole === 'admin') return targetRole === 'member' || targetRole === 'viewer'
  return false
}

export function isUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(value || ''))
}

export function getStoredActiveOrgId() {
  try {
    const v = localStorage.getItem(ACTIVE_ORG_KEY)
    return isUuid(v) ? v : null
  } catch {
    return null
  }
}

export function storeActiveOrgId(id) {
  try {
    if (id) localStorage.setItem(ACTIVE_ORG_KEY, id)
    else localStorage.removeItem(ACTIVE_ORG_KEY)
  } catch {
    // storage blocked (private mode, disabled site data) — the header simply isn't sent
  }
}

/** The stored workspace only counts if the user is still a member of it. */
export function pickActiveOrg(orgs, storedId) {
  if (!storedId || !Array.isArray(orgs)) return null
  return orgs.find(o => o.id === storedId) || null
}

export function stashPendingInvite(token) {
  try {
    if (token) sessionStorage.setItem(PENDING_INVITE_KEY, token)
  } catch {
    // storage blocked — the user can reopen the invitation link after signing in
  }
}

export function takePendingInvite() {
  try {
    const token = sessionStorage.getItem(PENDING_INVITE_KEY)
    if (token) sessionStorage.removeItem(PENDING_INVITE_KEY)
    return token || null
  } catch {
    return null
  }
}
