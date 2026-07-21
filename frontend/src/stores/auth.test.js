import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from './auth.js'

vi.mock('../api/auth.js', () => ({
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}))

import * as authApi from '../api/auth.js'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('auth store', () => {
  it('fetchCurrentUser sets user + checked on success', async () => {
    authApi.getCurrentUser.mockResolvedValue({ user_id: 'u1', email: 'a@example.com', storage_used_bytes: 0, storage_quota_bytes: 100 })
    const auth = useAuthStore()
    await auth.fetchCurrentUser()
    expect(auth.user.email).toBe('a@example.com')
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.checked).toBe(true)
  })

  it('fetchCurrentUser clears user on failure but still marks checked', async () => {
    authApi.getCurrentUser.mockRejectedValue(new Error('401'))
    const auth = useAuthStore()
    await auth.fetchCurrentUser()
    expect(auth.user).toBe(null)
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.checked).toBe(true)
  })

  it('logout clears the user', async () => {
    authApi.logout.mockResolvedValue(null)
    const auth = useAuthStore()
    auth.user = { email: 'a@example.com' }
    await auth.logout()
    expect(auth.user).toBe(null)
  })
})
