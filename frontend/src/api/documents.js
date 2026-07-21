import { request, jsonBody, API_BASE } from './client.js'

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
