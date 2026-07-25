/**
 * Tests for the upload path's two-phase progress reporting.
 *
 * Regression context: `watchUploadProgress` used React Native's global
 * `fetch`, which never exposes a readable `body.getReader()`. It therefore
 * always fell into the no-reader branch and reported an instant fake
 * "complete", so the bar never moved while the server was actually
 * processing — an 11 MB upload looked hung. Same root cause as the chat
 * streaming bug (task.md P1 #8), fixed the same way (expo/fetch).
 */

const mockExpoFetch = jest.fn()
jest.mock('expo/fetch', () => ({ fetch: (...args: any[]) => mockExpoFetch(...args) }))

jest.mock('./client', () => ({
  request: jest.fn(),
  jsonBody: jest.fn(),
  getToken: jest.fn().mockResolvedValue('jwt-123'),
  API_BASE: 'http://api.test',
  notifyUnauthorized: jest.fn(),
}))

import { uploadWithProgress, watchUploadProgress } from './documents'
import { notifyUnauthorized } from './client'

// ── XHR fake ────────────────────────────────────────────────────────────────
// Captures the instance so a test can drive upload.onprogress / onload.
let lastXhr: FakeXhr
class FakeXhr {
  upload: { onprogress?: (e: any) => void } = {}
  onload?: () => void
  onerror?: () => void
  ontimeout?: () => void
  status = 200
  responseText = '{}'
  headers: Record<string, string> = {}
  opened: [string, string] | null = null
  constructor() { lastXhr = this }
  open(method: string, url: string) { this.opened = [method, url] }
  setRequestHeader(k: string, v: string) { this.headers[k] = v }
  send(_body: any) {}
  /** Simulate the transfer then the server's response. */
  finish(status: number, body: any, transferSteps: number[] = []) {
    for (const loaded of transferSteps) {
      this.upload.onprogress?.({ lengthComputable: true, loaded, total: 100 })
    }
    this.status = status
    this.responseText = JSON.stringify(body)
    this.onload?.()
  }
}

function frames(...chunks: string[]) {
  const encoder = new TextEncoder()
  let i = 0
  return {
    read: async () => (i < chunks.length
      ? { value: encoder.encode(chunks[i++]), done: false }
      : { value: undefined, done: true }),
  }
}

const COMPLETE_FRAME = 'event: complete\ndata: {"progress":100,"message":"Done","status":"complete"}\n\n'

beforeEach(() => {
  jest.clearAllMocks()
  ;(global as any).XMLHttpRequest = FakeXhr
  // Default: progress stream immediately delivers a terminal complete event.
  // (A stream that ends *without* one now triggers reconnection — covered by
  // its own test below.)
  mockExpoFetch.mockResolvedValue({ ok: true, body: { getReader: () => frames(COMPLETE_FRAME) } })
})

test('reports byte-transfer progress during the upload phase', async () => {
  const onProgress = jest.fn()
  const promise = uploadWithProgress({ uri: 'file:///a.pdf', name: 'a.pdf' }, '', { onProgress })
  await Promise.resolve()
  lastXhr.finish(200, { task_id: '' }, [50, 100])
  await promise

  const pcts = onProgress.mock.calls.map((c) => c[0].progress)
  // Transfer occupies the first half of the bar, so 50% sent = 25% shown.
  expect(pcts).toContain(25)
  expect(pcts).toContain(50)
  expect(onProgress.mock.calls.every((c) => c[0].progress <= 50)).toBe(true)
})

test('server-side processing progress occupies the second half of the bar', async () => {
  mockExpoFetch.mockResolvedValue({
    ok: true,
    body: {
      getReader: () => frames(
        'event: progress\ndata: {"progress":0,"message":"Chunking","status":"processing"}\n\n',
        'event: progress\ndata: {"progress":100,"message":"Embedding","status":"processing"}\n\n',
        COMPLETE_FRAME,
      ),
    },
  })
  const onProgress = jest.fn()
  const promise = uploadWithProgress({ uri: 'file:///a.pdf', name: 'a.pdf' }, '', { onProgress })
  await Promise.resolve()
  lastXhr.finish(200, { task_id: 't1' })
  await promise

  const pcts = onProgress.mock.calls.map((c) => c[0].progress)
  // Server 0% maps to 50 (transfer already done), server 100% maps to 100.
  expect(pcts).toContain(50)
  expect(pcts).toContain(100)
})

