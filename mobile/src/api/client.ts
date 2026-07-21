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

/** Fetch wrapper: attaches the bearer token, parses JSON errors like the web client. */
export async function request<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken()
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) }
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const j = await res.json(); msg = j.detail || j.message || msg } catch { /* non-JSON */ }
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
