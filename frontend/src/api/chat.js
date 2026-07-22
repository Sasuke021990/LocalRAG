import { request, jsonBody } from './client.js'

// Conversation management. Creating a conversation is NOT exposed here — it
// happens implicitly on the first /query or /query/stream call that omits
// conversation_id (see api/query.js), so "New chat" never creates an empty
// orphaned conversation until a message is actually sent.
export const listConversations = () => request('/chat/conversations')
export const getConversation = (id) => request(`/chat/conversations/${encodeURIComponent(id)}`)
export const renameConversation = (id, title) =>
  request(`/chat/conversations/${encodeURIComponent(id)}`, jsonBody('PATCH', { title }))
export const deleteConversation = (id) =>
  request(`/chat/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' })
