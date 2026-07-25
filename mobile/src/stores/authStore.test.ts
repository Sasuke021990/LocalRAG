import { useAuthStore } from './authStore'

jest.mock('../api/auth', () => ({
  login: jest.fn(),
  signup: jest.fn(),
  getCurrentUser: jest.fn(),
  googleTokenExchange: jest.fn(),
  deleteAccount: jest.fn(),
  logout: jest.fn(),
}))
jest.mock('../api/client', () => ({
  setToken: jest.fn(),
  clearToken: jest.fn(),
  getToken: jest.fn(),
}))

import * as authApi from '../api/auth'
import { setToken, clearToken, getToken } from '../api/client'

const USER = { user_id: 'u1', username: 'alice', email: 'a@example.com', storage_used_bytes: 0, storage_quota_bytes: 100, is_admin: false, session_token: 'jwt-123' }

beforeEach(() => {
  jest.clearAllMocks()
  useAuthStore.setState({ user: null, checked: false })
})

test('login stores user + persists the token', async () => {
  ;(authApi.login as jest.Mock).mockResolvedValue(USER)
  await useAuthStore.getState().login('a@example.com', 'pw')
  expect(useAuthStore.getState().user?.email).toBe('a@example.com')
  expect(setToken).toHaveBeenCalledWith('jwt-123')
})

test('signup passes username, email, password and persists the token', async () => {
  ;(authApi.signup as jest.Mock).mockResolvedValue(USER)
  await useAuthStore.getState().signup('alice', 'a@example.com', 'pw')
  expect(authApi.signup).toHaveBeenCalledWith('alice', 'a@example.com', 'pw')
  expect(useAuthStore.getState().user?.username).toBe('alice')
  expect(setToken).toHaveBeenCalledWith('jwt-123')
})

test('login accepts a username as the identifier too', async () => {
  ;(authApi.login as jest.Mock).mockResolvedValue(USER)
  await useAuthStore.getState().login('alice', 'pw')
  expect(authApi.login).toHaveBeenCalledWith('alice', 'pw')
  expect(useAuthStore.getState().user?.username).toBe('alice')
})

test('logout revokes the token server-side, then clears user + local token', async () => {
  useAuthStore.setState({ user: USER as any, checked: true })
  ;(authApi.logout as jest.Mock).mockResolvedValue({ status: 'logged_out' })
  await useAuthStore.getState().logout()
  expect(authApi.logout).toHaveBeenCalled()
  expect(useAuthStore.getState().user).toBeNull()
  expect(clearToken).toHaveBeenCalled()
})

// Regression test: logout must never get stuck (or leave the user stuck
// mid-session) just because the device is offline or the token was already
// revoked -- the local logout always has to succeed.
test('logout still clears user + token even if the backend call fails', async () => {
  useAuthStore.setState({ user: USER as any, checked: true })
  ;(authApi.logout as jest.Mock).mockRejectedValue(new Error('Network request failed'))
  await useAuthStore.getState().logout()
  expect(useAuthStore.getState().user).toBeNull()
  expect(clearToken).toHaveBeenCalled()
})

test('deleteAccount calls the API with the password, then clears user + token', async () => {
  useAuthStore.setState({ user: USER as any, checked: true })
  ;(authApi.deleteAccount as jest.Mock).mockResolvedValue(undefined)
  await useAuthStore.getState().deleteAccount('correct-password')
  expect(authApi.deleteAccount).toHaveBeenCalledWith('correct-password')
  expect(useAuthStore.getState().user).toBeNull()
  expect(clearToken).toHaveBeenCalled()
})

test('deleteAccount propagates a failure (e.g. wrong password) without clearing the session', async () => {
  useAuthStore.setState({ user: USER as any, checked: true })
  ;(authApi.deleteAccount as jest.Mock).mockRejectedValue(new Error('Incorrect password'))
  await expect(useAuthStore.getState().deleteAccount('wrong')).rejects.toThrow('Incorrect password')
  expect(useAuthStore.getState().user).toEqual(USER)
  expect(clearToken).not.toHaveBeenCalled()
})

test('hydrate with no token marks checked, no user', async () => {
  ;(getToken as jest.Mock).mockResolvedValue(null)
  await useAuthStore.getState().hydrate()
  expect(useAuthStore.getState().checked).toBe(true)
  expect(useAuthStore.getState().user).toBeNull()
})

test('hydrate with a valid token restores the user', async () => {
  ;(getToken as jest.Mock).mockResolvedValue('jwt-123')
  ;(authApi.getCurrentUser as jest.Mock).mockResolvedValue(USER)
  await useAuthStore.getState().hydrate()
  expect(useAuthStore.getState().user?.email).toBe('a@example.com')
})

test('hydrate with an invalid token clears it', async () => {
  ;(getToken as jest.Mock).mockResolvedValue('bad')
  ;(authApi.getCurrentUser as jest.Mock).mockRejectedValue(new Error('401'))
  await useAuthStore.getState().hydrate()
  expect(clearToken).toHaveBeenCalled()
  expect(useAuthStore.getState().user).toBeNull()
})
