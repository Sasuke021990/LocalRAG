import { create } from 'zustand'
import type { User } from '../api/auth'

interface UsageState {
  storageUsedBytes: number
  storageQuotaBytes: number
  plan: string
  percentUsed: () => number
  syncFromUser: (user: User | null) => void
}

export const useUsageStore = create<UsageState>((set, get) => ({
  storageUsedBytes: 0,
  storageQuotaBytes: 1,
  plan: 'free',
  percentUsed: () => Math.min(100, (get().storageUsedBytes / (get().storageQuotaBytes || 1)) * 100),
  syncFromUser: (user) => {
    if (!user) return
    set({
      storageUsedBytes: user.storage_used_bytes ?? 0,
      storageQuotaBytes: user.storage_quota_bytes || 1,
      plan: (user as any).plan || 'free',
    })
  },
}))
