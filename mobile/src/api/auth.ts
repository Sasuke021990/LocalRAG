import { request, jsonBody } from './client'

export interface User {
  user_id: string
  email: string
  storage_used_bytes: number
  storage_quota_bytes: number
  plan: string
  is_admin: boolean
  session_token?: string
}

export const signup = (email: string, password: string) =>
  request<User>('/auth/signup', jsonBody('POST', { email, password }))

export const login = (email: string, password: string) =>
  request<User>('/auth/login', jsonBody('POST', { email, password }))

export const getCurrentUser = () => request<User>('/auth/me')

export const googleTokenExchange = (code: string) =>
  request<User>('/auth/google/token-exchange', jsonBody('POST', { code }))

export const requestPasswordReset = (email: string) =>
  request('/auth/password-reset/request', jsonBody('POST', { email }))

export const changePassword = (currentPassword: string, newPassword: string) =>
  request('/auth/change-password', jsonBody('POST', { current_password: currentPassword, new_password: newPassword }))
