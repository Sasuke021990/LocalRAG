import { request, jsonBody, getToken, API_BASE } from './client'

export interface Source { file_name: string; pool: string; chunk_index: number; score: number; content: string }
export interface QueryResult { answer: string; sources: Source[]; processing_time: number; reasoning?: string; refused?: boolean }

export const sendQuery = (query: string, topK = 10, rerankTopK = 5) =>
  request<QueryResult>('/query', jsonBody('POST', { query, top_k: topK, rerank_top_k: rerankTopK }))

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

/**
 * Attempt real SSE streaming; if the RN runtime doesn't expose a readable
 * response body, fall back to the plain /query endpoint and reveal the answer
 * word-by-word (~35ms/word) — visually similar, fully reliable on-device.
 */
export async function streamQuery(query: string, topK = 10, rerankTopK = 5, h: StreamHandlers = {}) {
  try {
    const token = await getToken()
    const res = await fetch(`${API_BASE}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ query, top_k: topK, rerank_top_k: rerankTopK }),
    })
    const reader = (res as any).body?.getReader?.()
    if (!reader) return await fallback(query, topK, rerankTopK, h)

    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
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
  } catch (e: any) {
    // Any streaming failure → reliable fallback path.
    try { await fallback(query, topK, rerankTopK, h) } catch (err: any) { h.onError?.(err) }
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

async function fallback(query: string, topK: number, rerankTopK: number, h: StreamHandlers) {
  const res = await sendQuery(query, topK, rerankTopK)
  h.onSources?.(res.sources || [])
  if (res.refused) {
    h.onRefusal?.(res.answer)
    h.onDone?.({ ...res, cached: res.processing_time === 0 })
    return
  }
  if (res.reasoning) h.onThinking?.(res.reasoning)
  // Typewriter reveal.
  const words = (res.answer || '').split(/(\s+)/)
  for (const w of words) {
    h.onToken?.(w)
    await new Promise((r) => setTimeout(r, 30))
  }
  h.onDone?.({ ...res, cached: res.processing_time === 0 })
}
