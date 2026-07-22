import { request, jsonBody } from './client.js'

export const signup = (username, email, password) =>
  request('/auth/signup', jsonBody('POST', { username, email, password }))
export const login = (email, password) => request('/auth/login', jsonBody('POST', { email, password }))
export const logout = () => request('/auth/logout', { method: 'POST' })
export const getCurrentUser = () => request('/auth/me')
export const requestPasswordReset = (email) => request('/auth/password-reset/request', jsonBody('POST', { email }))
export const confirmPasswordReset = (token, newPassword) =>
  request('/auth/password-reset/confirm', jsonBody('POST', { token, new_password: newPassword }))
export const changePassword = (currentPassword, newPassword) =>
  request('/auth/change-password', jsonBody('POST', { current_password: currentPassword, new_password: newPassword }))

// URL for the Google OAuth redirect (a full navigation, not a fetch).
export const googleLoginUrl = '/api/auth/google/login'
