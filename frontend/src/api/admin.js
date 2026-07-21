import { request, jsonBody } from './client.js'

export const fetchUsers = (limit = 100, offset = 0) =>
  request(`/admin/users?limit=${limit}&offset=${offset}`)
export const fetchStats = () => request('/admin/stats')
export const fetchSettings = () => request('/admin/settings')

export const setQuota = (userId, quotaBytes) =>
  request(`/admin/users/${encodeURIComponent(userId)}/quota`, jsonBody('PATCH', { quota_bytes: quotaBytes }))
export const setActive = (userId, isActive) =>
  request(`/admin/users/${encodeURIComponent(userId)}/status`, jsonBody('PATCH', { is_active: isActive }))
export const setAdmin = (userId, isAdmin) =>
  request(`/admin/users/${encodeURIComponent(userId)}/admin`, jsonBody('PATCH', { is_admin: isAdmin }))
export const deleteUser = (userId) =>
  request(`/admin/users/${encodeURIComponent(userId)}`, { method: 'DELETE' })
export const updateSetting = (name, value) =>
  request('/admin/settings', jsonBody('PATCH', { name, value }))
