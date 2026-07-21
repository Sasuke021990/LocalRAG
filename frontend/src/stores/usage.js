import { defineStore } from 'pinia'

export const useUsageStore = defineStore('usage', {
  state: () => ({
    storageUsedBytes: 0,
    storageQuotaBytes: 1,   // avoid divide-by-zero before first sync
    plan: 'free',           // backend UserOut has no plan field yet — defaults to free
  }),
  getters: {
    percentUsed: (s) => Math.min(100, (s.storageUsedBytes / (s.storageQuotaBytes || 1)) * 100),
  },
  actions: {
    syncFromUser(user) {
      if (!user) return
      this.storageUsedBytes = user.storage_used_bytes ?? 0
      this.storageQuotaBytes = user.storage_quota_bytes || 1
      this.plan = user.plan || 'free'
    },
  },
})
