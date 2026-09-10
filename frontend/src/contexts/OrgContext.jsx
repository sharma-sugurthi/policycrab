import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useAuth } from './AuthContext'
import { apiFetch, readApiResponse } from '../lib/api'
import { getStoredActiveOrgId, pickActiveOrg, storeActiveOrgId } from '../lib/orgs'

const OrgContext = createContext({
  enabled: false, orgs: [], activeOrg: null, activeOrgId: null, loading: false, loaded: false,
  setActiveOrgId: () => {}, refresh: async () => {},
})

/**
 * Team workspaces. Loads /orgs/status once per signed-in user; when the feature
 * is disabled on the backend everything here stays empty and the UI hides it.
 * The active workspace id is kept in localStorage and sent as X-Org-Id by apiFetch.
 */
export function OrgProvider({ children }) {
  const { user } = useAuth()
  const [enabled, setEnabled] = useState(false)
  const [orgs, setOrgs] = useState([])
  const [activeOrgId, setActiveOrgIdState] = useState(() => getStoredActiveOrgId())
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)

  const refresh = useCallback(async () => {
    if (!user) {
      setEnabled(false); setOrgs([]); setLoaded(false)
      return
    }
    setLoading(true)
    try {
      const statusRes = await apiFetch('/orgs/status')
      const status = statusRes.ok ? await readApiResponse(statusRes) : null
      const on = Boolean(status?.enabled)
      setEnabled(on)
      if (!on) {
        setOrgs([]); setLoaded(true)
        return
      }
      const res = await apiFetch('/orgs')
      const data = res.ok ? await readApiResponse(res) : []
      setOrgs(Array.isArray(data) ? data : [])
      setLoaded(true)
    } catch (err) {
      console.warn('Team workspaces unavailable', err)
      setEnabled(false); setOrgs([])
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => { refresh() }, [refresh])

  const activeOrg = useMemo(() => pickActiveOrg(orgs, activeOrgId), [orgs, activeOrgId])

  // A stored workspace the user no longer belongs to (or a disabled feature) must
  // not keep an X-Org-Id header alive — the backend would reject every save.
  useEffect(() => {
    if (!loaded || !activeOrgId) return
    if (!enabled || !activeOrg) {
      storeActiveOrgId(null)
      setActiveOrgIdState(null)
    }
  }, [loaded, enabled, activeOrg, activeOrgId])

  const setActiveOrgId = useCallback((id) => {
    storeActiveOrgId(id || null)
    setActiveOrgIdState(id || null)
  }, [])

  const value = useMemo(
    () => ({ enabled, orgs, activeOrg, activeOrgId, loading, loaded, setActiveOrgId, refresh }),
    [enabled, orgs, activeOrg, activeOrgId, loading, loaded, setActiveOrgId, refresh],
  )
  return <OrgContext.Provider value={value}>{children}</OrgContext.Provider>
}

export const useOrg = () => useContext(OrgContext)