test('the bar never moves backwards across the two phases', async () => {
  mockExpoFetch.mockResolvedValue({
    ok: true,
    body: {
      getReader: () => frames(
        'event: progress\ndata: {"progress":10,"message":"Chunking","status":"processing"}\n\n',
        'event: progress\ndata: {"progress":80,"message":"Embedding","status":"processing"}\n\n',
        COMPLETE_FRAME,
      ),
    },
  })
  const onProgress = jest.fn()
  const promise = uploadWithProgress({ uri: 'file:///a.pdf', name: 'a.pdf' }, '', { onProgress })
  await Promise.resolve()
  lastXhr.finish(200, { task_id: 't1' }, [25, 60, 100])
  await promise

  const pcts = onProgress.mock.calls.map((c) => c[0].progress)
  const sorted = [...pcts].sort((a, b) => a - b)
  expect(pcts).toEqual(sorted)
})

test('uses expo/fetch for the progress stream, not RN global fetch', async () => {
  const promise = uploadWithProgress({ uri: 'file:///a.pdf', name: 'a.pdf' }, '', {})
  await Promise.resolve()
  lastXhr.finish(200, { task_id: 't1' })
  await promise
  expect(mockExpoFetch).toHaveBeenCalledWith(
    'http://api.test/progress/t1',
    expect.objectContaining({ headers: { Authorization: 'Bearer jwt-123' } }),
  )
})

test('a real stream delivers processing frames instead of a fake instant complete', async () => {
  mockExpoFetch.mockResolvedValue({
    ok: true,
    body: {
      getReader: () => frames(
        'event: progress\ndata: {"progress":40,"message":"Embedding","status":"processing"}\n\n',
        'event: complete\ndata: {"progress":100,"message":"Done","status":"complete"}\n\n',
      ),
    },
  })
  const onProgress = jest.fn()
  const onDone = jest.fn()
  await watchUploadProgress('t1', { onProgress, onDone })
  expect(onProgress).toHaveBeenCalledWith(expect.objectContaining({ message: 'Embedding' }))
  expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ status: 'complete' }))
})

test('reconnects when the stream drops without a terminal event', async () => {
  // First connection dies mid-processing (no terminal frame); the second
  // delivers completion. Before the reconnect logic, the first silent drop
  // ended the watch — the progress bar vanished while the server worked on.
  mockExpoFetch
    .mockResolvedValueOnce({
      ok: true,
      body: { getReader: () => frames('event: progress\ndata: {"progress":30,"message":"Embedding","status":"processing"}\n\n') },
    })
    .mockResolvedValueOnce({ ok: true, body: { getReader: () => frames(COMPLETE_FRAME) } })
  const onDone = jest.fn()
  const onError = jest.fn()
  await watchUploadProgress('t1', { onDone, onError })
  expect(mockExpoFetch).toHaveBeenCalledTimes(2)
  expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ status: 'complete' }))
  expect(onError).not.toHaveBeenCalled()
}, 10000)

test('a non-2xx upload rejects with the backend detail message', async () => {
  const promise = uploadWithProgress({ uri: 'file:///a.pdf', name: 'a.pdf' }, '', {})
  await Promise.resolve()
  lastXhr.finish(413, { detail: 'Storage quota exceeded' })
  await expect(promise).rejects.toThrow('Storage quota exceeded')
})

test('a 401 during upload triggers the global auto-logout handler', async () => {
  const promise = uploadWithProgress({ uri: 'file:///a.pdf', name: 'a.pdf' }, '', {})
  await Promise.resolve()
  lastXhr.finish(401, { detail: 'Session revoked' })
  await expect(promise).rejects.toThrow('Session revoked')
  expect(notifyUnauthorized).toHaveBeenCalled()
})

test('attaches the bearer token to the upload request', async () => {
  const promise = uploadWithProgress({ uri: 'file:///a.pdf', name: 'a.pdf' }, '', {})
  await Promise.resolve()
  lastXhr.finish(200, { task_id: '' })
  await promise
  expect(lastXhr.headers.Authorization).toBe('Bearer jwt-123')
  expect(lastXhr.opened).toEqual(['POST', 'http://api.test/upload'])
})
