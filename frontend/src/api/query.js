import { request, jsonBody } from './client.js'

export const sendQuery = (query, topK = 10, rerankTopK = 5) =>
  request('/query', jsonBody('POST', { query, top_k: topK, rerank_top_k: rerankTopK }))

export const fetchHealth = () => request('/health')

/**
 * Stream a grounded AI answer over SSE.
 * handlers: { onSources(list), onThinking(text), onToken(text), onRefusal(msg), onDone(data), onError(err) }
 * Returns a function that aborts the stream.
 */
export function streamQuery(query, { topK = 10, rerankTopK = 5 } = {}, handlers = {}) {
  const controller = new AbortController()

  ;(async () => {
    try {
      const res = await fetch('/api/query/stream', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_k: topK, rerank_top_k: rerankTopK }),
        signal: controller.signal,
      })
      if (!res.ok || !res.body) {
        let msg = `HTTP ${res.status}`
        try { const j = await res.json(); msg = j.detail || msg } catch (_) { /* */ }
        throw new Error(msg)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE frames are separated by a blank line.
        let sep
        while ((sep = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, sep)
          buffer = buffer.slice(sep + 2)
          dispatch(frame, handlers)
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') handlers.onError?.(err)
    }
  })()

  return () => controller.abort()
}

function dispatch(frame, handlers) {
  let event = 'message'
  const dataLines = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
  }
  if (dataLines.length === 0) return
  let data
  try { data = JSON.parse(dataLines.join('\n')) } catch (_) { data = dataLines.join('\n') }

  switch (event) {
    case 'sources': handlers.onSources?.(data); break
    case 'thinking': handlers.onThinking?.(data); break
    case 'token': handlers.onToken?.(data); break
    case 'refusal': handlers.onRefusal?.(data); break
    case 'done': handlers.onDone?.(data); break
    case 'error': handlers.onError?.(new Error(data?.detail || 'stream error')); break
  }
}
