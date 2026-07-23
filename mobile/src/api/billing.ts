import { request, jsonBody } from './client'

// Billing is a stub for Stripe: checkout/cancel change plan + quota immediately,
// with no real payment. See backend/billing/routes.py + billing/plans.py.
export interface PlanFeatures {
  pools: boolean
  hybrid_chat: boolean
  api_tokens: boolean
  webhooks: boolean
  priority_processing: boolean
  team_members: number | null
}

export interface Plan {
  id: string
  name: string
  price_inr_monthly: number | null
  price_inr_annual: number | null
  quota_bytes: number
  storage_gb: number
  ai_questions_per_day: number
  ai_unlimited_plan_wide: boolean
  contact_only: boolean
  conversation_limit: number
  features: PlanFeatures
}

export interface Subscription {
  plan: string
  quota_bytes: number
  ai_questions_used_today: number
  ai_questions_per_day: number
  ai_unlimited_plan_wide: boolean
  features: PlanFeatures
}

export interface ContactLead {
  name: string
  email: string
  company?: string
  message?: string
}

export const fetchPlans = () => request<{ plans: Plan[] }>('/billing/plans')
export const fetchSubscription = () => request<Subscription>('/billing/subscription')
export const checkout = (plan: string) =>
  request('/billing/checkout', jsonBody('POST', { plan }))
export const cancelSubscription = () =>
  request('/billing/cancel', { method: 'POST' })
export const submitContact = (lead: ContactLead) =>
  request('/billing/contact', jsonBody('POST', lead))
