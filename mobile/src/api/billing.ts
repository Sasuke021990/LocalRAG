import { request, jsonBody } from './client'

// Billing is a stub for Stripe: checkout/cancel change plan + quota immediately,
// with no real payment. See backend/billing/routes.py.
export interface Plan {
  id: string
  name: string
  price_cents: number
  quota_bytes: number
}

export interface Subscription {
  plan: string
  quota_bytes: number
}

export const fetchPlans = () => request<{ plans: Plan[] }>('/billing/plans')
export const fetchSubscription = () => request<Subscription>('/billing/subscription')
export const checkout = (plan: string) =>
  request('/billing/checkout', jsonBody('POST', { plan }))
export const cancelSubscription = () =>
  request('/billing/cancel', { method: 'POST' })
