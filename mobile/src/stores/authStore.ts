import { create } from 'zustand'
import * as authApi from '../api/auth'
import type { User } from '../api/auth'
import { setToken, clearToken, getToken } from '../api/client'
import { useUsageStore } from './usageStore'

interface AuthState {
  user: User | null
  checked: boolean
  hydrate: () => Promise<void>
  refresh: () => Promise<void>
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  loginWithGoogleCode: (code: string) => Promise<void>
  logout: () => Promise<void>
}

async function persist(user: User) {
  if (user.session_token) await setToken(user.session_token)
  useUsageStore.getState().syncFromUser(user)
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  checked: false,

  hydrate: async () => {
    const token = await getToken()
    if (!token) { set({ user: null, checked: true }); return }
    try {
      const user = await authApi.getCurrentUser()
      useUsageStore.getState().syncFromUser(user)
      set({ user, checked: true })
    } catch {
      await clearToken()
      set({ user: null, checked: true })
    }
  },

  refresh: async () => {
    // Re-pull /auth/me and re-sync usage (plan + quota) after a change like
    // a billing plan switch. Keeps the stored token as-is.
    const user = await authApi.getCurrentUser()
    useUsageStore.getState().syncFromUser(user)
    set({ user })
  },

  login: async (email, password) => {
    const user = await authApi.login(email, password)
    await persist(user)
    set({ user, checked: true })
  },

  signup: async (email, password) => {
    const user = await authApi.signup(email, password)
    await persist(user)
    set({ user, checked: true })
  },

  loginWithGoogleCode: async (code) => {
    const user = await authApi.googleTokenExchange(code)
    await persist(user)
    set({ user, checked: true })
  },

  logout: async () => {
    await clearToken()
    set({ user: null })
  },
}))
