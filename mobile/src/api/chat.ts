import { request, jsonBody } from './client'

export interface ConversationSummary {
  id: string
  title: string
  pool: string
  message_count: number
  preview: string
  created_at: string
  updated_at: string
}

export interface ConversationMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
  reasoning?: string
  sources?: Array<{ file_name: string; pool: string; chunk_index: number; score: number; content?: string }>
  refused?: boolean
}

export interface ConversationDetail {
  id: string
  title: string
  pool: string
  created_at: string
  updated_at: string
  messages: ConversationMessage[]
}

// Creating a conversation is not exposed here — it happens implicitly on the
// first /query(/stream) call that omits conversation_id (see api/query.ts),
// mirroring the web client.
export const listConversations = () => request<{ conversations: ConversationSummary[] }>('/chat/conversations')
export const getConversation = (id: string) => request<ConversationDetail>(`/chat/conversations/${encodeURIComponent(id)}`)
export const renameConversation = (id: string, title: string) =>
  request(`/chat/conversations/${encodeURIComponent(id)}`, jsonBody('PATCH', { title }))
export const deleteConversation = (id: string) =>
  request(`/chat/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' })
