import { request, jsonBody } from './client'

export interface AdminUser {
  user_id: string
  username: string
  email: string
  created_at: string
  storage_used_bytes: number
  storage_quota_bytes: number
  is_admin: boolean
  is_active: boolean
  document_count: number
}

export interface AdminStats {
  total_users: number
  active_users: number
  admin_users: number
  total_storage_used_bytes: number
  total_documents: number
  total_webhooks: number
  total_tokens: number
}

export interface AdminSettings {
  signups_enabled: boolean
  default_storage_quota_bytes: number
}

export const fetchUsers = (limit = 100, offset = 0) =>
  request<{ users: AdminUser[]; total: number }>(`/admin/users?limit=${limit}&offset=${offset}`)
export const fetchStats = () => request<AdminStats>('/admin/stats')
export const fetchSettings = () => request<{ settings: AdminSettings }>('/admin/settings')

export const setQuota = (userId: string, quotaBytes: number) =>
  request<AdminUser>(`/admin/users/${encodeURIComponent(userId)}/quota`, jsonBody('PATCH', { quota_bytes: quotaBytes }))
export const setActive = (userId: string, isActive: boolean) =>
  request<AdminUser>(`/admin/users/${encodeURIComponent(userId)}/status`, jsonBody('PATCH', { is_active: isActive }))
export const setAdmin = (userId: string, isAdmin: boolean) =>
  request<AdminUser>(`/admin/users/${encodeURIComponent(userId)}/admin`, jsonBody('PATCH', { is_admin: isAdmin }))
export const deleteUser = (userId: string) =>
  request(`/admin/users/${encodeURIComponent(userId)}`, { method: 'DELETE' })
export const updateSetting = (name: string, value: unknown) =>
  request('/admin/settings', jsonBody('PATCH', { name, value }))
