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
      cache: 'no-store', // CRITICAL: Prevent browser/Cloudflare from caching authenticated responses
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
    // Intercept network crashes, offline servers, or refused connections
    if (
      error.name === 'TypeError' ||
      error.message?.includes('Failed to fetch') ||
      error.message?.includes('NetworkError') ||
      error.message?.includes('ECONNREFUSED')
    ) {
      throw new Error('Our servers are currently loading or warming up! Please try again in a few moments. The problem is definitely not with you, but with us.')
    }
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


export function formatApiError(data, fallback = 'An unexpected technical issue occurred. Please bear with us and try again shortly.') {
  let rawText = fallback
  if (typeof data === 'string') {
    rawText = data
  } else if (Array.isArray(data?.errors) && data.errors.length) {
    rawText = data.errors.join(', ')
  } else if (typeof data?.detail === 'string') {
    rawText = data.detail
  } else if (Array.isArray(data?.detail) && data.detail.length) {
    rawText = data.detail
      .map(item => {
        const field = Array.isArray(item.loc) ? item.loc.filter(Boolean).slice(1).join('.') : ''
        return field ? `${field}: ${item.msg}` : item.msg
      })
      .filter(Boolean)
      .join(', ')
  } else if (typeof data?.message === 'string') {
    rawText = data.message
  }

  // ── Smart Empathetic Translation Matrix ────────────────────────────────
  const lower = rawText.toLowerCase()

  // 1. Rate Limits, Quotas, and AI Provider Traffic Overload
  if (
    lower.includes('429') ||
    lower.includes('quota') ||
    lower.includes('rate limit') ||
    lower.includes('too many requests') ||
    lower.includes('resource_exhausted') ||
    lower.includes('exhausted') ||
    lower.includes('traffic')
  ) {
    return 'We are currently experiencing high AI traffic! Please give us just a moment and try again shortly.'
  }

  // 2. Timeouts, Payload restrictions, and large files
  if (
    lower.includes('timeout') ||
    lower.includes('timed out') ||
    lower.includes('too large') ||
    lower.includes('payload') ||
    lower.includes('context length') ||
    lower.includes('token limit') ||
    lower.includes('max_tokens')
  ) {
    return 'We encountered a processing timeout due to high server load or document size. Please try again later, or try uploading a smaller or compressed document!'
  }

  // 3. Server crashes, disconnections, & maintenance
  if (
    lower.includes('500') ||
    lower.includes('502') ||
    lower.includes('503') ||
    lower.includes('504') ||
    lower.includes('bad gateway') ||
    lower.includes('service unavailable') ||
    lower.includes('internal server error') ||
    lower.includes('econnrefused') ||
    lower.includes('connection refused') ||
    lower.includes('server crash') ||
    lower.includes('failed to fetch')
  ) {
    return 'Our servers are currently loading or undergoing brief maintenance. Please try again shortly! Don\'t worry - the problem is entirely with us, not with your request or data.'
  }

  return rawText || fallback
}
