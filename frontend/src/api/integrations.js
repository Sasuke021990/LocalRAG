import { request, jsonBody } from './client.js'

// ─── MCP / API tokens ───
export const fetchTokens = () => request('/integrations/tokens')
export const createToken = (name) => request('/integrations/tokens', jsonBody('POST', { name }))
export const revokeToken = (tokenId) => request(`/integrations/tokens/${encodeURIComponent(tokenId)}`, { method: 'DELETE' })

// ─── Webhooks ───
export const WEBHOOK_EVENTS = ['document.ingested', 'document.deleted', 'document.ingest_failed']

export const fetchWebhooks = () => request('/integrations/webhooks')
export const createWebhook = (url, events, secret) =>
  request('/integrations/webhooks', jsonBody('POST', secret ? { url, events, secret } : { url, events }))
export const deleteWebhook = (id) => request(`/integrations/webhooks/${encodeURIComponent(id)}`, { method: 'DELETE' })
export const testWebhook = (id) => request(`/integrations/webhooks/${encodeURIComponent(id)}/test`, { method: 'POST' })
