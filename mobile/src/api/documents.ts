import { request, jsonBody } from './client'

export interface Pool { name: string; document_count: number }
export interface Doc {
  key: string
  file_name: string
  pool: string
  pool_assigned: boolean
  chunk_count: number
  processed_at: string
}

export const fetchPools = () => request<{ pools: Pool[]; total: number }>('/pools')
export const createPool = (name: string) => request('/pools', jsonBody('POST', { name }))

export const fetchDocuments = () => request<{ documents: Doc[]; total: number }>('/documents')

export const deleteDocument = (fileName: string, pool: string) =>
  request(`/documents/${encodeURIComponent(fileName)}?pool=${encodeURIComponent(pool)}`, { method: 'DELETE' })

export const moveDocument = (fileName: string, currentPool: string, newPool: string) =>
  request(`/documents/${encodeURIComponent(fileName)}/pool`, jsonBody('PATCH', { current_pool: currentPool, new_pool: newPool }))

export interface PickedFile { uri: string; name: string; mimeType?: string }

export async function uploadDocument(file: PickedFile, pool = '', chunkSize = 512, chunkOverlap = 50) {
  const form = new FormData()
  // React Native FormData file shape.
  form.append('file', { uri: file.uri, name: file.name, type: file.mimeType || 'application/octet-stream' } as any)
  form.append('pool', pool)
  form.append('chunk_size', String(chunkSize))
  form.append('chunk_overlap', String(chunkOverlap))
  return request('/upload', { method: 'POST', body: form })
}
