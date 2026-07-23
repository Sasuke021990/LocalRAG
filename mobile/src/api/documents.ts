import { request, jsonBody, getToken, API_BASE } from './client'

export interface Pool { name: string; document_count: number }
export interface Doc {
  key: string
  file_name: string
  pool: string
  pool_assigned: boolean
  chunk_count: number
  processed_at: string
}

// Kept in sync with backend/main.py ALLOWED_EXTENSIONS — images are OCR'd via
// the vision model at ingestion, so they go through the same /upload route.
export const IMAGE_MIME_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/bmp', 'image/tiff']
export const DOCUMENT_MIME_TYPES = [
  'application/pdf', 'text/*', 'application/json', 'application/xml', 'text/xml',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]

export const fetchPools = () => request<{ pools: Pool[]; total: number }>('/pools')
export const createPool = (name: string) => request('/pools', jsonBody('POST', { name }))

export const fetchDocuments = () => request<{ documents: Doc[]; total: number }>('/documents')

export const deleteDocument = (fileName: string, pool: string) =>
  request(`/documents/${encodeURIComponent(fileName)}?pool=${encodeURIComponent(pool)}`, { method: 'DELETE' })

export const moveDocument = (fileName: string, currentPool: string, newPool: string) =>
  request(`/documents/${encodeURIComponent(fileName)}/pool`, jsonBody('PATCH', { current_pool: currentPool, new_pool: newPool }))

export interface PickedFile { uri: string; name: string; mimeType?: string }

export interface UploadStartResult {
  status: string
  task_id: string
  filename: string
  pool: string
  pool_assigned: boolean
  message: string
}

export async function uploadDocument(file: PickedFile, pool = '', chunkSize = 512, chunkOverlap = 50) {
  const form = new FormData()
  // React Native FormData file shape.
  form.append('file', { uri: file.uri, name: file.name, type: file.mimeType || 'application/octet-stream' } as any)
  form.append('pool', pool)
  form.append('chunk_size', String(chunkSize))
  form.append('chunk_overlap', String(chunkOverlap))
  return request<UploadStartResult>('/upload', { method: 'POST', body: form })
}

export interface UploadProgressEvent { progress: number; message: string; status: 'processing' | 'complete' | 'failed' }
export interface UploadProgressHandlers {
  onProgress?: (p: UploadProgressEvent) => void
  onDone?: (p: UploadProgressEvent) => void
  onError?: (e: Error) => void
}

// Blank-line SSE frame separator, tolerant of \r\n / \r / \n line endings —
// same tolerant split used for /query/stream (sse_starlette uses \r\n).
const FRAME_SEP = /\r\n\r\n|\r\r|\n\n/

/**
 * Subscribes to GET /progress/{task_id}, an SSE stream (no plain-JSON polling
 * endpoint exists server-side). Mirrors the fetch+ReadableStream approach used
 * by streamQuery in api/query.ts, since RN has no native EventSource.
 */
export async function watchUploadProgress(taskId: string, h: UploadProgressHandlers) {
  try {
    const token = await getToken()
    const res = await fetch(`${API_BASE}/progress/${encodeURIComponent(taskId)}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    const reader = (res as any).body?.getReader?.()
    if (!reader) {
      h.onDone?.({ progress: 100, message: 'Done — ready to search', status: 'complete' })
      return
    }
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let m
      while ((m = FRAME_SEP.exec(buffer)) !== null) {
        const stop = dispatchProgress(buffer.slice(0, m.index), h)
        buffer = buffer.slice(m.index + m[0].length)
        if (stop) return
      }
    }
  } catch (e: any) {
    h.onError?.(e)
  }
}

function dispatchProgress(frame: string, h: UploadProgressHandlers): boolean {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of frame.split(/\r\n|\r|\n/)) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
  }
  if (!dataLines.length) return false
  let data: any
  try { data = JSON.parse(dataLines.join('\n')) } catch { return false }
  if (event === 'progress') { h.onProgress?.(data); return false }
  if (event === 'complete') { h.onDone?.(data); return true }
  if (event === 'error') { h.onError?.(new Error(data?.detail || 'progress stream error')); return true }
  return false
}

export async function uploadWithProgress(
  file: PickedFile, pool: string, handlers: UploadProgressHandlers, chunkSize = 512, chunkOverlap = 50,
) {
  const res = await uploadDocument(file, pool, chunkSize, chunkOverlap)
  if (!res.task_id) {
    handlers.onDone?.({ progress: 100, message: 'Done — ready to search', status: 'complete' })
    return res
  }
  await watchUploadProgress(res.task_id, handlers)
  return res
}
