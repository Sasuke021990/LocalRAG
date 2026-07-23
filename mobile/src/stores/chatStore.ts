import { create } from 'zustand'
import * as chatApi from '../api/chat'
import { streamQuery, type Source } from '../api/query'

export interface ChatMsg {
  query: string
  answer: string
  reasoning?: string
  sources: Source[]
  refused?: boolean
  streaming?: boolean
  // The pool this turn was scoped to when sent — used only for the
  // "Searching/Analysing …" status text before any passages stream back.
  queryPool?: string
}

// Fixed retrieval depth (matches web): fetch 40 candidates, rerank, keep the
// top 20 passages. No user-facing "Retrieval" controls on either platform.
const RETRIEVE_K = 20

interface ChatState {
  history: ChatMsg[]
  loading: boolean
  activeConversationId: string
  pool: string
  poolChosen: boolean
  conversations: chatApi.ConversationSummary[]
  conversationsLoading: boolean

  loadConversations: () => Promise<void>
  newChat: () => void
  choosePool: (pool: string) => void
  openConversation: (id: string) => Promise<void>
  renameConversation: (id: string, title: string) => Promise<void>
  deleteConversation: (id: string) => Promise<void>
  submit: (query: string) => void
}

// Reconstruct display exchanges (one bubble-pair per turn) from the stored
// flat user/assistant message list — mirrors web's messagesToExchanges().
function messagesToHistory(messages: chatApi.ConversationMessage[]): ChatMsg[] {
  const out: ChatMsg[] = []
  let pendingUser: chatApi.ConversationMessage | null = null
  for (const msg of messages) {
    if (msg.role === 'user') {
      pendingUser = msg
    } else if (msg.role === 'assistant') {
      out.push({
        query: pendingUser?.content || '',
        answer: msg.content,
        reasoning: msg.reasoning || '',
        sources: (msg.sources || []) as Source[],
        refused: !!msg.refused,
        streaming: false,
        queryPool: '',
      })
      pendingUser = null
    }
  }
  return out
}

export const useChatStore = create<ChatState>((set, get) => ({
  history: [],
  loading: false,
  activeConversationId: '',
  pool: '',
  poolChosen: false,
  conversations: [],
  conversationsLoading: true,

  loadConversations: async () => {
    try {
      const res = await chatApi.listConversations()
      set({ conversations: res.conversations || [] })
    } catch {
      // sidebar/history list just stays empty
    } finally {
      set({ conversationsLoading: false })
    }
  },

  newChat: () => {
    if (get().loading) return
    set({ activeConversationId: '', history: [], pool: '', poolChosen: false })
  },

  choosePool: (pool: string) => {
    set({ pool, poolChosen: true })
  },

  openConversation: async (id: string) => {
    if (get().loading || id === get().activeConversationId) return
    const detail = await chatApi.getConversation(id)
    set({
      activeConversationId: detail.id,
      history: messagesToHistory(detail.messages),
      pool: detail.pool || '',
      poolChosen: true,
    })
  },

  renameConversation: async (id: string, title: string) => {
    await chatApi.renameConversation(id, title)
    set((s) => ({ conversations: s.conversations.map((c) => (c.id === id ? { ...c, title } : c)) }))
  },

  deleteConversation: async (id: string) => {
    await chatApi.deleteConversation(id)
    set((s) => ({ conversations: s.conversations.filter((c) => c.id !== id) }))
    if (get().activeConversationId === id) get().newChat()
  },

  submit: (query: string) => {
    const q = query.trim()
    if (!q || get().loading) return
    set({ loading: true })

    const idx = get().history.length
    const m: ChatMsg = { query: q, answer: '', reasoning: '', sources: [], refused: false, streaming: true, queryPool: get().pool }
    set((s) => ({ history: [...s.history, m] }))

    const patch = (p: Partial<ChatMsg>) =>
      set((s) => ({ history: s.history.map((h, i) => (i === idx ? { ...h, ...p } : h)) }))

    streamQuery(q, {
      topK: RETRIEVE_K * 2, rerankTopK: RETRIEVE_K,
      pool: get().pool, conversationId: get().activeConversationId,
    }, {
      onSources: (s) => patch({ sources: s }),
      onThinking: (t) => patch({ reasoning: (get().history[idx]?.reasoning || '') + t }),
      onToken: (t) => patch({ answer: (get().history[idx]?.answer || '') + t }),
      onRefusal: (msg) => patch({ answer: msg, refused: true }),
      onDone: (d) => {
        patch({
          answer: d.answer ?? get().history[idx]?.answer,
          reasoning: d.reasoning ?? get().history[idx]?.reasoning,
          refused: d.refused,
          streaming: false,
        })
        if (d.conversation_id) set({ activeConversationId: d.conversation_id })
        set({ loading: false })
        get().loadConversations()
      },
      onError: () => {
        patch({ streaming: false })
        set({ loading: false })
      },
    })
  },
}))
