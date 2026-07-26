import { create } from 'zustand'
import * as chatApi from '../api/chat'
import { streamQuery, type Source } from '../api/query'
import { queryClient } from '../api/queryClient'
import { notifySuccess, notifyError } from '../utils/haptics'

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
  // Set when the request itself failed (network down, quota exceeded,
  // server error) — distinct from `refused`, which is a normal grounded
  // "nothing relevant found" answer. Rendered as an explicit error state
  // instead of an empty bubble.
  error?: string
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
  stop: () => void
  retry: () => void
}

// The in-flight request's abort handle. Kept outside the store because it's
// a transient control object, not renderable state — `loading` is what the
// UI actually watches.
let inFlight: AbortController | null = null

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

    const controller = new AbortController()
    inFlight = controller

    const idx = get().history.length
    const m: ChatMsg = { query: q, answer: '', reasoning: '', sources: [], refused: false, streaming: true, queryPool: get().pool }
    set((s) => ({ history: [...s.history, m] }))

    const patch = (p: Partial<ChatMsg>) =>
      set((s) => ({ history: s.history.map((h, i) => (i === idx ? { ...h, ...p } : h)) }))

    streamQuery(q, {
      topK: RETRIEVE_K * 2, rerankTopK: RETRIEVE_K,
      pool: get().pool, conversationId: get().activeConversationId,
      signal: controller.signal,
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
        inFlight = null
        set({ loading: false })
        // An answer can take tens of seconds; users look away. A success tap
        // tells them it landed without needing to watch the screen.
        notifySuccess()
        get().loadConversations()
        // This answer just consumed one of the day's AI questions — refresh
        // the cached subscription so the quota indicators (Home, Chat header)
        // count down live instead of only after a screen remount.
        queryClient.invalidateQueries({ queryKey: ['subscription'] })
      },
      onError: (e) => {
        // Surface the real failure instead of leaving an empty bubble — the
        // backend's detail message (quota exceeded, server error, etc.) is
        // already user-readable (see backend's _internal_error/rate-limit
        // messages); a raw network failure falls back to a generic message.
        patch({ streaming: false, error: e?.message || 'Something went wrong. Please try again.' })
        inFlight = null
        set({ loading: false })
        notifyError()
        // The backend counts a question at dispatch, before generation — so a
        // failed answer still spent quota. Refresh here too, or the indicator
        // would over-report what's left.
        queryClient.invalidateQueries({ queryKey: ['subscription'] })
      },
    })
  },

  stop: () => {
    if (!get().loading || !inFlight) return
    inFlight.abort()
    inFlight = null
    // Keep whatever text already streamed in — a stopped answer is partial,
    // not failed, so it stays readable rather than being wiped or marked
    // with an error.
    set((s) => ({
      loading: false,
      history: s.history.map((h, i) => (i === s.history.length - 1 ? { ...h, streaming: false } : h)),
    }))
    // The backend charged a question at dispatch, so stopping doesn't refund
    // it — refresh so the quota indicator reflects that honestly.
    queryClient.invalidateQueries({ queryKey: ['subscription'] })
  },

  retry: () => {
    if (get().loading) return
    const last = get().history[get().history.length - 1]
    if (!last) return
    // Drop the failed/stopped turn before resending, so the same question
    // doesn't appear twice in the transcript. Safe to discard: the backend
    // only persists a turn once it completes (main.py only calls
    // _persist_turn when final_data exists), so an errored or stopped turn
    // was never written server-side.
    set((s) => ({ history: s.history.slice(0, -1) }))
    get().submit(last.query)
  },
}))
