jest.mock('expo-constants', () => ({ expoConfig: { extra: { apiBaseUrl: 'https://api.test' } } }))
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}))

import * as SecureStore from 'expo-secure-store'
import { request } from './client'

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
