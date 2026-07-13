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
