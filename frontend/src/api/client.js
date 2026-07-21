export const API_BASE = '/api'

// Shared fetch wrapper: same-origin cookies (session auth), JSON error parsing.
export async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, { credentials: 'same-origin', ...options })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const j = await res.json(); msg = j.detail || j.message || msg } catch (_) { /* non-JSON body */ }
    const err = new Error(msg)
    err.status = res.status
    throw err
  }
  if (res.status === 204) return null
  return res.json()
}

export function jsonBody(method, body) {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}
