import { create } from 'zustand'
import * as authApi from '../api/auth'
import type { User } from '../api/auth'
import { setToken, clearToken, getToken } from '../api/client'
import { registerForPush, unregisterFromPush } from '../utils/push'
import { useUsageStore } from './usageStore'

interface AuthState {
  user: User | null
  checked: boolean
  // This device's Expo push token, once registered against the session.
  // Null in Expo Go, on a simulator, or when permission was declined — see
  // utils/push.ts. Kept here so logout can detach it from the account.
  pushToken: string | null
  hydrate: () => Promise<void>
  refresh: () => Promise<void>
  login: (identifier: string, password: string) => Promise<void>
  signup: (username: string, email: string, password: string) => Promise<void>
  loginWithGoogleCode: (code: string) => Promise<void>
  logout: () => Promise<void>
  deleteAccount: (password: string) => Promise<void>
}

async function persist(user: User) {
  if (user.session_token) await setToken(user.session_token)
  useUsageStore.getState().syncFromUser(user)
}

// Deliberately not awaited by callers: registration involves a permission
// prompt and a network round trip, and blocking the post-login transition on
// either would leave the user staring at a spinner behind a system dialog.
// Best-effort by design — registerForPush never throws.
function startPushRegistration(set: (partial: Partial<AuthState>) => void) {
  registerForPush().then((token) => {
    if (token) set({ pushToken: token })
  })
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  checked: false,
  pushToken: null,

  hydrate: async () => {
    const token = await getToken()
    if (!token) { set({ user: null, checked: true }); return }
    try {
      const user = await authApi.getCurrentUser()
      useUsageStore.getState().syncFromUser(user)
      set({ user, checked: true })
      // Re-register on every launch of a restored session: Expo can rotate
      // a device token, and the backend treats re-registration as idempotent.
      startPushRegistration(set)
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

  login: async (identifier, password) => {
    const user = await authApi.login(identifier, password)
    await persist(user)
    set({ user, checked: true })
    startPushRegistration(set)
  },

  signup: async (username, email, password) => {
    const user = await authApi.signup(username, email, password)
    await persist(user)
    set({ user, checked: true })
    startPushRegistration(set)
  },

  loginWithGoogleCode: async (code) => {
    const user = await authApi.googleTokenExchange(code)
    await persist(user)
    set({ user, checked: true })
    startPushRegistration(set)
  },

  logout: async () => {
    // Best-effort: revoke the token server-side (see api/auth.ts::logout)
    // while it's still available to identify. Must never block the local
    // logout on network failure -- the user can always log out locally
    // regardless of connectivity, same as the backend's own "logging out
    // when already logged out is a safe no-op" behavior.
    // Detach this device first, while the session token is still valid to
    // authenticate the call — otherwise the next person to sign in here
    // would keep receiving the outgoing user's notifications.
    await unregisterFromPush(get().pushToken)
    try { await authApi.logout() } catch { /* offline or already-invalid token — fine */ }
    await clearToken()
    set({ user: null, pushToken: null })
  },

  deleteAccount: async (password) => {
    // No explicit unregister needed: deleting the account drops every push
    // token server-side (admin.store.delete_user_completely). Just clear the
    // local copy so a later logout doesn't try to detach a dead token.
    await authApi.deleteAccount(password)
    await clearToken()
    set({ user: null, pushToken: null })
  },
}))
