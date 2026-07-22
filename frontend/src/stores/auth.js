import { defineStore } from 'pinia'
import * as authApi from '../api/auth.js'
import { useUsageStore } from './usage.js'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    checked: false,   // has fetchCurrentUser run at least once this session
  }),
  getters: {
    isAuthenticated: (s) => !!s.user,
  },
  actions: {
    _sync() {
      useUsageStore().syncFromUser(this.user)
    },
    async fetchCurrentUser() {
      try {
        this.user = await authApi.getCurrentUser()
        this._sync()
      } catch (_) {
        this.user = null
      } finally {
        this.checked = true
      }
    },
    async login(email, password) {
      this.user = await authApi.login(email, password)
      this.checked = true
      this._sync()
    },
    async signup(username, email, password) {
      this.user = await authApi.signup(username, email, password)
      this.checked = true
      this._sync()
    },
    async logout() {
      try { await authApi.logout() } finally { this.user = null }
    },
  },
})
