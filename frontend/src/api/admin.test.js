import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchUsers, setQuota, setActive, deleteUser, updateSetting } from './admin.js'

function mockOnce(body) {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body })
}
beforeEach(() => { global.fetch = vi.fn() })
afterEach(() => { vi.restoreAllMocks() })

describe('admin api', () => {
  it('fetchUsers builds the paged URL with credentials', async () => {
    mockOnce({ users: [], total: 0 })
    await fetchUsers(50, 10)
    expect(global.fetch).toHaveBeenCalledWith('/api/admin/users?limit=50&offset=10', { credentials: 'same-origin' })
  })

  it('setQuota PATCHes quota_bytes', async () => {
    mockOnce({})
    await setQuota('u1', 5000)
    const [url, opts] = global.fetch.mock.calls[0]
    expect(url).toBe('/api/admin/users/u1/quota')
    expect(opts.method).toBe('PATCH')
    expect(opts.body).toBe(JSON.stringify({ quota_bytes: 5000 }))
  })

  it('setActive PATCHes is_active', async () => {
    mockOnce({})
    await setActive('u1', false)
    expect(global.fetch.mock.calls[0][1].body).toBe(JSON.stringify({ is_active: false }))
  })

  it('deleteUser DELETEs', async () => {
    mockOnce({})
    await deleteUser('u1')
    const [url, opts] = global.fetch.mock.calls[0]
    expect(url).toBe('/api/admin/users/u1')
    expect(opts.method).toBe('DELETE')
  })

  it('updateSetting PATCHes name/value', async () => {
    mockOnce({})
    await updateSetting('signups_enabled', false)
    expect(global.fetch.mock.calls[0][1].body).toBe(JSON.stringify({ name: 'signups_enabled', value: false }))
  })
})
