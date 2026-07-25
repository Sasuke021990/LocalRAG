import { request, jsonBody } from './client'

export interface User {
  user_id: string
  username: string
  email: string
  storage_used_bytes: number
  storage_quota_bytes: number
  plan: string
  is_admin: boolean
  idle_timeout_seconds?: number
  session_token?: string
}

export const signup = (username: string, email: string, password: string) =>
  request<User>('/auth/signup', jsonBody('POST', { username, email, password }))

// `identifier` accepts either an email address or a username — the backend
// tries email first, then falls back to username (auth.store.get_user_by_identifier).
export const login = (identifier: string, password: string) =>
  request<User>('/auth/login', jsonBody('POST', { email: identifier, password }))

export const getCurrentUser = () => request<User>('/auth/me')

// Revokes the presented token server-side via a jti blacklist (see
// backend/auth/session_blacklist.py) -- without this call, a "logged out"
// mobile token stayed valid until its natural expiry, unlike web (which
// already calls this same endpoint on logout).
export const logout = () => request('/auth/logout', { method: 'POST' })

export const googleTokenExchange = (code: string) =>
  request<User>('/auth/google/token-exchange', jsonBody('POST', { code }))

export const requestPasswordReset = (email: string) =>
  request('/auth/password-reset/request', jsonBody('POST', { email }))

// Returns a fresh session_token: this request itself invalidates the
// client's current token (the backend bumps token_version), so the caller
// must persist the returned one immediately or every subsequent request
// will 401.
export const changePassword = (currentPassword: string, newPassword: string) =>
  request<{ status: string; session_token: string }>(
    '/auth/change-password', jsonBody('POST', { current_password: currentPassword, new_password: newPassword }),
  )

// Permanently deletes the signed-in user's account and everything they own
// (documents, pools, conversations, tokens, webhooks) -- cannot be undone.
// `password` re-confirms identity even though the session is already
// authenticated; blank is only valid for a Google-only account (no
// password set), which isn't reachable on mobile today since Google
// Sign-In is hidden here (see LoginScreen.tsx).
export const deleteAccount = (password: string) =>
  request('/auth/me', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) })
