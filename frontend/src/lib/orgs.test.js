import { beforeEach, describe, expect, it } from 'vitest'
import {
  canManageMember, getStoredActiveOrgId, grantableRoles, pickActiveOrg, roleAtLeast,
  stashPendingInvite, storeActiveOrgId, takePendingInvite,
} from './orgs'

const ORG_A = '11111111-1111-4111-8111-111111111111'
const ORG_B = '22222222-2222-4222-8222-222222222222'

describe('orgs helpers', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  it('mirrors the backend role ladder', () => {
    expect(roleAtLeast('owner', 'admin')).toBe(true)
    expect(roleAtLeast('member', 'admin')).toBe(false)
    expect(grantableRoles('owner')).toEqual(['admin', 'member', 'viewer'])
    expect(grantableRoles('admin')).toEqual(['member', 'viewer'])
    expect(grantableRoles('member')).toEqual([])
    expect(canManageMember('admin', 'admin')).toBe(false)
    expect(canManageMember('admin', 'member')).toBe(true)
    expect(canManageMember('owner', 'owner')).toBe(false)
  })

  it('only trusts a stored workspace the user still belongs to', () => {
    storeActiveOrgId(ORG_A)
    expect(getStoredActiveOrgId()).toBe(ORG_A)
    expect(pickActiveOrg([{ id: ORG_A, name: 'A' }], ORG_A)).toEqual({ id: ORG_A, name: 'A' })
    expect(pickActiveOrg([{ id: ORG_B, name: 'B' }], ORG_A)).toBeNull()
    storeActiveOrgId(null)
    expect(getStoredActiveOrgId()).toBeNull()
    localStorage.setItem('policycrab_active_org', 'not-a-uuid')
    expect(getStoredActiveOrgId()).toBeNull()
  })

  it('hands a pending invitation token over exactly once', () => {
    stashPendingInvite('tok_123')
    expect(takePendingInvite()).toBe('tok_123')
    expect(takePendingInvite()).toBeNull()
  })
})
