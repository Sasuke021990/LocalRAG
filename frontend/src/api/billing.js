import { request, jsonBody } from './client.js'

// Billing is a stub for Stripe: checkout/cancel change plan + quota immediately,
// with no real payment. See backend/billing/routes.py.
export const fetchPlans = () => request('/billing/plans')
export const fetchSubscription = () => request('/billing/subscription')
export const checkout = (plan) => request('/billing/checkout', jsonBody('POST', { plan }))
export const cancelSubscription = () => request('/billing/cancel', { method: 'POST' })
