import { request, jsonBody } from './client'

// Attach/detach this device's Expo push token to the signed-in account.
// Registration is idempotent and safe to call on every launch — Expo can
// rotate a token, and the backend reassigns one that belonged to a different
// account (shared device) rather than leaving it delivering to the old user.
export const registerDevice = (token: string) =>
  request<{ status: string }>('/notifications/device', jsonBody('POST', { token }))

export const unregisterDevice = (token: string) =>
  request<{ status: string }>('/notifications/device', {
    ...jsonBody('DELETE', { token }),
  })
