export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || '/api/v1'
).replace(/\/$/, '')

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  let payload = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  if (!response.ok) {
    const error = new Error(
      payload?.error?.message ||
        `Request failed with status ${response.status}. Please try again.`,
    )
    error.code = payload?.error?.code || 'RequestFailed'
    error.details = payload?.error?.details || {}
    error.status = response.status
    throw error
  }

  return payload
}

/** POST the trip inputs and receive the full plan. */
export function planTrip(input) {
  return request('/plan/', { method: 'POST', body: JSON.stringify(input) })
}

/** Autocomplete for the three location inputs. */
export function searchPlaces(query, signal) {
  return request(`/places/?q=${encodeURIComponent(query)}`, { signal })
}

export function fetchHealth() {
  return request('/health/')
}
