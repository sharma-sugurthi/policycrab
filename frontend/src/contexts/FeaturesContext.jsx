import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useAuth } from './AuthContext'
import { apiFetch, readApiResponse } from '../lib/api'

const DEFAULTS = { orgs: false, api_keys: false, cases: false, usage_metering: false, audit_trail: false }
const FeaturesContext = createContext({ features: DEFAULTS, loaded: false, refresh: async () => {} })

/** Which opt-in features this deployment enables (GET /api/features), fetched once per signed-in user. */
export function FeaturesProvider({ children }) {
  const { user } = useAuth()
  const [features, setFeatures] = useState(DEFAULTS)
  const [loaded, setLoaded] = useState(false)

  const refresh = useCallback(async () => {
    if (!user) {
      setFeatures(DEFAULTS); setLoaded(false)
      return
    }
    try {
      const res = await apiFetch('/features')
      const data = res.ok ? await readApiResponse(res) : null
      setFeatures({ ...DEFAULTS, ...(data && typeof data === 'object' ? data : {}) })
    } catch (err) {
      console.warn('Feature flags unavailable', err)
      setFeatures(DEFAULTS)
    } finally {
      setLoaded(true)
    }
  }, [user])

  useEffect(() => { refresh() }, [refresh])

  const value = useMemo(() => ({ features, loaded, refresh }), [features, loaded, refresh])
  return <FeaturesContext.Provider value={value}>{children}</FeaturesContext.Provider>
}

export const useFeatures = () => useContext(FeaturesContext)
