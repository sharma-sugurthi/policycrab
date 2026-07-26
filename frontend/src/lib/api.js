import { supabase } from './supabase'

const API_BASE_URL = '/api' // Rewritten by Vercel in production, or Vite proxy locally

/**
 * Custom fetch wrapper that automatically attaches the Supabase JWT token
 * to the Authorization header if a user is logged in.
 */
export async function apiFetch(endpoint, options = {}) {
  // Get the current session to extract the access token
  const { data: { session }, error: sessionError } = await supabase.auth.getSession()

  const isFormData = options.body instanceof FormData
  const headers = {
    ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
    ...options.headers,
  }

  // If we have a valid session, attach the Bearer token
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`
  } else if (sessionError) {
    console.error('Error fetching Supabase session:', sessionError)
  }

  // Construct the full URL
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    })

    // Special handling for 401 Unauthorized
    if (response.status === 401) {
      console.warn('API returned 401 Unauthorized. User session may have expired.')
      // Optionally sign out the user locally
      // await supabase.auth.signOut()
    }

    return response
  } catch (error) {
    console.error(`API Fetch failed for ${url}:`, error)
    throw error
  }
}

export async function readApiResponse(response) {
  const contentType = response.headers.get('content-type') || ''

  if (contentType.includes('application/json')) {
    try {
      return await response.json()
    } catch (error) {
      console.warn('Failed to parse JSON response:', error)
    }
  }

  const text = await response.text().catch(() => '')
  if (!text) return null

  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}


export function formatApiError(data, fallback = 'Request failed') {
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (Array.isArray(data.errors) && data.errors.length) return data.errors.join(', ')
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail) && data.detail.length) {
    return data.detail
      .map(item => {
        const field = Array.isArray(item.loc) ? item.loc.filter(Boolean).slice(1).join('.') : ''
        return field ? `${field}: ${item.msg}` : item.msg
      })
      .filter(Boolean)
      .join(', ')
  }
  if (typeof data.message === 'string') return data.message
  return fallback
}
