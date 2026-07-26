import { fetch as expoFetch } from 'expo/fetch'
import { request, jsonBody, getToken, API_BASE } from './client'

export interface Source { file_name: string; pool: string; chunk_index: number; score: number; content: string }
export interface QueryResult {
  answer: string
  sources: Source[]
  processing_time: number
  reasoning?: string
  refused?: boolean
  conversation_id?: string
}

export const sendQuery = (query: string, topK = 10, rerankTopK = 5, pool = '', conversationId = '') =>
  request<QueryResult>('/query', jsonBody('POST', {
    query, top_k: topK, rerank_top_k: rerankTopK,
    pool: pool || null, conversation_id: conversationId || null,
  }))

// Blank-line SSE frame separator, tolerant of \r\n / \r / \n line endings.
const FRAME_SEP = /\r\n\r\n|\r\r|\n\n/

export interface StreamHandlers {
  onSources?: (s: Source[]) => void
  onThinking?: (t: string) => void
  onToken?: (t: string) => void
  onRefusal?: (m: string) => void
  onDone?: (d: any) => void
  onError?: (e: Error) => void
}

export interface StreamOptions {
  topK?: number
  rerankTopK?: number
  pool?: string
  conversationId?: string
  // Aborting this closes the HTTP connection, which is what the backend
  // watches for: main.py's query_stream checks `is_disconnected()` before
  // every yield and calls `agen.aclose()`, propagating cancellation down
  // into the LLM backend so the inference server actually stops generating
  // (see generation/llm.py's cancel_event). Without this the model would
  // keep producing tokens nobody will read.
  signal?: AbortSignal
}

/**
 * Attempt real SSE streaming via `expo/fetch` — unlike React Native's global
 * `fetch`, Expo's fetch (SDK 51+) exposes a genuine readable `response.body`,
 * so this actually streams token-by-token instead of always silently
 * falling back to a fake typewriter reveal. If it's ever unavailable for any
 * reason (older Expo Go client, web, etc.), falls back to the plain /query
 * endpoint and reveals the answer word-by-word — visually similar, fully
 * reliable either way. `onDone`'s payload includes `conversation_id` — new
 * if `conversationId` was blank (a fresh conversation was created),
 * otherwise the one passed in.
 */
export async function streamQuery(query: string, opts: StreamOptions = {}, h: StreamHandlers = {}) {
  const { topK = 10, rerankTopK = 5, pool = '', conversationId = '', signal } = opts

  // Whether the initial streaming attempt got far enough that a failure
  // from here on is a genuine backend error (bad response, quota, etc.)
  // rather than "this runtime doesn't support readable streams" — in the
  // latter case we want to try the fallback path once, not report an error
  // before even attempting it.
  let reader: any
  try {
    const token = await getToken()
    const res = await expoFetch(`${API_BASE}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        query, top_k: topK, rerank_top_k: rerankTopK,
        pool: pool || null, conversation_id: conversationId || null,
      }),
      signal,
    })
    if (!res.ok) {
      // A real backend error (quota exceeded, server error, etc.) — the
      // body is a plain JSON error, not an SSE stream, so read it as such
      // and surface it directly rather than misreading it as stream frames
      // or silently retrying the same failing request a second time.
      let detail = `HTTP ${res.status}`
      try { detail = (await res.json())?.detail || detail } catch { /* non-JSON error body */ }
      throw Object.assign(new Error(detail), { status: res.status })
    }
    reader = (res as any).body?.getReader?.()
  } catch (err: any) {
    // A user-initiated stop aborts the fetch, which surfaces here as a
    // rejection. That's a deliberate cancellation, not a failure: reporting
    // it via onError would paint a red "something went wrong" bubble over an
    // answer the user chose to stop, and falling back would re-run the query
    // they just cancelled (double-charging their daily quota).
    if (signal?.aborted) return
    if (err?.status) { h.onError?.(err); return } // real HTTP error — already reported, don't fall back
    reader = undefined // network-level failure before we even got a response — fall back
  }

  if (!reader) {
    // No readable stream support on this runtime, or the initial request
    // itself failed at the network level — either way, try exactly once
    // more via the plain /query endpoint. A failure here is real and must
    // reach onError, not be silently retried again.
    try { await fallback(query, topK, rerankTopK, pool, conversationId, h, signal) }
    catch (err: any) { if (!signal?.aborted) h.onError?.(err) }
    return
  }

  try {
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      // Stop pulling the moment the user cancels, rather than draining
      // whatever the server already queued.
      if (signal?.aborted) { reader.cancel?.().catch?.(() => {}); return }
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // SSE frames are separated by a blank line; sse_starlette uses \r\n
      // endings (\r\n\r\n), so match any blank-line form rather than only \n\n.
      let m
      while ((m = FRAME_SEP.exec(buffer)) !== null) {
        dispatch(buffer.slice(0, m.index), h)
        buffer = buffer.slice(m.index + m[0].length)
      }
    }
  } catch (err: any) {
    // Same reasoning as the pre-response abort above: a cancelled read is
    // the user's own doing, not an error to surface.
    if (signal?.aborted) return
    // A stream that started but broke mid-flight (dropped connection, server
    // error) — this is a real failure, not a "no stream support" case, so it
    // must reach onError directly rather than silently retrying the query a
    // second time (which could double-consume the daily AI-question quota).
    h.onError?.(err)
  }
}

function dispatch(frame: string, h: StreamHandlers) {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of frame.split(/\r\n|\r|\n/)) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
  }
  if (!dataLines.length) return
  let data: any
  try { data = JSON.parse(dataLines.join('\n')) } catch { data = dataLines.join('\n') }
  if (event === 'sources') h.onSources?.(data)
  else if (event === 'thinking') h.onThinking?.(data)
  else if (event === 'token') h.onToken?.(data)
  else if (event === 'refusal') h.onRefusal?.(data)
  else if (event === 'done') h.onDone?.(data)
  else if (event === 'error') h.onError?.(new Error(data?.detail || 'stream error'))
}

async function fallback(
  query: string, topK: number, rerankTopK: number, pool: string, conversationId: string,
  h: StreamHandlers, signal?: AbortSignal,
) {
  const res = await sendQuery(query, topK, rerankTopK, pool, conversationId)
  if (signal?.aborted) return
  h.onSources?.(res.sources || [])
  if (res.refused) {
    h.onRefusal?.(res.answer)
    h.onDone?.({ ...res, cached: res.processing_time === 0 })
    return
  }
  if (res.reasoning) h.onThinking?.(res.reasoning)
  // Typewriter reveal. The answer is already fully in hand here, so stopping
  // only halts the reveal — nothing upstream is still generating.
  const words = (res.answer || '').split(/(\s+)/)
  for (const w of words) {
    if (signal?.aborted) return
    h.onToken?.(w)
    await new Promise((r) => setTimeout(r, 30))
  }
  h.onDone?.({ ...res, cached: res.processing_time === 0 })
}
