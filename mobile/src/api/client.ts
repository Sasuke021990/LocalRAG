import Constants from 'expo-constants'
import * as SecureStore from 'expo-secure-store'

export const TOKEN_KEY = 'session_token'

const API_BASE: string =
  (Constants.expoConfig?.extra as any)?.apiBaseUrl || 'http://localhost:8000'

export async function getToken(): Promise<string | null> {
  try { return await SecureStore.getItemAsync(TOKEN_KEY) } catch { return null }
}
export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token)
}
export async function clearToken(): Promise<void> {
  try { await SecureStore.deleteItemAsync(TOKEN_KEY) } catch { /* noop */ }
}

export interface ApiError extends Error { status?: number }

// Fired on every 401 response, in addition to the normal throw below (so a
// caller's own try/catch — e.g. the login form's "wrong password" message —
// still works exactly as before). Registered once at app startup (App.tsx)
// rather than imported directly here, to avoid a circular import between
// this module and authStore.ts (which itself calls into api/auth.ts, which
// imports this module). Without this, an expired/revoked session token just
// left the user stuck on a broken screen with no auto-logout or re-login
// prompt anywhere (task.md's mobile launch-readiness audit, P0 #3).
let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn
}

/**
 * Fire the registered 401 handler from a call site that doesn't go through
 * ``request`` — currently the XHR-based upload, which needs raw
 * ``upload.onprogress`` events that fetch can't provide. Without this, an
 * expired session during an upload would skip the global auto-logout.
 */
export function notifyUnauthorized(): void {
  onUnauthorized?.()
}

/** Fetch wrapper: attaches the bearer token, parses JSON errors like the web client. */
export async function request<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken()
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) }
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const j = await res.json(); msg = j.detail || j.message || msg } catch { /* non-JSON */ }
    if (res.status === 401) onUnauthorized?.()
    const err: ApiError = new Error(msg)
    err.status = res.status
    throw err
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export function jsonBody(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

export { API_BASE }
