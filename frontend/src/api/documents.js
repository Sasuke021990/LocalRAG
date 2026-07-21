import { request, jsonBody, API_BASE } from './client.js'

// Kept in sync with the backend's ALLOWED_EXTENSIONS (backend/main.py).
// Images are OCR'd/described via a vision model at ingestion time, so they
// become searchable/chat-able just like any text document.
export const ACCEPTED_FILE_TYPES =
  '.pdf,.docx,.txt,.csv,.md,.html,.htm,.json,.xml,.png,.jpg,.jpeg,.webp,.gif,.bmp,.tiff,.tif'

// ─── Pools ───
export const fetchPools = () => request('/pools')
export const createPool = (name) => request('/pools', jsonBody('POST', { name }))
export const deletePool = (name) => request(`/pools/${encodeURIComponent(name)}`, { method: 'DELETE' })

// ─── Documents ───
export const fetchDocuments = () => request('/documents')

export const deleteDocument = (fileName, pool) =>
  request(`/documents/${encodeURIComponent(fileName)}?pool=${encodeURIComponent(pool)}`, { method: 'DELETE' })

export const moveDocument = (fileName, currentPool, newPool) =>
  request(`/documents/${encodeURIComponent(fileName)}/pool`, jsonBody('PATCH', { current_pool: currentPool, new_pool: newPool }))

// pool may be '' — the backend then lands it in General flagged pool_assigned=false.
export function uploadDocument(file, pool = '', chunkSize = 512, chunkOverlap = 50) {
  const form = new FormData()
  form.append('file', file)
  form.append('pool', pool)
  form.append('chunk_size', chunkSize)
  form.append('chunk_overlap', chunkOverlap)
  return request('/upload', { method: 'POST', body: form })
}

/**
 * Watch a background ingestion task's real progress (parse → chunk → embed →
 * store, plus OCR for images) via the `GET /progress/{task_id}` SSE stream.
 * handlers: { onProgress({progress, message}), onDone({progress, message, status}), onError(err) }
 * `status` on the terminal event is 'complete' or 'failed'.
 * Returns a function that stops watching (closes the stream early).
 */
export function watchUploadProgress(taskId, handlers = {}) {
  // Same-origin request (browser talks only to :3000; the Express proxy
  // forwards to the backend server-side) so the session cookie is sent
  // automatically — no Authorization header needed/possible on EventSource.
  const es = new EventSource(`${API_BASE}/progress/${encodeURIComponent(taskId)}`, { withCredentials: true })
  es.addEventListener('progress', (e) => handlers.onProgress?.(JSON.parse(e.data)))
  es.addEventListener('complete', (e) => { handlers.onDone?.(JSON.parse(e.data)); es.close() })
  es.addEventListener('error', (e) => {
    let detail
    try { detail = JSON.parse(e.data)?.detail } catch (_) { /* connection-level error, no payload */ }
    handlers.onError?.(new Error(detail || 'Progress stream error'))
    es.close()
  })
  return () => es.close()
}

/**
 * Upload a file and watch it through to completion in one call — combines
 * uploadDocument + watchUploadProgress so callers don't have to wire the two
 * together by hand.
 * handlers: { onQueued(uploadResponse), onProgress({progress, message}), onDone({...}), onError(err) }
 */
export function uploadWithProgress(file, pool, chunkSize, chunkOverlap, handlers = {}) {
  ;(async () => {
    let res
    try {
      res = await uploadDocument(file, pool, chunkSize, chunkOverlap)
    } catch (e) {
      handlers.onError?.(e)
      return
    }
    handlers.onQueued?.(res)
    if (!res.task_id) {
      // Defensive fallback if an older backend doesn't return a task_id yet.
      handlers.onDone?.({ progress: 100, message: res.message, status: 'complete' })
      return
    }
    watchUploadProgress(res.task_id, handlers)
  })()
}
