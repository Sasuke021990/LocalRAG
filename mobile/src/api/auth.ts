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

export const googleTokenExchange = (code: string) =>
  request<User>('/auth/google/token-exchange', jsonBody('POST', { code }))

export const requestPasswordReset = (email: string) =>
  request('/auth/password-reset/request', jsonBody('POST', { email }))

export const changePassword = (currentPassword: string, newPassword: string) =>
  request('/auth/change-password', jsonBody('POST', { current_password: currentPassword, new_password: newPassword }))
