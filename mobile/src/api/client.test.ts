jest.mock('expo-constants', () => ({ expoConfig: { extra: { apiBaseUrl: 'https://api.test' } } }))
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}))

import * as SecureStore from 'expo-secure-store'
import { request, setUnauthorizedHandler } from './client'

function mockFetchOnce(status: number, body: any) {
  ;(global as any).fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
}

beforeEach(() => { jest.clearAllMocks() })

test('attaches Authorization when a token is stored', async () => {
  ;(SecureStore.getItemAsync as jest.Mock).mockResolvedValue('jwt-123')
  mockFetchOnce(200, { ok: true })
  await request('/pools')
  const [url, opts] = (global as any).fetch.mock.calls[0]
  expect(url).toBe('https://api.test/pools')
  expect(opts.headers.Authorization).toBe('Bearer jwt-123')
})

test('omits Authorization when no token', async () => {
  ;(SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null)
  mockFetchOnce(200, {})
  await request('/pools')
  const [, opts] = (global as any).fetch.mock.calls[0]
  expect(opts.headers.Authorization).toBeUndefined()
})

test('throws the server detail on non-2xx', async () => {
  ;(SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null)
  mockFetchOnce(404, { detail: 'Not found' })
  await expect(request('/x')).rejects.toThrow('Not found')
})

// Regression test: an expired/revoked session token used to leave the user
// stuck on a broken screen with no auto-logout anywhere in the app.
test('a 401 fires the registered unauthorized handler in addition to throwing', async () => {
  const handler = jest.fn()
  setUnauthorizedHandler(handler)
  ;(SecureStore.getItemAsync as jest.Mock).mockResolvedValue('stale-token')
  mockFetchOnce(401, { detail: 'Session revoked' })
  await expect(request('/documents')).rejects.toThrow('Session revoked')
  expect(handler).toHaveBeenCalledTimes(1)
  setUnauthorizedHandler(() => {}) // reset so later test files aren't affected
})

test('a non-401 error does not fire the unauthorized handler', async () => {
  const handler = jest.fn()
  setUnauthorizedHandler(handler)
  ;(SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null)
  mockFetchOnce(500, { detail: 'Internal error' })
  await expect(request('/x')).rejects.toThrow('Internal error')
  expect(handler).not.toHaveBeenCalled()
  setUnauthorizedHandler(() => {})
})
