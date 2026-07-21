import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchPools, createPool, fetchDocuments, deleteDocument, moveDocument, uploadDocument } from './documents.js'

function mockOnce(status, body) {
  global.fetch = vi.fn().mockResolvedValue({ ok: status >= 200 && status < 300, status, json: async () => body })
}

beforeEach(() => { global.fetch = vi.fn() })
afterEach(() => { vi.restoreAllMocks() })

describe('fetchPools', () => {
  it('GETs /api/pools with same-origin credentials', async () => {
    mockOnce(200, { pools: [{ name: 'General', document_count: 0 }], total: 1 })
    await fetchPools()
    expect(global.fetch).toHaveBeenCalledWith('/api/pools', { credentials: 'same-origin' })
  })
})

describe('createPool', () => {
  it('POSTs the pool name', async () => {
    mockOnce(200, { status: 'created', pool: 'Finance' })
    await createPool('Finance')
    const [url, opts] = global.fetch.mock.calls[0]
    expect(url).toBe('/api/pools')
    expect(opts.method).toBe('POST')
    expect(opts.body).toBe(JSON.stringify({ name: 'Finance' }))
  })
})

describe('deleteDocument', () => {
  it('DELETEs with the file name and pool as query params', async () => {
    mockOnce(200, { status: 'deleted' })
    await deleteDocument('a b.pdf', 'My Pool')
    const [url, opts] = global.fetch.mock.calls[0]
    expect(url).toBe('/api/documents/a%20b.pdf?pool=My%20Pool')
    expect(opts.method).toBe('DELETE')
  })
})

describe('moveDocument', () => {
  it('PATCHes the pool with current + new', async () => {
    mockOnce(200, { status: 'moved' })
    await moveDocument('a.pdf', 'General', 'Finance')
    const [url, opts] = global.fetch.mock.calls[0]
    expect(url).toBe('/api/documents/a.pdf/pool')
    expect(opts.method).toBe('PATCH')
    expect(opts.body).toBe(JSON.stringify({ current_pool: 'General', new_pool: 'Finance' }))
  })
})

describe('uploadDocument', () => {
  it('POSTs a multipart form with the file and pool', async () => {
    mockOnce(200, { status: 'processing_started' })
    const file = new Blob(['content'])
    await uploadDocument(file, 'Research', 256, 25)
    const [url, opts] = global.fetch.mock.calls[0]
    expect(url).toBe('/api/upload')
    expect(opts.method).toBe('POST')
    expect(opts.body).toBeInstanceOf(FormData)
    expect(opts.body.get('pool')).toBe('Research')
    expect(opts.body.get('chunk_size')).toBe('256')
  })
})

describe('error handling', () => {
  it('throws the server detail on non-2xx', async () => {
    mockOnce(404, { detail: 'Document not found' })
    await expect(fetchDocuments()).rejects.toThrow('Document not found')
  })

  it('falls back to an HTTP status message when body is not JSON', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => { throw new Error('nope') } })
    await expect(fetchDocuments()).rejects.toThrow('HTTP 500')
  })
})
